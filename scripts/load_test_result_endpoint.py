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

    python scripts/load_test_result_endpoint.py <job_id> <token> \\
        [--batch 50] [--concurrency 10] [--rounds 3] \\
        [--host http://localhost:8000]

Dependencies: Python 3.10+, stdlib only.
"""
import argparse
import concurrent.futures
import json
import time
import urllib.error
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


def fire_one(url: str, token: str, body: bytes, idx: int) -> tuple[int, int, float]:
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return (idx, resp.status, time.time() - t0)
    except urllib.error.HTTPError as e:
        return (idx, e.code, time.time() - t0)
    except Exception:
        return (idx, -1, time.time() - t0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job_id", type=int, help="Target Job.pk (must be in a running state)")
    ap.add_argument("token", help="DRF auth Token for a user with result-POST permission")
    ap.add_argument("--batch", type=int, default=50, help="results per POST body (default 50)")
    ap.add_argument("--concurrency", type=int, default=10, help="parallel POSTs per round (default 10)")
    ap.add_argument("--rounds", type=int, default=3, help="how many waves to fire (default 3)")
    ap.add_argument("--host", default="http://localhost:8000", help="API host (default localhost:8000)")
    args = ap.parse_args()

    url = f"{args.host}/api/v2/jobs/{args.job_id}/result/"
    print(f"url={url} batch={args.batch} concurrency={args.concurrency} rounds={args.rounds}")

    t_start = time.time()
    for round_idx in range(args.rounds):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [
                ex.submit(fire_one, url, args.token, make_body(args.batch, f"r{round_idx}_{i}"), i)
                for i in range(args.concurrency)
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        good = sum(1 for _, s, _ in results if s == 200)
        latencies = sorted([lat for _, _, lat in results])
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(
            f"round {round_idx}: ok={good}/{args.concurrency} "
            f"p50={p50:.2f}s p95={p95:.2f}s elapsed={time.time() - t_start:.1f}s"
        )


if __name__ == "__main__":
    main()
