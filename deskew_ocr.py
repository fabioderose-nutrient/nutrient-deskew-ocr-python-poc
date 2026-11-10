"""Straightens every page of a scanned PDF and makes it searchable, with the
Nutrient Python SDK, tuned for the time of a single document.

1. page.auto_deskew() measures the skew of each page and rotates the page
   image back, page by page.
2. editor.make_searchable() runs OCR on the straightened pages and adds an
   invisible text layer.
3. The result is saved as a new PDF.

Three OCR settings are tuned for speed:

  favor_accuracy = False         Speed mode: a single recognition pass, without
                                 the inverted-text pass and the layout refiners.
  enable_skew_detection = False  The pages are already straight after
                                 auto_deskew, so the recognizer does not need
                                 to measure the skew again.
  max_threads = N                Pages OCR'd in parallel inside make_searchable
                                 (NUTRIENT_OCR_THREADS, default 0 = one thread
                                 per CPU core). Only the document-level
                                 editor.make_searchable() uses it: calling
                                 page.make_searchable() page by page runs on
                                 one core whatever the value.

Split mode (NUTRIENT_OCR_WORKERS > 1) cuts the document into page ranges,
deskews and OCRs each range in its own process and merges the results in page
order. On one machine it gives the same time as max_threads; its use is to
spread one document over several machines or serverless invocations.

Usage:
    python deskew_ocr.py [input.pdf] [output.pdf]
"""

import multiprocessing
import os
import resource
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from nutrient_sdk import Document, License, NutrientException, PdfEditor

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "samples" / "skewed-scan.pdf"
OUTPUT_DIR = BASE_DIR / "outputs"

OCR_THREADS = int(os.environ.get("NUTRIENT_OCR_THREADS", "0"))
OCR_WORKERS = int(os.environ.get("NUTRIENT_OCR_WORKERS", "1"))
OCR_LANGUAGES = os.environ.get("NUTRIENT_OCR_LANGUAGES", "eng")


def register_license() -> None:
    """Registers the license key when one is set. Without it the SDK runs in
    evaluation mode."""
    key = os.environ.get("NUTRIENT_LICENSE_KEY", "").strip()
    if key:
        License.register_key(key)


def _require_tuning_support() -> None:
    """Refuses to run on SDK versions that silently ignore the tuned settings.

    On nutrient-sdk 1.0.10.1 and earlier, max_threads is accepted without
    effect and favor_accuracy is ignored by the OCR pipeline, so a benchmark
    would measure an untuned run while looking tuned.
    """
    from nutrient_sdk.ocrsettings import OcrSettings

    if not isinstance(getattr(OcrSettings, "max_threads", None), property):
        sys.exit("This nutrient-sdk version does not support ocr_settings.max_threads. "
                 "Install the version pinned in requirements.txt.")


def cpu_seconds() -> float:
    """CPU time used by this process and its finished worker processes."""
    own = resource.getrusage(resource.RUSAGE_SELF)
    workers = resource.getrusage(resource.RUSAGE_CHILDREN)
    return own.ru_utime + own.ru_stime + workers.ru_utime + workers.ru_stime


def process(input_path: Path, output_path: Path, verbose: bool = True, threads: int | None = None,
            first_page: int = 0, end_page: int | None = None) -> dict:
    """Deskew + OCR + save once, for the whole document or the pages
    [first_page, end_page). Returns timings and the angle applied to each page."""
    _require_tuning_support()
    threads = OCR_THREADS if threads is None else threads
    t0 = time.perf_counter()
    angles = []

    with Document.open(str(input_path)) as document:
        # Skew detection, shared by the page-level deskew and the OCR pipeline.
        # Pages skewed by more than skew_tolerance degrees are left as they are.
        document.settings.deskew_settings.skew_tolerance = 15.0
        document.settings.deskew_settings.optimistic_skew_detection = False
        document.settings.deskew_settings.skew_binarization_method = "default"

        # Language models the recognizer loads. Combine with "+", e.g. "dan+eng".
        # Set them explicitly: make_searchable reads the default "auto" as English.
        document.settings.ocr_settings.default_languages = OCR_LANGUAGES

        # Speed tuning (see the module docstring).
        document.settings.ocr_settings.favor_accuracy = False
        document.settings.ocr_settings.enable_skew_detection = False
        document.settings.ocr_settings.max_threads = threads

        editor = PdfEditor.edit(document)
        try:
            # 0. Keep only the requested page range (split mode).
            pages = editor.get_page_collection()
            end_page = pages.count if end_page is None else end_page
            for index in range(pages.count - 1, end_page - 1, -1):
                pages.remove_at(index)
            for _ in range(first_page):
                pages.remove_at(0)
            page_count = pages.count

            # 1. Straighten every page before any text is recognized.
            for index, page in enumerate(pages, start=first_page + 1):
                applied = page.auto_deskew()
                angles.append(round(applied, 2))
                if verbose:
                    if applied:
                        print(f"Page {index}: corrected {applied:.2f} degrees of skew.")
                    else:
                        print(f"Page {index}: no skew detected, left unchanged.")
            t_deskew = time.perf_counter() - t0

            # 2. OCR the straightened document and write the invisible text layer.
            #    Document level, so that max_threads pages are OCR'd in parallel.
            editor.make_searchable()
            t_ocr = time.perf_counter() - t0 - t_deskew

            editor.save_as(str(output_path))
        finally:
            editor.close()

    elapsed = time.perf_counter() - t0
    return {"seconds": elapsed, "deskew_seconds": t_deskew, "ocr_seconds": t_ocr, "pages": page_count,
            "deskewed": sum(1 for a in angles if a), "angles": angles}


