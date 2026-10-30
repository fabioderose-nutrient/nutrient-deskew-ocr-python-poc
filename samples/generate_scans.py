"""Generates samples/skewed-scan.pdf, a fictitious 6-page scanned contract.

Each page is drawn as text on paper, then turned into a scan: rotated by a
known angle (as a sheet fed crooked into a scanner), with grey paper, speckle
noise, a little blur and JPEG compression. The pages carry no text layer.
Every company, person and figure in the document is invented.

    pip install -r samples/requirements.txt
    python samples/generate_scans.py
"""

import io
import json
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
DPI = 200
W, H = int(8.27 * DPI), int(11.69 * DPI)  # A4
# Skew of each page in degrees, counter-clockwise. 0 = fed straight.
ANGLES = [-3.2, 1.8, 0.0, 4.5, -1.4, 2.6]

FONTS = {
    "regular": ["/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "C:/Windows/Fonts/times.ttf"],
    "bold": ["/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "C:/Windows/Fonts/timesbd.ttf"],
}


def font(kind, size):
    for path in FONTS[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


PAGES = [
    ("FACILITIES MAINTENANCE AGREEMENT", [
        "This Facilities Maintenance Agreement (the Agreement) is made on 3 March 2026 between Ravenglass "
        "Property Services Ltd, of 14 Orchard Street, Northbridge NB2 5JD (the Contractor), and Tidewell "
        "Logistics Ltd, of Unit 9, Harbour Park, Eastwick EW4 7QA (the Client).",
        "1. Services. The Contractor shall provide planned and reactive maintenance of the building services "
        "at the Client's distribution centre at Harbour Park, as described in Schedule 1, including heating, "
        "ventilation, lighting, fire alarm and access control systems.",
        "2. Term. The Agreement starts on 1 April 2026 and continues for three years, unless terminated "
        "earlier under clause 11. The Client may extend the term by one further year by giving written "
        "notice at least three months before the end of the initial term.",
        "3. Standards. The Contractor shall perform the Services with reasonable skill and care, in "
        "accordance with good industry practice, the manufacturers' instructions and all applicable laws.",
    ]),
    ("4. RESPONSE TIMES", [
        "The Contractor shall attend reactive maintenance requests within the response times below, measured "
        "from the time the request is logged on the helpdesk.",
        "TABLE",
        "If the Contractor fails to meet a response time more than three times in a calendar month, the "
        "Client may deduct five per cent of the monthly charge for that month as a service credit.",
        "5. Reporting. The Contractor shall send the Client a monthly report listing the requests received, "
        "the response and completion times, the planned tasks completed and any recommended remedial work.",
    ]),
    ("6. CHARGES AND PAYMENT", [
        "The Client shall pay the Contractor a fixed charge of 7,450 pounds per month, exclusive of VAT, for "
        "the planned maintenance and for reactive attendance during normal working hours.",
        "Reactive work outside normal working hours is charged at 68 pounds per hour, with a minimum charge "
        "of two hours. Materials are charged at cost plus ten per cent.",
        "The Contractor shall invoice monthly in arrears. The Client shall pay each undisputed invoice "
        "within thirty days of receipt.",
        "7. Price review. The fixed charge is reviewed on each anniversary of the start date by reference to "
        "the change in the consumer prices index over the previous twelve months.",
    ]),
    ("8. PERSONNEL", [
        "The Contractor shall appoint a contract manager who will be the Client's main point of contact. The "
        "Contractor shall ensure that all engineers are competent, trained and hold the qualifications "
        "required for the systems they work on.",
        "The Contractor's personnel shall comply with the Client's site rules, including the rules on "
        "vehicle movements in the yard, high-visibility clothing and the signing-in procedure.",
        "9. Health and safety. The Contractor shall provide risk assessments and method statements for "
        "all planned tasks and shall obtain a permit to work before any work on live electrical systems, "
        "at height above two metres, or involving hot works.",
    ]),
    ("10. INSURANCE AND LIABILITY", [
        "The Contractor shall maintain public liability insurance of not less than ten million pounds and "
        "employer's liability insurance of not less than five million pounds for each claim.",
        "The total liability of either party under this Agreement in any contract year is limited to one "
        "hundred and fifty per cent of the charges paid in that year, except for death or personal injury "
        "caused by negligence, or fraud.",
        "11. Termination. Either party may terminate this Agreement by giving the other at least six months' "
        "written notice. Either party may terminate this Agreement immediately if the other commits a "
        "material breach which is not remedied within thirty days of a written notice.",
    ]),
    ("12. GENERAL", [
        "Notices under this Agreement shall be in writing and sent to the addresses given above. This "
        "Agreement is governed by the law of England and Wales.",
        "Signed for and on behalf of Ravenglass Property Services Ltd",
        "Name: Helen Dacre        Position: Operations Director        Date: 3 March 2026",
        "Signed for and on behalf of Tidewell Logistics Ltd",
        "Name: Marcus Ebbing        Position: Head of Facilities        Date: 3 March 2026",
    ]),
]

RESPONSE_TABLE = [("Priority", "Example", "Attend within"), ("1 - Emergency", "Fire alarm fault, loss of power", "2 hours"),
                  ("2 - Urgent", "Heating failure in winter", "4 hours"), ("3 - Routine", "Faulty light fitting", "2 working days"),
                  ("4 - Planned", "Minor repairs, adjustments", "10 working days")]


def draw_page(number, title, paragraphs):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    body, bold = font("regular", 40), font("bold", 44)
    x, y = 190, 230
    d.text((x, y), title, font=bold, fill=0)
    y += 110
    for para in paragraphs:
        if para == "TABLE":
            cols = [x, x + 330, x + 950, W - 190]
            for r, row in enumerate(RESPONSE_TABLE):
                for c, cell in enumerate(row):
                    d.text((cols[c] + 14, y + 12), cell, font=bold if r == 0 else body, fill=0)
                d.line((x, y, W - 190, y), fill=0, width=3)
                y += 70
            d.line((x, y, W - 190, y), fill=0, width=3)
            for cx in cols:
                d.line((cx, y - 70 * len(RESPONSE_TABLE), cx, y), fill=0, width=3)
            y += 50
            continue
        for line in textwrap.wrap(para, 64):
            d.text((x, y), line, font=body, fill=0)
            y += 58
        y += 34
    d.text((W // 2, H - 170), f"Page {number} of {len(PAGES)}", font=font("regular", 32), fill=0, anchor="ma")
    return img


def scan(img, angle, seed):
    """Feeds the page crooked into a scanner: rotation, grey paper, noise."""
    rng = np.random.default_rng(seed)
    rotated = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
    a = np.asarray(rotated).astype(np.float32)
    a = a * 0.86 + 255 * 0.08                  # ink not quite black, paper not quite white
    a += rng.normal(0, 6, a.shape)              # sensor noise
    specks = rng.random(a.shape) < 0.0006       # dust specks
    a[specks] = rng.uniform(40, 120, specks.sum())
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=55)
    return Image.open(io.BytesIO(buf.getvalue()))


def main():
    pages = [scan(draw_page(i + 1, t, p), ANGLES[i], i) for i, (t, p) in enumerate(PAGES)]
    out = HERE / "skewed-scan.pdf"
    pages[0].save(out, "PDF", resolution=DPI, save_all=True, append_images=pages[1:])
    (HERE / "skew-angles.json").write_text(json.dumps(
        {"file": out.name, "applied_skew_degrees": ANGLES,
         "note": "Positive = rotated counter-clockwise when the page was scanned."}, indent=2) + "\n")
    print(f"{out.name}: {len(pages)} pages, {out.stat().st_size // 1024} KB, skew {ANGLES}")


if __name__ == "__main__":
    main()
