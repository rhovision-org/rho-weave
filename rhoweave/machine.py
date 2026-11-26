"""Synthesize a bounded recovery controller from an enumerated actor artifact."""

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from .__main__ import MAX_ARTIFACT, atomic_json, load, parse_json
from .engine import MAX_STATES, LimitError, Model, ModelError, prepare_policy

FORGE = "rho-forge/v1"
PARTITIONED = "rho-forge/partitioned-v1"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}")
MAX_CONTROLLER_BYTES = 512_000


def _need(condition, message):
    if not condition:
        raise ModelError(message)


def _identifier(value):
    return type(value) is str and NAME.fullmatch(value) is not None


def _names(values, where):
    _need(type(values) is list and len(values) <= 256 and all(map(_identifier, values)),
          f"invalid {where}")
    _need(len(values) == len(set(values)), f"duplicate {where}")
    return values


def _state_id(value, count):
    return type(value) is int and 0 <= value < count


def _counts(marking, resources):
    return type(marking) is dict and set(marking) <= set(resources) and all(
        type(value) is int and 0 <= value <= 1_000_000 for value in marking.values()
    )


def _forge_rows(table, role, count):
    actions = table["actions"][role]
    _need(type(actions) is dict and set(actions) == {str(i) for i in range(count)},
          "incomplete Forge action table")
    for source, row in actions.items():
        _need(type(row) is dict, "invalid Forge action row")
        for op, step in row.items():
            _need(type(step) is dict and set(step) == {"target", "plan"}
                  and type(step["plan"]) is list, "invalid Forge rule")
            target = step["target"]
            _need(_state_id(target, count), "invalid Forge rule target")
            if step["plan"]:
                yield int(source), op, target
            else:
                _need(target == int(source), "non-mutating rule changes state")


def _artifact(artifact, lane, role):
    _need(type(artifact) is dict, "machine artifact must be an object")
    kind = artifact.get("schema")
    roles = _names(artifact["roles"], "machine roles")
    _need(role in roles, "objective requires an undeclared role")
    if kind in (FORGE, PARTITIONED):
        if kind == PARTITIONED:
            _need(_identifier(lane) and lane in artifact["lanes"], "select a valid Forge lane with --lane")
            table = artifact["lanes"][lane]
        else:
            _need(lane is None, "--lane requires a partitioned Forge artifact")
            table = artifact
        resources = _names(table["places"], "places")
        markings = table["markings"]
        _need(type(markings) is list, "invalid Forge markings")
        rows = _forge_rows(table, role, len(markings))
    elif type(kind) is int and kind == 1:
        _need(lane is None, "--lane requires a partitioned Forge artifact")
        resources = _names(artifact["resources"], "resources")
        states = artifact["states"]
        _need(type(states) is list and all(type(v) is list and len(v) == len(resources) for v in states),
              "invalid Foundry state vectors")
        markings = [dict(zip(resources, v)) for v in states]
        rows = ((r["state"], r["operation"], r["target"]) for r in artifact["rules"] if r["role"] == role)
    else:
        raise ModelError("expected an enumerated Forge or Foundry machine")
    _need(resources and markings, "empty machine table")
    if len(markings) > MAX_STATES:
        raise LimitError("machine exceeds Weave's concrete-state budget")
    _need(all(_counts(m, resources) and len(m) == len(resources) for m in markings), "invalid markings")
    _need(len({tuple(m[r] for r in resources) for m in markings}) == len(markings),
          "ambiguous duplicate markings")
    edges = {}
    for source, op, target in rows:
        _need(_state_id(source, len(markings)) and _state_id(target, len(markings))
              and _identifier(op), "invalid machine rule")
        _need((source, op) not in edges, "duplicate machine rule")
        edges[source, op] = target
    return kind, resources, markings, edges


def _contains(marking, pattern):
    return all(marking[k] == v for k, v in pattern.items())


def _build(artifact, objective, lane):
    fields = {"name", "role", "initial", "goal", "avoid", "observe", "operations"}
    _need(type(objective) is dict and set(objective) == fields, "invalid recovery objective fields")
    name, role = objective["name"], objective["role"]
    _need(_identifier(name) and _identifier(role), "invalid objective name or role")
    kind, resources, markings, edges = _artifact(artifact, lane, role)
    observed = sorted(_names(objective["observe"], "observed resources"))
    _need(set(observed) <= set(resources), "unknown observed resource")
    allowed = set(_names(objective["operations"], "operations"))
    _need(allowed and allowed <= {op for _, op in edges}, "operation unavailable to selected role")
    initial, goal, avoid = objective["initial"], objective["goal"], objective["avoid"]
    _need(type(initial) is list and 0 < len(initial) <= MAX_STATES and
          type(avoid) is list and len(avoid) <= MAX_STATES, "invalid marking pattern lists")
    _need(all(_counts(p, resources) and p for p in [*initial, goal, *avoid]), "invalid marking pattern")

    nodes = {}
    for i, marking in enumerate(markings):
        label = ",".join(f"{r}={marking[r]}" for r in observed) or "hidden"
        safe = not any(_contains(marking, p) for p in avoid)
        nodes[str(i)] = {"observation": label, "safe": safe,
                         "goal": safe and _contains(marking, goal)}
    model = {
        "name": name,
        "states": nodes,
        "initial": [str(i) for i, m in enumerate(markings) if any(_contains(m, p) for p in initial)],
        "transitions": [[str(s), op, str(t)] for (s, op), t in sorted(edges.items())
                        if op in allowed and not nodes[str(s)]["goal"]],
    }
    _need(model["initial"], "initial patterns match no reachable marking")
    return kind, model, edges


