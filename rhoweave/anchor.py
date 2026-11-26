"""Optional binding of by-hash reads to fresh Observer evidence."""

from dataclasses import dataclass
import re
from time import monotonic_ns

from .engine import ModelError

HEX = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ReadAnchor:
    network_id: str
    shard_id: str
    block_number: int
    block_hash: str
    evidence: str


def anchored_read(fetch_evidence, read_by_hash, *, network, shard, max_age_ms):
    """Return (anchor, value) using caller-trusted evidence and read transports.

    Callbacks supply the evidence object and a response bound to its chain,
    shard and block hash. No fallback or mutation is performed here.
    """
    if type(max_age_ms) is not int or max_age_ms < 1:
        raise ModelError("positive anchor freshness bound required")
    start = monotonic_ns()
    report = fetch_evidence()
    if (type(report) is not dict or report.get("schema") != "rho-observer/read-anchor/v1"
        or report.get("status") != "available"
        or report.get("evidence") not in ("unanimous_reports", "verified_ancestry")):
        raise ModelError("read anchor unavailable")
    age = report.get("snapshot_age_ms")
    stale_after = report.get("stale_after_ms")
    sources = report.get("observed_nodes")
    comparable = report.get("comparable_nodes")
    if (type(age) is not int or age < 0 or type(stale_after) is not int or stale_after < 1
        or type(sources) is not int or sources < 2 or type(comparable) is not int or sources != comparable):
        raise ModelError("invalid anchor freshness or coverage")
    detail = report.get("anchor")
    if (type(detail) is not dict or type(network) is not str or not network
        or type(shard) is not str or not shard or detail.get("network_id") != network
        or detail.get("shard_id") != shard or type(detail.get("block_number")) is not int
        or detail["block_number"] < 0 or type(detail.get("block_hash")) is not str
        or HEX.fullmatch(detail["block_hash"]) is None):
        raise ModelError("anchor does not match expected network, shard or block identity")
    anchor = ReadAnchor(network, shard, detail["block_number"], detail["block_hash"], report["evidence"])
    budget_ns = (min(max_age_ms, stale_after) - age) * 1_000_000
    if monotonic_ns() - start >= budget_ns:
        raise ModelError("read anchor freshness expired")
    reply = read_by_hash(anchor)
    if monotonic_ns() - start >= budget_ns:
        raise ModelError("read anchor freshness expired")
    expected = (anchor.network_id, anchor.shard_id, anchor.block_hash)
    if (type(reply) is not dict or "value" not in reply
        or (reply.get("network_id"), reply.get("shard_id"), reply.get("block_hash")) != expected):
        raise ModelError("read response does not match the anchor")
    return anchor, reply["value"]
