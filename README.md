# Nutrient Deskew and OCR (Python)

A Nutrient.io demo that straightens every page of a scanned PDF and makes it searchable with the Nutrient Python SDK, with the OCR settings tuned for batch throughput, and a benchmark to measure it.

![A page scanned with 4.5 degrees of skew, and the same page after auto_deskew and OCR with the recognized words outlined](docs/screenshots/01-before-after.png)

1. **Open.** `Document.open()` loads the scanned PDF. The pages are images without a text layer.
2. **Deskew.** `page.auto_deskew()` measures the skew of each page and rotates the page image back. It returns the angle it applied, 0 when the page is already straight. Pages skewed by more than `skew_tolerance` (15 degrees) are left as they are.
3. **OCR.** `editor.make_searchable()` recognizes the text of the straightened pages and adds an invisible text layer, so the PDF can be searched, selected and indexed.
4. **Save.** `editor.save_as()` writes a new PDF. The original is not modified.

Three OCR settings are tuned for throughput:

| Setting | Value | Effect |
|---|---|---|
| `ocr_settings.favor_accuracy` | `False` | Speed mode: one recognition pass, without the inverted-text pass and the layout refiners |
| `ocr_settings.enable_skew_detection` | `False` | The pages are already straight after `auto_deskew()`, so the recognizer does not measure the skew again |
| `ocr_settings.max_threads` | `NUTRIENT_OCR_THREADS` | Pages OCR'd in parallel inside `make_searchable()` |

`max_threads` and a working `favor_accuracy` need nutrient-sdk 1.0.11 or later. The script stops on an older version rather than run untuned.

## Prerequisites

- Python 3.12 or later
- macOS on Apple Silicon, or Linux x86_64 (the Nutrient Python SDK native runtimes)

## Environment variables

Copy `.env.example` to `.env` and load it in your shell, or export the variables. The license key is only read from the environment, never from code.

| Variable | Purpose | Default |
|---|---|---|
| `NUTRIENT_LICENSE_KEY` | Nutrient Python SDK license key | empty = evaluation mode |
| `NUTRIENT_OCR_THREADS` | Pages OCR'd in parallel by `make_searchable()`. `0` = one thread per CPU core | `2` |
| `NUTRIENT_OCR_LANGUAGES` | OCR languages, combined with `+`, for example `eng+deu` | `eng` |

In evaluation mode the SDK adds a "Nutrient SDK Trial Version" mark to every output page, and each process can run for one hour. Deskew and OCR work fully.

## Build and run

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

```bash
set -a; . ./.env; set +a
```

```bash
python deskew_ocr.py
```

The script reads `samples/skewed-scan.pdf` and writes `outputs/skewed-scan-deskewed-ocr.pdf`. To process your own file, pass its path, and optionally the output path:

```bash
python deskew_ocr.py path/to/scan.pdf path/to/result.pdf
```

## Usage

`deskew_ocr.py` prints the angle applied to each page and the time of each step. On the sample:

```text
Page 1: corrected 3.25 degrees of skew.
Page 2: corrected -1.75 degrees of skew.
Page 3: no skew detected, left unchanged.
Page 4: corrected -4.50 degrees of skew.
Page 5: corrected 1.44 degrees of skew.
Page 6: corrected -2.56 degrees of skew.

Pages         : 6 (5 deskewed)
Deskew        : 0.22 s
OCR           : 2.75 s (4 thread(s))
Total time    : 3.08 s
Time per page : 0.51 s
```

The angles match the skew the sample generator applied (`samples/skew-angles.json`), with the opposite sign, within 0.05 degrees. The OCR engine may print `Error in pixGetInvBackgroundMap` lines for very small image regions; they do not affect the result.

### Benchmark

`benchmark.py` processes the same PDF many times across worker processes and reports the throughput and the time per document and per page:

```bash
python benchmark.py 100 4
```

The arguments are the number of runs (default 100), the number of worker processes (default: CPU cores divided by `NUTRIENT_OCR_THREADS`) and an optional input PDF. Keep workers x `NUTRIENT_OCR_THREADS` at or below the number of CPU cores: oversubscription lowers the total throughput. For a single file, `NUTRIENT_OCR_THREADS=4` (or `0`) gives the shortest time per file.

24 runs of the 6-page sample, 4 workers x 2 OCR threads, evaluation mode, on an Apple M2 Pro laptop:

```text
Batch    | runs OK     : 24/24
         | total pages : 144
         | total time  : 0 min 26.8 s
         | throughput  : 53.7 docs/min, 5.4 pages/s
Document | average     : 4.38 s
Page     | average     : 731 ms
         | effective   : 186 ms (wall clock / total pages, 4 workers)
```

The numbers depend on the CPU, the page size and resolution, and the amount of text per page. Run the benchmark on your own scans.

## Sample

`samples/skewed-scan.pdf` is a fictitious 6-page maintenance agreement. Every company, person and figure in it is invented. Each page was drawn as text, then rotated by a known angle and degraded like a scan (grey paper, noise, dust specks, blur, JPEG compression). To regenerate it:

```bash
pip install -r samples/requirements.txt
```

```bash
python samples/generate_scans.py
```

## Files

| Path | Content |
|---|---|
| `deskew_ocr.py` | Deskew, OCR and save, with the tuned settings |
| `benchmark.py` | Parallel batch benchmark |
| `samples/skewed-scan.pdf` | Sample scan |
| `samples/skew-angles.json` | Skew applied to each page of the sample |
| `samples/generate_scans.py` | Sample generator |
