# Benchmark: old vs new version

Time to deskew and OCR one 68-page scanned document (`samples/skewed-scan-68p.pdf`, written by `python samples/generate_scans.py --pages 68`), with the old version of `deskew_ocr.py` (first commit) and the new one, on the same machines, Nutrient Python SDK 1.0.13, evaluation mode. Each run is a fresh process. "CPU cores used" is CPU time / wall time.

| Version | OCR threads (`max_threads`) | Pages per worker |
|---|---|---|
| Old, SDK default | 1 | all |
| Old, its default | 2 | all |
| New, its default | 0 = one per CPU core | all |
| New, split mode (`NUTRIENT_OCR_WORKERS`) | cores / workers | one page range per worker process |

## Apple M2 Pro laptop, 12 cores (8 performance + 4 efficiency), 32 GB RAM, macOS

| Configuration | Time (s) | s/page | CPU cores used | vs old default |
|---|---|---|---|---|
| Old, max_threads 1 | 57.6 | 0.85 | 1.10 | 0.54x |
| Old, default (max_threads 2) | 31.2 | 0.46 | 2.05 | 1.00x |
| New, default (one thread per core) | 14.2 | 0.21 | 5.09 | **2.20x faster** |
| New, split mode, 4 workers x 3 threads | 11.1 | 0.16 | 6.56 | **2.80x faster** |

## Linux container limited to 2 CPUs (Docker `--cpus=2`, Debian 13, ARM64 on the same laptop)

| Configuration | Time (s) | s/page | CPU cores used | vs old default |
|---|---|---|---|---|
| Old, max_threads 1 | 91.1 | 1.34 | 0.94 | 0.57x |
| Old, default (max_threads 2) | 51.7 | 0.76 | 1.69 | 1.00x |
| New, default (one thread per core) | 47.4 | 0.70 | 1.81 | 1.09x faster |
| New, split mode, 2 workers x 1 thread | 44.9 | 0.66 | 1.77 | 1.15x faster |

## What the numbers say

- With one OCR thread, the document uses one core, whatever the machine.
- The old default (2 threads) can never use more than 2 cores. The new default uses every core the machine or container gives it.
- In a container limited to 2 CPUs, old default and new default are close: both already use the 2 CPUs. To go faster there, give the container more vCPUs, or split the document across several containers or serverless invocations (split mode).
- On one machine, split mode helps when there are many cores, because the deskew step also runs in parallel. On 2 CPUs the gain is small, and on another 68-page document of smaller, 150 DPI pages it was slower than one process (the extra processes cost more than they save). Its main use is to spread one document over several machines.
- A fresh container downloads the OCR models before its first document. The `Dockerfile` downloads them at build time: on the 6-page sample in 2 CPUs, 7.1 s on 1.0 core without it, 3.9 s on 1.9 cores with it.
- The old and new versions write the same text layer: only the way the pages are spread over the cores changed.
