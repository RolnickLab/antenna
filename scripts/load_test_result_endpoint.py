#!/usr/bin/env python3
"""Fire concurrent batched POSTs against ``POST /api/v2/jobs/{id}/result/``.

Reproduces the row-lock contention pathology described in
``docs/claude/debugging/row-lock-contention-reproduction.md``. Each POST body
contains N fake ``PipelineResultsError`` entries so the per-result
``job.logger.info(...)`` call inside ``ATOMIC_REQUESTS`` stacks N UPDATEs on
``jobs_job.logs`` in a single view transaction — the shape real ADC workers
produce (``AMI_LOCALIZATION_BATCH_SIZE=4``, ``AMI_CLASSIFICATION_BATCH_SIZE=150``).

A single-result-per-POST loop does NOT reproduce the contention. Batching
is load-bearing.

Usage:

    export ANTENNA_TOKEN=...
    python scripts/load_test_result_endpoint.py <job_id> \\
        [--batch 50] [--concurrency 10] [--rounds 3] \\
        [--host http://localhost:8000]

Dependencies: Python 3.10+, stdlib only.
"""
import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def make_body(batch_size: int, prefix: str) -> bytes:
    results = [
        {
            "reply_subject": f"{prefix}.r{i}.{uuid.uuid4().hex[:8]}",
            "result": {"error": "load-test", "image_id": f"img-{prefix}-{i}"},
        }
        for i in range(batch_size)
    ]
    return json.dumps({"results": results}).encode()


def fire_one(url: str, token: str, body: bytes, idx: int) -> tuple[int, int, float, str]:
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return (idx, resp.status, time.time() - t0, "")
    except urllib.error.HTTPError as e:
        return (idx, e.code, time.time() - t0, f"HTTPError: {e.reason}")
    except urllib.error.URLError as e:
        return (idx, -1, time.time() - t0, f"URLError: {e.reason}")
    except Exception as e:
        return (idx, -1, time.time() - t0, f"{type(e).__name__}: {e}")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"must be an integer, got {value!r}") from e
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {parsed}")
    return parsed


def _http_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise argparse.ArgumentTypeError(f"must be an http(s) URL, got {value!r}")
    return value.rstrip("/")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id", type=_positive_int, help="Target Job.pk (must be in a running state)")
    ap.add_argument(
        "--token",
        default=os.environ.get("ANTENNA_TOKEN"),
        help="DRF auth Token (default: $ANTENNA_TOKEN). Prefer the env var to avoid shell-history leakage.",
    )
    ap.add_argument("--batch", type=_positive_int, default=50, help="results per POST body (default 50)")
    ap.add_argument("--concurrency", type=_positive_int, default=10, help="parallel POSTs per round (default 10)")
    ap.add_argument("--rounds", type=_positive_int, default=3, help="how many waves to fire (default 3)")
    ap.add_argument(
        "--host", type=_http_url, default="http://localhost:8000", help="API host (default localhost:8000)"
    )
    args = ap.parse_args()

    if not args.token:
        ap.error("no token provided: set ANTENNA_TOKEN env var or pass --token")

    url = f"{args.host}/api/v2/jobs/{args.job_id}/result/"
    # Never print the token — just echo the request shape.
    print(f"url={url} batch={args.batch} concurrency={args.concurrency} rounds={args.rounds}")

    t_start = time.time()
    for round_idx in range(args.rounds):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [
                ex.submit(fire_one, url, args.token, make_body(args.batch, f"r{round_idx}_{i}"), i)
                for i in range(args.concurrency)
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        good = sum(1 for _, s, _, _ in results if s == 200)
        latencies = sorted([lat for _, _, lat, _ in results])
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(
            f"round {round_idx}: ok={good}/{args.concurrency} "
            f"p50={p50:.2f}s p95={p95:.2f}s elapsed={time.time() - t_start:.1f}s"
        )
        errors = [(idx, status, err) for idx, status, _, err in results if err]
        for idx, status, err in errors[:5]:
            print(f"  err[{idx}] status={status} {err}", file=sys.stderr)
        if len(errors) > 5:
            print(f"  ...{len(errors) - 5} more errors suppressed", file=sys.stderr)


if __name__ == "__main__":
    main()
