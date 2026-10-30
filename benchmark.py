"""Benchmark: processes the same PDF N times (default 100) across worker
processes and reports per-batch, per-document and per-page statistics.

Each worker registers the license once (when NUTRIENT_LICENSE_KEY is set) and
calls process() from deskew_ocr.py. Keep workers x NUTRIENT_OCR_THREADS at or
below the number of CPU cores: oversubscription lowers the total throughput.

Usage:
    python benchmark.py [runs] [workers] [input.pdf]
"""

import os
import statistics
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Not imported from deskew_ocr: the parent process must not load the native
# SDK, only the workers do.
DEFAULT_INPUT = Path(__file__).resolve().parent / "samples" / "skewed-scan.pdf"
OCR_THREADS = int(os.environ.get("NUTRIENT_OCR_THREADS", "2"))


def _init_worker() -> None:
    from deskew_ocr import register_license

    register_license()


def _run_once(run_index: int, input_path: str, out_dir: str) -> tuple[int, float, int, int, str | None]:
    from nutrient_sdk import NutrientException

    from deskew_ocr import process

    out = Path(out_dir) / f"run_{run_index:04}.pdf"
    try:
        stats = process(Path(input_path), out, verbose=False)
        return run_index, stats["seconds"], stats["pages"], stats["deskewed"], None
    except (NutrientException, Exception) as e:
        return run_index, 0.0, 0, 0, f"{type(e).__name__}: {e}"
    finally:
        out.unlink(missing_ok=True)


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else max(1, (os.cpu_count() or 2) // max(1, OCR_THREADS))
    input_path = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_INPUT

    print(f"Benchmark: {runs} runs of {input_path.name} | {workers} workers x {OCR_THREADS} OCR thread(s)")

    durations: list[float] = []
    total_pages = 0
    failures: list[tuple[int, str]] = []
    t0 = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="deskew-ocr-bench-") as out_dir, \
            ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as pool:
        futures = [pool.submit(_run_once, i, str(input_path), out_dir) for i in range(1, runs + 1)]
        for done, fut in enumerate(as_completed(futures), start=1):
            idx, seconds, pages, deskewed, err = fut.result()
            if err:
                failures.append((idx, err))
                print(f"[{done:>4}/{runs}] FAIL run {idx}: {err}")
            else:
                durations.append(seconds)
                total_pages += pages
                elapsed = time.perf_counter() - t0
                eta = elapsed / done * (runs - done)
                print(f"[{done:>4}/{runs}] OK run {idx} ({pages} pages, {deskewed} deskewed, {seconds:.1f}s, "
                      f"ETA {eta / 60:.0f} min)")

    elapsed = time.perf_counter() - t0
    minutes, seconds = divmod(elapsed, 60)

    print()
    print("=" * 62)
    print(f"Batch    | runs OK     : {len(durations)}/{runs}")
    if failures:
        print(f"         | failed      : {len(failures)}")
        for idx, err in failures[:10]:
            print(f"         |   run {idx}: {err}")
    print(f"         | total pages : {total_pages}")
    print(f"         | total time  : {int(minutes)} min {seconds:.1f} s")
    if durations:
        pages_per_doc = total_pages // len(durations)
        print(f"         | throughput  : {len(durations) / elapsed * 60:.1f} docs/min, "
              f"{total_pages / elapsed:.1f} pages/s")
        print(f"Document | average     : {statistics.mean(durations):.2f} s")
        print(f"         | median      : {statistics.median(durations):.2f} s")
        print(f"         | min / max   : {min(durations):.2f} s / {max(durations):.2f} s")
        print(f"         | stdev       : {statistics.pstdev(durations):.2f} s")
        print(f"Page     | average     : {statistics.mean(durations) / pages_per_doc * 1000:.0f} ms")
        print(f"         | effective   : {elapsed / total_pages * 1000:.0f} ms "
              f"(wall clock / total pages, {workers} workers)")
    print("=" * 62)


if __name__ == "__main__":
    main()
