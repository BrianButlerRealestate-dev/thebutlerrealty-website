"""
Builds the downloadable market report PDF (the free report offered by the lead
popup and the Resources page) from the newest published Market Update hand-off
file in content-queue-articles/.

    python automation/build_market_report_pdf.py            # newest market update
    python automation/build_market_report_pdf.py <file.md>  # a specific hand-off

Output: downloads/san_tan_valley_florence_market_report.pdf (always the same
filename, so every link on the site keeps working and just serves the newest
month).

Why this exists: the PDF used to be a hand-edited template that quietly went
stale. Now the numbers, recap and Brian's Take come straight from the same
hand-off file that publishes the monthly /market-updates page, so the PDF can't
drift from what's already on the site. poll_and_publish_website.py calls
build() right after a Market Update publishes (see refresh_market_report there).

No third-party dependencies: the PDF is printed from HTML by Microsoft Edge in
headless mode, which ships with Windows 11 (Chrome works as a fallback).

Rules this keeps (see CLAUDE.md): no "The Butler Realty" wordmark; identity is
"Brian Butler | eXp Realty | License SA701819000"; no franchise language; no
invented figures -- every number is copied from the hand-off, and the build
refuses to produce a PDF if the hand-off is incomplete.
"""

import html
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_QUEUE = PROJECT_ROOT / "content-queue-articles"
OUTPUT_PDF = PROJECT_ROOT / "downloads" / "san_tan_valley_florence_market_report.pdf"
IMAGES = PROJECT_ROOT / "images"

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# Label may carry a parenthetical instruction, e.g. "RESTATEMENT NOTE (display as ...):"
FIELD_RE = re.compile(r"^([A-Z][A-Z /'&-]+?)(?: \([^)]*\))?:[ \t]*(.*)$")
SECTION_NAMES = {
    "METRICS TABLE", "RESTATEMENT NOTE", "RECAP PARAGRAPH", "BRIAN'S TAKE",
}


class ReportError(Exception):
    pass


# ----------------------------------------------------------------- parsing

