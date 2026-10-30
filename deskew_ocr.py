"""Straightens every page of a scanned PDF and makes it searchable, with the
Nutrient Python SDK.

1. page.auto_deskew() measures the skew of each page and rotates the page
   image back, page by page.
2. editor.make_searchable() runs OCR on the straightened pages and adds an
   invisible text layer.
3. The result is saved as a new PDF.

Three OCR settings are tuned for batch throughput:

  favor_accuracy = False         Speed mode: a single recognition pass, without
                                 the inverted-text pass and the layout refiners.
  enable_skew_detection = False  The pages are already straight after
                                 auto_deskew, so the recognizer does not need
                                 to measure the skew again.
  max_threads = N                Pages OCR'd in parallel inside make_searchable
                                 (NUTRIENT_OCR_THREADS, default 2). For a single
                                 file use 4, or 0 for one thread per core. For
                                 a batch keep workers x threads at or below the
                                 number of cores (see benchmark.py).

Usage:
    python deskew_ocr.py [input.pdf] [output.pdf]
"""

import os
import sys
import time
from pathlib import Path

from nutrient_sdk import Document, License, NutrientException, PdfEditor

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "samples" / "skewed-scan.pdf"
OUTPUT_DIR = BASE_DIR / "outputs"

OCR_THREADS = int(os.environ.get("NUTRIENT_OCR_THREADS", "2"))
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


def process(input_path: Path, output_path: Path, verbose: bool = True) -> dict:
    """Deskew + OCR + save once. Returns timings and the angle applied to each page."""
    _require_tuning_support()
    t0 = time.perf_counter()
    angles = []

    with Document.open(str(input_path)) as document:
        # Skew detection, shared by the page-level deskew and the OCR pipeline.
        # Pages skewed by more than skew_tolerance degrees are left as they are.
        document.settings.deskew_settings.skew_tolerance = 15.0
        document.settings.deskew_settings.optimistic_skew_detection = False
        document.settings.deskew_settings.skew_binarization_method = "default"

        # Language models the recognizer loads. Combine with "+", e.g. "eng+deu".
        document.settings.ocr_settings.default_languages = OCR_LANGUAGES

        # Throughput tuning (see the module docstring).
        document.settings.ocr_settings.favor_accuracy = False
        document.settings.ocr_settings.enable_skew_detection = False
        document.settings.ocr_settings.max_threads = OCR_THREADS

        page_count = document.page_count
        editor = PdfEditor.edit(document)
        try:
            # 1. Straighten every page before any text is recognized.
            for index, page in enumerate(editor.get_page_collection(), start=1):
                applied = page.auto_deskew()
                angles.append(round(applied, 2))
                if verbose:
                    if applied:
                        print(f"Page {index}: corrected {applied:.2f} degrees of skew.")
                    else:
                        print(f"Page {index}: no skew detected, left unchanged.")
            t_deskew = time.perf_counter() - t0

            # 2. OCR the straightened document and write the invisible text layer.
            editor.make_searchable()
            t_ocr = time.perf_counter() - t0 - t_deskew

            editor.save_as(str(output_path))
        finally:
            editor.close()

    elapsed = time.perf_counter() - t0
    return {"seconds": elapsed, "deskew_seconds": t_deskew, "ocr_seconds": t_ocr, "pages": page_count,
            "deskewed": sum(1 for a in angles if a), "angles": angles}


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"{input_path.stem}-deskewed-ocr.pdf"

    register_license()
    try:
        stats = process(input_path, output_path)
    except NutrientException as e:
        sys.exit(f"Error: {e}")

    print()
    print(f"Output        : {output_path}")
    print(f"Pages         : {stats['pages']} ({stats['deskewed']} deskewed)")
    print(f"Deskew        : {stats['deskew_seconds']:.2f} s")
    print(f"OCR           : {stats['ocr_seconds']:.2f} s ({OCR_THREADS} thread(s))")
    print(f"Total time    : {stats['seconds']:.2f} s")
    print(f"Time per page : {stats['seconds'] / stats['pages']:.2f} s")


if __name__ == "__main__":
    main()
