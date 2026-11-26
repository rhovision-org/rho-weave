"""Run manifest-derived reservation controllers in a loopback-only Rholo node."""

import argparse
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryFile
from threading import Thread
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from rhoweave.anchor import anchored_read
from rhoweave.machine import compile_recovery


ROOT = Path(__file__).resolve().parents[1]
RHOLO_COMMIT = "e63b7e5a8ccfcc25ff64860ac989d95a748eaaca"
RHOLO_SHA = "232d12bd5d3fadc8371c26ec6a888ea48a4062b1187bb63c35b9d19423f28ead"


@contextmanager
def relay(request):
    # Two observation URLs can expose one dev node for this topology test.
    # They relay the exact native responses and represent one operator.
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/api/status", "/api/last-finalized-block"):
                self.send_error(404)
                return
            try:
                data = json.dumps(request(self.path)).encode()
            except (OSError, ValueError):
                self.send_error(502)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            worker.join()


@contextmanager
def start_observer(binary, request):
    with ExitStack() as cleanup:
        sources = [cleanup.enter_context(relay(request)) for _ in range(2)]
        with socket.socket() as port:
            port.bind(("127.0.0.1", 0))
            address = f"127.0.0.1:{port.getsockname()[1]}"
        opener = build_opener(ProxyHandler({}))

        def fetch():
            with opener.open(f"http://{address}/v1/read-anchor", timeout=2) as response:
                return json.loads(response.read(64_000))

        args = [str(binary), "--node", "a=" + sources[0], "--node", "b=" + sources[1],
                "serve", "--listen", address, "--refresh-ms", "1000"]
        with TemporaryFile() as log, subprocess.Popen(args, stdout=log, stderr=log) as process:
            try:
                deadline = monotonic() + 15
                while monotonic() < deadline and process.poll() is None:
                    try:
                        fetch()
                    except URLError:
                        sleep(0.2)
                    else:
                        break
                else:
                    log.seek(0)
                    details = request("/api/last-finalized-block")
                    raise RuntimeError(f"Observer could not select the native anchor: {details!r}; "
                                       f"{log.read(2000).decode(errors='replace')}")
                yield fetch
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def forge_cases(forge):
    from rhoforge.partition import compile_partitioned

    manifest, factory = compile_partitioned(json.loads((forge / "examples/venues.json").read_text()))
    objective = json.loads((ROOT / "examples/venue-recovery.json").read_text())
    _, cert, table, recovery = compile_recovery(manifest, objective, "free_a")
    if cert["status"] != "WIN":
        raise AssertionError("expected a winning venue policy")
    _, blind, _, generated = compile_recovery(manifest, {**objective, "observe": []}, "free_a")
    if blind["status"] != "NO_POLICY" or generated is not None:
        raise AssertionError("a blind controller could take an unavailable action")

    marks = manifest["lanes"]["free_a"]["markings"]
    target = next(i for i, row in enumerate(marks) if row["issued_a"] == 3)
    cold = table["nodes"][table["initial"]["held_a=0,issued_a=0"]]
    resumed = table["nodes"][table["initial"]["held_a=2,issued_a=1"]]
    if min(cold["actions"]) != "reserve_all_a" or min(resumed["actions"]) != "issue_a":
        raise AssertionError("wrong one-lane recovery choices")

    def term(body):
        return f'''new result, factory, recover, ready in {{
          {factory} | {recovery} | factory!("free_a", *ready) |
          for (view, clerk, manager <- ready) {{ {body} }}
        }}'''

    run = "new done in { recover!(*view, *clerk, *done) | for (@x <- done) { result!(x) } }"
    prefix = '''new a, b in {
      clerk!("reserve_all_a", 0, *a) |
      for (@first <- a) {
        clerk!("issue_a", 1, *b) |
        for (@lost_client_reply <- b) { %s }
      }
    }'''
    yield "forge:cold", term(run), ["DONE", target, 4]
    yield "forge:reply-lost-after-first-issue", term(prefix % run), ["DONE", target, 4]
    yield "forge:wrong-capability", term(run.replace("*clerk", "*manager")), ["DEFER", 0, 0]


def foundry_case(foundry):
    from foundry.core import compile_protocol

    raw = json.loads((foundry / "examples/reservation.json").read_text())
    manifest, factory = compile_protocol(raw)
    objective = {"name": "finish_sale", "role": "agent", "initial": [{"sold": 0}],
                 "goal": {"sold": 3}, "avoid": [], "observe": ["held", "sold"],
                 "operations": ["hold", "buy"]}
    _, cert, _, recovery = compile_recovery(manifest, objective)
    if cert["status"] != "WIN":
        raise AssertionError("expected a winning Foundry policy")
    sold = manifest["resources"].index("sold")
    target = next(i for i, row in enumerate(manifest["states"]) if row[sold] == 3)
    term = f'''new result, factory, recover, ready in {{
      {factory} | {recovery} | factory!(*ready) |
      for (agent, customer <- ready) {{
        new done in {{ recover!(*agent, *done) | for (@x <- done) {{ result!(x) }} }}
      }}
    }}'''
    return "foundry:issue-three", term, ["DONE", target, 6]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forge", type=Path, required=True)
    parser.add_argument("--foundry", type=Path)
    parser.add_argument("--observer", type=Path, help="optional built rchain-observer binary")
    parser.add_argument("--rholo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    forge = args.forge.resolve()
    sys.path[:0] = [str(forge), str(forge / "tools")]
    from isolated_rholo import run
    from probe_generated import decode

    cases = list(forge_cases(forge))
    if args.foundry:
        sys.path.insert(0, str(args.foundry.resolve()))
        cases.append(foundry_case(args.foundry))

    def probe(request, _repeats, runtime_anchor):
        status = request("/api/status")
        network, shard = status["networkId"], status["shardId"]
        rows = []
        with ExitStack() as cleanup:
            fetch = cleanup.enter_context(start_observer(args.observer.resolve(), request)) if args.observer else None
            for name, term, expected in cases:
                def explore(block_hash):
                    reply = request("/api/explore-deploy-by-block-hash", {
                        "term": term, "blockHash": block_hash, "usePreStateHash": False,
                    })
                    if reply.get("replySource") != "firstPrivateName":
                        raise ValueError("unexpected native result channel")
                    return {"block_hash": reply["block"]["blockHash"], "network_id": network,
                            "shard_id": shard, "value": [decode(item) for item in reply["expr"]]}

                evidence = None
                if fetch:
                    anchor, actual = anchored_read(fetch, lambda a: explore(a.block_hash),
                                                   network=network, shard=shard, max_age_ms=10_000)
                    used_hash, evidence = anchor.block_hash, anchor.evidence
                else:
                    reply = explore(runtime_anchor)
                    used_hash, actual = reply["block_hash"], reply["value"]
                if used_hash != runtime_anchor or actual != [expected]:
                    raise AssertionError(f"{name}: {used_hash}, {actual!r} != {runtime_anchor}, {[expected]!r}")
                rows.append({"fixture": name, "passed": True, "actual": actual[0],
                             "block_hash": used_hash, "observer_evidence": evidence})
                print(name, actual[0], flush=True)
        return rows

    report = run(args.rholo.resolve(), RHOLO_SHA, RHOLO_COMMIT, 1, probe)
    report["observer_topology"] = "two local routes to one isolated node" if args.observer else None
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("PASS", report["fixture_count"], "native recovery scenarios")


if __name__ == "__main__":
    main()