def parse_handoff(path):
    """Parse a `CONTENT TYPE: Market Update` hand-off into a dict of fields.

    Single-line fields (MONTH/YEAR, SOURCE, ...) hold their value; multi-line
    sections (METRICS TABLE, RECAP PARAGRAPH, BRIAN'S TAKE, RESTATEMENT NOTE)
    hold everything up to the next ALL-CAPS field label."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    fields, current = {}, None
    for line in text.split("\n"):
        m = FIELD_RE.match(line)
        if m and (m.group(1) in SECTION_NAMES or m.group(1) in (
                "CONTENT TYPE", "MONTH/YEAR", "AREA", "DATA PERIOD", "COMPARED TO",
                "SOURCE", "PUBLISH DATE", "PROPOSED SLUG", "HEADLINE")):
            current = m.group(1)
            fields[current] = [m.group(2)] if m.group(2) else []
        elif current is not None:
            fields[current].append(line)
    return {k: "\n".join(v).strip() for k, v in fields.items()}


def newest_market_update(queue=CONTENT_QUEUE):
    """Newest Market Update hand-off by its PUBLISH DATE."""
    best = None
    for p in queue.glob("*.md"):
        try:
            head = p.read_text(encoding="utf-8")[:300]
        except OSError:
            continue
        if not re.search(r"^CONTENT TYPE:\s*Market Update\s*$", head, re.M):
            continue
        f = parse_handoff(p)
        key = f.get("PUBLISH DATE", "")
        if best is None or key > best[0]:
            best = (key, p)
    if best is None:
        raise ReportError("No Market Update hand-off files found in content-queue-articles/")
    return best[1]


def parse_metrics(table_text):
    rows = []
    for line in table_text.split("\n"):
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3:
            rows.append(cells[:3])
    if len(rows) < 2:
        raise ReportError("METRICS TABLE has no data rows")
    return rows[0], rows[1:]  # header, body


# ----------------------------------------------------------------- rendering

def esc(s):
    return html.escape(s, quote=True)


def paragraphs(text):
    return "".join(f"<p>{esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", text) if p.strip())


def img_url(name):
    return (IMAGES / name).as_uri()


GLOSSARY = [
    ("Sold Listings", "Homes that closed during the month. A rise or fall here shows how many buyers actually completed purchases."),
    ("New Listings", "Homes newly put on the market during the month. More new listings means more choices for buyers."),
    ("Active Listings", "Homes currently for sale. Low inventory means more competition among buyers; high inventory means more choices and room to negotiate."),
    ("Under Contract", "Homes with an accepted offer that haven't closed yet. It's a look at where sales are heading in the weeks ahead."),
    ("Avg. Days on Market", "How long homes sit before going under contract. Under 30 days is generally considered fast; over 60 days gives buyers more room."),
    ("Months of Supply", "How long current inventory would last at the recent sales pace. Under 3 months generally favors sellers, over 6 favors buyers, and 3\u20136 is considered balanced."),
    ("Sold-to-List Ratio", "The share of asking price homes actually sell for. Above 100% means homes are selling over asking; below 98% generally means more negotiating room."),
]


def render_html(f):
    for needed in ("MONTH/YEAR", "AREA", "SOURCE", "METRICS TABLE", "RECAP PARAGRAPH", "PUBLISH DATE"):
        if not f.get(needed):
            raise ReportError(f"Hand-off is missing {needed} -- not building a PDF from incomplete data")
    header, rows = parse_metrics(f["METRICS TABLE"])
    month_year = f["MONTH/YEAR"]
    area = f["AREA"]

    pub = f["PUBLISH DATE"]
    try:
        y, m, d = (int(x) for x in pub.split("-"))
        pub_long = date(y, m, d).strftime("%B ") + str(d) + f", {y}"
    except ValueError:
        pub_long = pub

    body_rows = "".join(
        f"<tr><td class='m'>{esc(a)}</td><td class='v'>{esc(b)}</td><td>{esc(c)}</td></tr>"
        for a, b, c in rows
    )
    restatement = (
        f"<p class='note'>{esc(f['RESTATEMENT NOTE'])}</p>" if f.get("RESTATEMENT NOTE") else ""
    )
    take = ""
    take_text = f.get("BRIAN'S TAKE", "")
    if take_text:
        take = (
            "<div class='take'><div class='label'>Brian\u2019s Take</div>"
            f"{paragraphs(take_text)}</div>"
        )
    glossary = "".join(
        f"<div class='g'><b>{esc(t)}</b><span>{esc(d)}</span></div>" for t, d in GLOSSARY
    )
    compared = f" Changes are measured against {esc(f['COMPARED TO'])}." if f.get("COMPARED TO") else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{esc(month_year)} Market Report: {esc(area)}</title>
<style>
  @page {{ size: Letter; margin: 0.45in 0.6in 0.45in 0.6in; }}
  :root {{ --primary:#1B4F72; --accent:#2E86C1; --light:#EBF5FB; --gray:#555566; --dark:#1a1a2e; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:'Segoe UI','DM Sans',Arial,sans-serif; color:#2d2d3a; font-size:10pt; line-height:1.45; margin:0; }}
  h1,h2,.serif {{ font-family:Georgia,'Playfair Display',serif; color:var(--primary); }}
  .band {{ background:var(--primary); color:#fff; border-radius:10px; padding:16px 24px; display:flex; align-items:center; gap:18px; }}
  .band img {{ width:54px; height:54px; }}
  .band .who {{ font-family:Georgia,serif; font-size:15pt; font-weight:700; letter-spacing:.02em; }}
  .band .sub {{ font-size:9pt; opacity:.85; }}
  h1 {{ font-size:23pt; line-height:1.15; margin:14px 0 4px; }}
  .kicker {{ color:var(--accent); font-weight:700; letter-spacing:.12em; text-transform:uppercase; font-size:8.5pt; }}
  .dateline {{ color:var(--gray); font-size:9.5pt; margin-bottom:14px; }}
  h2 {{ font-size:13.5pt; margin:16px 0 6px; }}
  table {{ width:100%; border-collapse:collapse; margin:6px 0 4px; font-size:10pt; }}
  th {{ background:var(--primary); color:#fff; text-align:left; padding:8px 10px; font-weight:600; }}
  td {{ padding:6px 10px; border-bottom:1px solid #dfe6ec; vertical-align:top; }}
  tr:nth-child(even) td {{ background:#f6fafc; }}
  td.m {{ font-weight:600; width:34%; }} td.v {{ font-weight:700; color:var(--primary); width:20%; }}
  p {{ margin:0 0 8px; }}
  p.note {{ font-size:9pt; color:var(--gray); font-style:italic; margin-top:6px; }}
  .take {{ background:var(--dark); color:#fff; border-radius:10px; padding:16px 20px; margin:16px 0 4px; break-inside:avoid; }}
  .take p {{ color:#eef2f6; }} .take .label {{ color:#8cc6ec; font-weight:700; letter-spacing:.1em; text-transform:uppercase; font-size:8.5pt; margin-bottom:6px; }}
  .g {{ display:flex; gap:12px; padding:4px 0; border-bottom:1px solid #e6edf2; break-inside:avoid; }}
  .g b {{ flex:0 0 125px; color:var(--primary); }} .g span {{ color:#3a3a48; }}
  .cta {{ display:flex; gap:14px; margin-top:6px; }}
  .card {{ flex:1; background:var(--light); border-radius:10px; padding:14px 16px; break-inside:avoid; }}
  .card h3 {{ margin:0 0 4px; font-family:Georgia,serif; color:var(--primary); font-size:12pt; }}
  .contact {{ margin-top:12px; text-align:center; font-weight:600; color:var(--primary); }}
  .fine {{ margin-top:10px; border-top:1px solid #dfe6ec; padding-top:10px; font-size:8pt; color:var(--gray); display:flex; gap:14px; align-items:center; break-inside:avoid; }}
  .fine img.hud {{ height:34px; }} .fine img.exp {{ height:22px; }}
</style></head><body>

<div class="band"><img src="{img_url('butler-icon-white.png')}" alt="">
  <div><div class="who">Brian Butler</div>
  <div class="sub">REALTOR&reg; &nbsp;|&nbsp; eXp Realty &nbsp;|&nbsp; License # SA701819000</div></div></div>

<div class="kicker" style="margin-top:14px">Free Market Report</div>
<h1>{esc(area)}<br>{esc(month_year)} Market Report</h1>
<div class="dateline">Source: {esc(f['SOURCE'])} &nbsp;&bull;&nbsp; Published {esc(pub_long)} &nbsp;&bull;&nbsp; Updated monthly on thebutlerrealty.com</div>

<h2>The Numbers</h2>
<table><tr><th>{esc(header[0])}</th><th>{esc(header[1])}</th><th>{esc(header[2])}</th></tr>{body_rows}</table>
{restatement}

<h2>What the Numbers Say</h2>
{paragraphs(f['RECAP PARAGRAPH'])}
{take}

<h2>How to Read These Numbers</h2>
{glossary}

<h2>Want These Numbers Applied to Your Situation?</h2>
<p>Averages for a whole area only go so far. What matters is your neighborhood, your street, and your goals.{compared}</p>
<div class="cta">
  <div class="card"><h3>Thinking of buying?</h3>Tell me your price range and the areas you like, and I&rsquo;ll walk you through what&rsquo;s actually available and what it takes to win it.</div>
  <div class="card"><h3>Thinking of selling?</h3>Ask for a free, no-obligation home value analysis based on recent sales near you. See <b>thebutlerrealty.com/home-value</b>.</div>
</div>
<div class="contact">Call or text 480-810-9255 &nbsp;&bull;&nbsp; Brian@thebutlerrealty.com &nbsp;&bull;&nbsp; thebutlerrealty.com</div>

<div class="fine">
  <img class="hud" src="{img_url('hud-realtor-mls.png')}" alt="Equal Housing Opportunity, REALTOR, MLS">
  <div>Brian Butler, REALTOR&reg; &nbsp;|&nbsp; eXp Realty &nbsp;|&nbsp; License # SA701819000, Arizona Department of Real Estate. Data from {esc(f['SOURCE'])}; ARMLS may revise prior-month figures in later reports. This report is general market information, not financial, investment, or legal advice. Information deemed reliable but not guaranteed.</div>
</div>
</body></html>"""