def _process_range(args: tuple) -> dict:
    register_license()
    input_path, output_path, threads, first_page, end_page = args
    return process(Path(input_path), Path(output_path), verbose=False, threads=threads,
                   first_page=first_page, end_page=end_page)


def page_ranges(page_count: int, parts: int) -> list[tuple[int, int]]:
    """Splits [0, page_count) into `parts` consecutive ranges of near-equal size."""
    size, extra = divmod(page_count, parts)
    ranges, start = [], 0
    for part in range(min(parts, page_count)):
        end = start + size + (1 if part < extra else 0)
        ranges.append((start, end))
        start = end
    return ranges


def merge(parts: list[Path], output_path: Path) -> None:
    """Appends the OCR'd parts, in order, into one PDF."""
    with Document.open(str(parts[0])) as first:
        editor = PdfEditor.edit(first)
        try:
            for part in parts[1:]:
                with Document.open(str(part)) as document:
                    editor.append_document(document)
            editor.save_as(str(output_path))
        finally:
            editor.close()


def process_split(input_path: Path, output_path: Path, workers: int, threads: int | None = None) -> dict:
    """Deskews and OCRs page ranges in `workers` processes, then merges them."""
    t0 = time.perf_counter()
    with Document.open(str(input_path)) as document:
        page_count = document.page_count
    # Default: share the CPU cores between the workers.
    threads = threads if threads is not None else (OCR_THREADS or max(1, (os.cpu_count() or 1) // workers))

    with tempfile.TemporaryDirectory(prefix="deskew-ocr-split-") as tmp:
        ranges = page_ranges(page_count, workers)
        parts = [Path(tmp) / f"part_{i:03}.pdf" for i in range(len(ranges))]
        jobs = [(str(input_path), str(part), threads, first, end) for part, (first, end) in zip(parts, ranges)]
        # "spawn" on every OS: forking a process that has loaded the native SDK
        # (the Linux default) can hang the workers.
        with ProcessPoolExecutor(max_workers=len(jobs), mp_context=multiprocessing.get_context("spawn")) as pool:
            results = list(pool.map(_process_range, jobs))
        t_merge = time.perf_counter()
        merge(parts, output_path)
        t_merge = time.perf_counter() - t_merge

    angles = [a for r in results for a in r["angles"]]
    return {"seconds": time.perf_counter() - t0, "merge_seconds": t_merge, "pages": page_count,
            "deskewed": sum(1 for a in angles if a), "angles": angles, "workers": len(jobs), "threads": threads}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"{input_path.stem}-deskewed-ocr.pdf"

    register_license()
    cpu0 = cpu_seconds()
    try:
        if OCR_WORKERS > 1:
            stats = process_split(input_path, output_path, OCR_WORKERS)
        else:
            stats = process(input_path, output_path)
    except NutrientException as e:
        sys.exit(f"Error: {e}")
    cores = (cpu_seconds() - cpu0) / stats["seconds"]

    print()
    print(f"Output        : {output_path}")
    print(f"Pages         : {stats['pages']} ({stats['deskewed']} deskewed)")
    if OCR_WORKERS > 1:
        print(f"Split         : {stats['workers']} workers x {stats['threads'] or 'all'} OCR thread(s), "
              f"merge {stats['merge_seconds']:.2f} s")
    else:
        print(f"Deskew        : {stats['deskew_seconds']:.2f} s")
        threads = f"{OCR_THREADS} thread(s)" if OCR_THREADS else "one thread per core"
        print(f"OCR           : {stats['ocr_seconds']:.2f} s ({threads})")
    print(f"Total time    : {stats['seconds']:.2f} s")
    print(f"Time per page : {stats['seconds'] / stats['pages']:.2f} s")
    print(f"CPU cores used: {cores:.2f} on average")


if __name__ == "__main__":
    main()
