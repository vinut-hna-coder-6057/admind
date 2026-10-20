"""Loopback-only HTTP smoke/load check; reports latency and status counts."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import http.client
import json
import math
import threading
import time
from urllib.parse import urlsplit


def _percentile(samples, percentile):
    if not samples:
        return None
    ordered = sorted(samples)
    return round(ordered[max(0, math.ceil(percentile * len(ordered)) - 1)], 2)


def run_load_test(base_url, requests, concurrency, mode, pid=None):
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
        raise ValueError("load checks may only target loopback hosts")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("load-test base URL must not include a path, query, or fragment")
    if requests < 1 or concurrency < 1:
        raise ValueError("requests and concurrency must be positive")
    if mode == "rate-limit" and requests > 30:
        raise ValueError("rate-limit profile is capped at 30 calls")

    def call(index):
        if mode == "mixed" and index % 4 == 0:
            path, payload = "/livez", None
        elif mode == "mixed" and index % 4 == 1:
            path, payload = "/readyz", None
        elif mode == "mixed" and index % 4 == 2:
            path, payload = "/recommend-ad", {"title": "", "mode": "study"}
        else:
            path, payload = "/recommend-ad", {
                "title": "A video about Python programming and data analysis",
                "mode": "study", "user_type": "developer",
            }
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        started = time.perf_counter()
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=120)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            connection.request("GET" if body is None else "POST", path, body=body, headers=headers)
            response = connection.getresponse()
            response.read(4096)
            status = response.status
        except (http.client.HTTPException, TimeoutError, OSError) as exc:
            return {"status": "error", "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "error": type(exc).__name__}
        finally:
            connection.close()
        return {"status": str(status), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}

    server_usage = {"peak_server_rss_mb": "not_measured", "peak_server_cpu_percent": "not_measured"}
    stop_sampling = threading.Event()
    sampler = None
    if pid is not None:
        try:
            import psutil
            process = psutil.Process(pid)
            server_usage = {"peak_server_rss_mb": 0.0, "peak_server_cpu_percent": 0.0}
            def sample_process():
                process.cpu_percent(interval=None)
                while not stop_sampling.is_set():
                    try:
                        server_usage["peak_server_rss_mb"] = max(server_usage["peak_server_rss_mb"], round(process.memory_info().rss / (1024 * 1024), 1))
                        server_usage["peak_server_cpu_percent"] = max(server_usage["peak_server_cpu_percent"], process.cpu_percent(interval=None))
                    except Exception:
                        break
                    stop_sampling.wait(.1)
            sampler = threading.Thread(target=sample_process, daemon=True)
            sampler.start()
        except ImportError:
            server_usage = {"peak_server_rss_mb": "psutil_not_installed", "peak_server_cpu_percent": "psutil_not_installed"}
        except Exception:
            server_usage = {"peak_server_rss_mb": "pid_unavailable", "peak_server_cpu_percent": "pid_unavailable"}
    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(call, index) for index in range(requests)]
        for future in as_completed(futures):
            results.append(future.result())
    stop_sampling.set()
    if sampler:
        sampler.join(timeout=1)
    elapsed = time.perf_counter() - started
    latencies = [row["elapsed_ms"] for row in results]
    counts = Counter(row["status"] for row in results)
    return {
        "base_url": base_url,
        "mode": mode,
        "requests": requests,
        "concurrency": concurrency,
        "duration_seconds": round(elapsed, 3),
        "throughput_rps": round(requests / elapsed, 2) if elapsed else None,
        "status_counts": dict(counts),
        "error_count": counts.get("error", 0),
        "latency_ms": {"p50": _percentile(latencies, .50), "p95": _percentile(latencies, .95), "p99": _percentile(latencies, .99)},
        **server_usage,
        "note": "Rate limiting and model cache state affect results; use only against a local test instance.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--requests", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--mode", choices=("valid", "mixed", "rate-limit"), default="valid")
    parser.add_argument("--pid", type=int, help="optional local API process ID for psutil resource sampling")
    args = parser.parse_args()
    result = run_load_test(f"http://{args.host}:{args.port}", args.requests, args.concurrency, args.mode, args.pid)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