# ----------------------------------------------------------------- printing

def find_browser():
    for c in BROWSER_CANDIDATES:
        if Path(c).exists():
            return c
    return shutil.which("msedge") or shutil.which("chrome")


def check_html(doc):
    """Last line of defense before anything ships."""
    low = doc.lower()
    if "the butler realty" in low:
        raise ReportError("Retired wordmark 'The Butler Realty' found in the report -- refusing to build")
    if "independently owned" in low:
        raise ReportError("Franchise language found in the report -- refusing to build")
    if re.search(r"\[update|\[brian|\{\w+\}", doc):
        raise ReportError("Unfilled placeholder found in the report -- refusing to build")


def html_to_pdf(doc, output):
    """Print an HTML string to `output` through headless Edge/Chrome. The
    existing file is replaced only after a good PDF is produced."""
    check_html(doc)
    browser = find_browser()
    if not browser:
        raise ReportError("Neither Microsoft Edge nor Chrome was found to print the PDF")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        page, out, profile = tmp / "report.html", tmp / "report.pdf", tmp / "profile"
        page.write_text(doc, encoding="utf-8")
        proc = subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
             f"--user-data-dir={profile}", f"--print-to-pdf={out}", page.as_uri()],
            capture_output=True, text=True, timeout=120, creationflags=NO_WINDOW,
        )
        # Edge can return before the file is fully written -- wait for it to
        # appear and stop growing.
        last, stable = -1, 0
        for _ in range(60):
            size = out.stat().st_size if out.exists() else 0
            stable = stable + 1 if (size and size == last) else 0
            if stable >= 2:
                break
            last = size
            time.sleep(0.5)
        if not out.exists() or out.stat().st_size < 5000 or out.read_bytes()[:4] != b"%PDF":
            raise ReportError(f"Browser did not produce a valid PDF: {proc.stderr[-300:]}")
        output = Path(output)
        output.parent.mkdir(exist_ok=True)
        shutil.copyfile(out, output)  # replace only after a good build
    return output


def build(handoff=None, output=OUTPUT_PDF):
    """Build the PDF from `handoff` (default: newest market update). Returns
    (output_path, month_year). Raises ReportError on any problem, leaving the
    existing PDF untouched."""
    handoff = Path(handoff) if handoff else newest_market_update()
    fields = parse_handoff(handoff)
    if fields.get("CONTENT TYPE", "").lower() != "market update":
        raise ReportError(f"{handoff.name} is not a Market Update hand-off")
    doc = render_html(fields)
    return html_to_pdf(doc, output), fields["MONTH/YEAR"]


if __name__ == "__main__":
    try:
        path, month = build(sys.argv[1] if len(sys.argv) > 1 else None)
    except ReportError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"Built {path} ({month})")