def _controller(kind, model, cert, table, edges):
    beliefs = cert["nodes"]
    queue = deque(sorted(set(table["initial"].values())))
    seen = set(queue)
    branches = []
    while queue:
        node = queue.popleft()
        policy = table["nodes"][node]
        if policy["rank"] == 0:
            branches.append(f'          ({node}, _) => {{ ret!(("DONE", sid, revision)) }}')
            continue
        op = min(policy["actions"])
        outcomes = policy["actions"][op]
        for state in beliefs[int(node)]["belief"]:
            target = edges[int(state), op]
            label = model["states"][str(target)]["observation"]
            successor = outcomes[label]
            branches.append(
                f'          ({node}, {state}) => {{ sendop!({json.dumps(op)}, {target}, {successor}, revision) }}'
            )
        for successor in sorted(set(outcomes.values()) - seen):
            seen.add(successor)
            queue.append(successor)
        if len(branches) > 8192:
            raise LimitError("recovery controller branch budget exceeded")

    forge = kind in (FORGE, PARTITIONED)
    start_op = "viewcap!(*initial)" if forge else 'writecap!("inspect", 0, *initial)'
    start_status = "READ" if forge else "STATE"
    signature = "viewcap, writecap, ret" if forge else "writecap, ret"
    extra = ", plan" if forge else ""
    initial_cases = []
    for state in model["initial"]:
        label = model["states"][state]["observation"]
        node = table["initial"][label]
        initial_cases.append(f'        ("{start_status}", {state}) => {{ nextstep!({node}, sid, revision) }}')
    source = "\n".join([
        "// Rho Weave recovery controller; model sha256 " + cert["model_sha256"],
        f"contract recover({signature}) = {{",
        "  new initial, nextstep, sendop in {",
        "    contract nextstep(@node, @sid, @revision) = {",
        "      match (node, sid) {",
        *branches,
        '        _ => { ret!(("DEFER", sid, revision)) }',
        "      }",
        "    } |",
        "    contract sendop(@op, @target, @successor, @expected) = {",
        "      new ack in {",
        "        writecap!(op, expected, *ack) |",
        f"        for (@(status, sid, revision{extra}) <- ack) {{",
        '          match (status == "OK", sid == target, revision == expected + 1) {',
        "            (true, true, true) => { nextstep!(successor, sid, revision) }",
        '            _ => { ret!(("DEFER", sid, revision)) }',
        "          }",
        "        }",
        "      }",
        "    } |",
        f"    {start_op} |",
        f"    for (@(status, sid, revision{extra}) <- initial) {{",
        "      match (status, sid) {",
        *initial_cases,
        '        _ => { ret!(("DEFER", sid, revision)) }',
        "      }",
        "    }",
        "  }",
        "}",
        "",
    ])
    if len(source.encode()) > MAX_CONTROLLER_BYTES:
        raise LimitError("recovery controller byte budget exceeded")
    return source


def compile_recovery(artifact, objective, lane=None):
    """Return a model, checked certificate, portable policy and Rholang source."""
    kind, raw, edges = _build(artifact, objective, lane)
    model = Model.parse(raw)
    cert, table = prepare_policy(model, export=True)
    source = _controller(kind, raw, cert, table, edges) if table is not None else None
    return raw, cert, table, source


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("machine", type=Path)
    parser.add_argument("objective", type=Path)
    parser.add_argument("--lane")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args(argv)
    try:
        if args.out.exists():
            raise ModelError("output directory already exists")
        with args.machine.open("rb") as stream:
            machine_bytes = stream.read(MAX_ARTIFACT + 1)
        if len(machine_bytes) > MAX_ARTIFACT:
            raise LimitError("machine artifact byte budget exceeded")
        artifact = parse_json(machine_bytes)
        objective = load(args.objective)
        model, cert, table, source = compile_recovery(artifact, objective, args.lane)
        with TemporaryDirectory(prefix=".weave-machine-", dir=args.out.parent) as staging:
            target = Path(staging) / "bundle"
            target.mkdir()
            atomic_json(target / "model.json", model)
            atomic_json(target / "certificate.json", cert)
            if table is not None:
                atomic_json(target / "policy.json", table)
                (target / "recovery.rho").write_text(source, encoding="utf-8", newline="\n")
            atomic_json(target / "binding.json", {
                "machine_sha256": hashlib.sha256(machine_bytes).hexdigest(),
                "model_sha256": cert["model_sha256"],
                "role": objective["role"],
                "lane": args.lane,
                "controller_sha256": hashlib.sha256(source.encode()).hexdigest() if source else None,
            })
            target.rename(args.out)
        print(json.dumps({"status": cert["status"], "output": str(args.out)}))
        return 0 if cert["status"] == "WIN" else 1
    except (LimitError, RecursionError) as error:
        result = {"status": "UNKNOWN", "reason": str(error)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        result = {"status": "ERROR", "reason": str(error)}
    print(json.dumps(result), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
