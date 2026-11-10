"""Latency benchmark: the time to deskew and OCR ONE document, for several
ways of spreading it over the CPU cores, and the number of cores really used.

Each configuration is WORKERSxTHREADS:
  1x1   one process, one OCR thread (the SDK default)
  1x0   one process, one OCR thread per CPU core (max_threads = 0)
  1x4   one process, four OCR threads
  2x2   split mode: two worker processes, two OCR threads each

"cores used" is CPU time / wall time. A value close to 1 while THREADS > 1
means the pages are not OCR'd in parallel: check that the code calls the
document-level editor.make_searchable(), and how many CPUs the container gets.

Usage:
    python latency.py [input.pdf] [--runs 3] [--config 1x1 --config 1x0 ...]
"""

import argparse
import os
import platform
import statistics
import tempfile
from pathlib import Path

from deskew_ocr import DEFAULT_INPUT, OCR_LANGUAGES, cpu_seconds, process, process_split, register_license


def run(input_path: Path, output_path: Path, workers: int, threads: int) -> tuple[float, float, int]:
    cpu0 = cpu_seconds()
    if workers > 1:
        stats = process_split(input_path, output_path, workers, threads)
    else:
        stats = process(input_path, output_path, verbose=False, threads=threads)
    return stats["seconds"], (cpu_seconds() - cpu0) / stats["seconds"], stats["pages"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", nargs="?", default=str(DEFAULT_INPUT))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--config", action="append", help="WORKERSxTHREADS, repeatable (default: 1x1 and 1x0)")
    args = parser.parse_args()
    configs = args.config or ["1x1", "1x0"]
    input_path = Path(args.input)
    register_license()

    print(f"{Path(input_path).name} | languages {OCR_LANGUAGES} | {args.runs} run(s) per config | "
          f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs visible")
    print(f"{'config':>7} {'median s':>9} {'min s':>7} {'max s':>7} {'s/page':>7} {'cores used':>11}")
    with tempfile.TemporaryDirectory(prefix="deskew-ocr-latency-") as tmp:
        for config in configs:
            workers, threads = (int(x) for x in config.lower().split("x"))
            results = [run(input_path, Path(tmp) / f"{config}_{i}.pdf", workers, threads) for i in range(args.runs)]
            seconds = [r[0] for r in results]
            median = statistics.median(seconds)
            print(f"{config:>7} {median:>9.1f} {min(seconds):>7.1f} {max(seconds):>7.1f} "
                  f"{median / results[0][2]:>7.2f} {statistics.median(r[1] for r in results):>11.2f}", flush=True)


if __name__ == "__main__":
    main()
