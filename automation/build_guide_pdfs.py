"""
Builds the four evergreen downloadable guides on thebutlerrealty.com:

    downloads/first_time_buyer_guide.pdf
    downloads/home_seller_checklist.pdf
    downloads/home_maintenance_calendar.pdf
    downloads/neighborhood_spotlights.pdf

    python automation/build_guide_pdfs.py            # rebuild all four
    python automation/build_guide_pdfs.py buyer      # just one (buyer|seller|maintenance|neighborhoods)

Rebuilt 2026-11-13 after finding the old versions (made by a one-off script that
was never saved) carried the retired "The Butler Realty" wordmark on the cover,
hard-coded price ranges and assistance-program names that go stale, and East
Valley city scope the business no longer targets.

Content rules baked in (CLAUDE.md + Brian's direction):
  * Identity is "Brian Butler | REALTOR(R) | eXp Realty | License # SA701819000".
    No "The Butler Realty" wordmark, no franchise language (check_html enforces).
  * No dollar figures that change: no price ranges, closing-cost dollar amounts,
    HOA dollar amounts, vendor prices. Buyers are pointed to Brian ("call for
    the last 90 days of closed sales") and to the monthly market report.
  * No named down-payment-assistance programs. The guide says options exist and
    that Brian will connect the reader with a lender who can walk through them.
  * The neighborhood guide is generated FROM the site's own neighborhood pages
    (neighborhoods/**), so it stays in sync with what's already published and
    never says anything the site doesn't. Re-run this script after adding or
    changing a neighborhood page.

Printing is shared with build_market_report_pdf.py (headless Edge, no pip deps).
"""

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_market_report_pdf import ReportError, html_to_pdf, img_url  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = PROJECT_ROOT / "downloads"

ID_LINE = "Brian Butler, REALTOR&reg; &nbsp;|&nbsp; eXp Realty &nbsp;|&nbsp; License # SA701819000"
CONTACT = "480-810-9255 &nbsp;&bull;&nbsp; Brian@thebutlerrealty.com &nbsp;&bull;&nbsp; thebutlerrealty.com"
GENERAL_DISCLAIMER = (
    "This guide is general information, not financial, legal, tax, or investment advice. "
    "Programs, rules, timelines, and costs vary and change; confirm specifics with your lender, "
    "title company, and the documents for your own transaction. Information deemed reliable but not guaranteed."
)


def esc(s):
    return html.escape(s, quote=True)


# ------------------------------------------------------------ block renderer
# Content is a list of tuples:
#   ("h2", text) ("h3", text) ("p", text) ("ul", [items]) ("ol", [items])
#   ("check", [items]) ("tip", text) ("table", [header...], [[row...]...])
#   ("page",)  -> force a page break
# Text is plain; it is escaped here (use &-free wording).

def render_blocks(blocks):
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h2":
            out.append(f"<h2>{esc(b[1])}</h2>")
        elif kind == "h3":
            out.append(f"<h3>{esc(b[1])}</h3>")
        elif kind == "p":
            out.append(f"<p>{esc(b[1])}</p>")
        elif kind == "ul":
            out.append("<ul>" + "".join(f"<li>{esc(i)}</li>" for i in b[1]) + "</ul>")
        elif kind == "ol":
            out.append("<ol>" + "".join(f"<li>{esc(i)}</li>" for i in b[1]) + "</ol>")
        elif kind == "check":
            out.append("<ul class='check'>" + "".join(f"<li>{esc(i)}</li>" for i in b[1]) + "</ul>")
        elif kind == "tip":
            out.append(f"<div class='tip'><b>Brian&rsquo;s Tip:</b> {esc(b[1])}</div>")
        elif kind == "table":
            head = "".join(f"<th>{esc(h)}</th>" for h in b[1])
            rows = "".join(
                "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in b[2]
            )
            out.append(f"<table><tr>{head}</tr>{rows}</table>")
        elif kind == "page":
            out.append("<div class='pb'></div>")
        else:
            raise ReportError(f"unknown block kind {kind}")
    return "\n".join(out)


CSS = """
  @page { size: Letter; margin: 0.6in 0.7in 0.8in 0.7in;
    @bottom-center { content: 'Brian Butler, REALTOR®  |  eXp Realty  |  License # SA701819000  |  480-810-9255  |  thebutlerrealty.com'; font-size:7.5pt; color:#555566; font-family:'Segoe UI',Arial,sans-serif; } }
  @page :first { @bottom-center { content: ''; } }
  :root { --primary:#1B4F72; --accent:#2E86C1; --light:#EBF5FB; --gray:#555566; --dark:#1a1a2e; }
  * { box-sizing:border-box; }
  body { font-family:'Segoe UI','DM Sans',Arial,sans-serif; color:#2d2d3a; font-size:10.5pt; line-height:1.5; margin:0; }
  h1,h2,h3 { font-family:Georgia,'Playfair Display',serif; color:var(--primary); }
  h2 { font-size:15pt; margin:20px 0 6px; break-after:avoid; }
  h3 { font-size:12pt; margin:14px 0 4px; break-after:avoid; }
  p { margin:0 0 8px; }
  ul,ol { margin:4px 0 10px; padding-left:22px; } li { margin-bottom:4px; }
  ul.check { list-style:none; padding-left:0; }
  ul.check li { padding-left:22px; position:relative; }
  ul.check li::before { content:''; position:absolute; left:0; top:4px; width:11px; height:11px; border:1.5px solid var(--accent); border-radius:2px; }
  .tip { background:var(--light); border-left:4px solid var(--accent); border-radius:6px; padding:10px 14px; margin:10px 0; break-inside:avoid; }
  table { width:100%; border-collapse:collapse; margin:8px 0 12px; font-size:10pt; break-inside:avoid; }
  th { background:var(--primary); color:#fff; text-align:left; padding:7px 10px; }
  td { padding:7px 10px; border-bottom:1px solid #dfe6ec; vertical-align:top; }
  tr:nth-child(even) td { background:#f6fafc; }
  .pb { break-after:page; }
  .cover { min-height:8.6in; display:flex; flex-direction:column; justify-content:center; break-after:page; }
  .cover .band { background:var(--primary); color:#fff; border-radius:12px; padding:26px 30px; }
  .cover .band .who { font-family:Georgia,serif; font-size:17pt; font-weight:700; }
  .cover .band .sub { font-size:10pt; opacity:.85; margin-top:2px; }
  .cover img.icon { width:64px; height:64px; margin-bottom:12px; }
  .cover .kicker { color:var(--accent); font-weight:700; letter-spacing:.14em; text-transform:uppercase; font-size:9pt; margin:36px 0 6px; }
  .cover h1 { font-size:33pt; line-height:1.1; margin:0 0 12px; }
  .cover .tag { font-size:13pt; color:var(--gray); margin-bottom:6px; }
  .cover .area { margin-top:30px; font-size:10.5pt; color:var(--gray); }
  .endcard { background:var(--dark); color:#fff; border-radius:12px; padding:22px 26px; margin-top:22px; break-inside:avoid; }
  .endcard h2 { color:#fff; margin-top:0; } .endcard p { color:#e6ebf0; }
  .endcard .contact { font-weight:700; color:#8cc6ec; margin-top:8px; }
  .legal { margin-top:18px; border-top:1px solid #dfe6ec; padding-top:10px; font-size:8pt; color:var(--gray); display:flex; gap:12px; align-items:center; break-inside:avoid; }
  .legal img { height:34px; }
  .nb { break-inside:avoid; margin-bottom:6px; }
  .nb h3 { margin-top:16px; font-size:12.5pt; }
  .fit { display:flex; gap:10px; margin:6px 0 10px; }
  .fit div { flex:1; background:#f6fafc; border-top:3px solid var(--accent); border-radius:6px; padding:8px 11px; font-size:9.6pt; }
  .fit div.no { border-top-color:#9a9aaa; } .fit b { color:var(--primary); display:block; margin-bottom:2px; }
"""


def page(title, kicker, tagline, area_line, body_html):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title><style>{CSS}</style></head><body>
<section class="cover">
  <div class="band"><img class="icon" src="{img_url('butler-icon-white.png')}" alt="">
    <div class="who">Brian Butler</div>
    <div class="sub">REALTOR&reg; &nbsp;|&nbsp; eXp Realty &nbsp;|&nbsp; License # SA701819000</div></div>
  <div class="kicker">{esc(kicker)}</div>
  <h1>{title_html(title)}</h1>
  <div class="tag">{esc(tagline)}</div>
  <div class="area">{esc(area_line)}</div>
</section>
{body_html}
<div class="legal"><img src="{img_url('hud-realtor-mls.png')}" alt="Equal Housing Opportunity, REALTOR, MLS">
  <div>{ID_LINE}, Arizona Department of Real Estate. {esc(GENERAL_DISCLAIMER)}</div></div>
</body></html>"""


def title_html(title):
    return esc(title).replace(": ", ":<br>", 1) if ": " in title else esc(title)


def end_card(heading, text):
    return (f"<div class='endcard'><h2>{esc(heading)}</h2><p>{esc(text)}</p>"
            f"<div class='contact'>{CONTACT}</div></div>")


# ------------------------------------------------------------ first-time buyer

def buyer_guide():
    blocks = [
        ("h2", "A Message From Brian"),
        ("p", "If you're reading this, you're probably thinking about buying your first home. That's exciting, and it can also feel overwhelming. There's a lot of information out there, and some of it is confusing."),
        ("p", "I put this guide together to give you a clear, honest picture of what the home buying process looks like from start to finish. My approach is simple: you choose the home, on your timeline, at a price that makes sense for your life. No pressure. Just guidance and protection."),

        ("h2", "Step 1: Get Your Finances in Order"),
        ("p", "Before you start browsing listings, the smartest move is understanding your financial picture. A conversation with a lender early on answers most of your questions."),
        ("h3", "Understanding Down Payments"),
        ("p", "The question I hear most from first-time buyers is how much they need for a down payment. The answer is often less than people expect, and it depends on the loan program:"),
        ("ul", [
            "Conventional loans: available with relatively small down payments for qualified buyers.",
            "FHA loans: designed with flexible credit and down payment requirements, popular with first-time buyers.",
            "VA loans: a benefit for eligible veterans and service members that can allow no down payment.",
            "USDA loans: a zero-down option for eligible properties and buyers in qualifying rural areas.",
        ]),
        ("p", "Minimums, limits, and eligibility change and depend on your credit, income, and the property, so your lender is the right person to give you real numbers."),
        ("h3", "Help With Down Payment and Closing Costs"),
        ("p", "Good news: there are options. Down payment and closing cost assistance programs exist, offered through a mix of state, local, and lender programs. Who qualifies, how much is available, and what the rules are change often, so I don't list specific programs here. A list printed today could be wrong next month."),
        ("p", "What I can do is put you in touch with a lender who can walk through the options available right now and tell you which ones may fit your situation. Reach out and I'll make the introduction."),
        ("tip", "Don't drain your entire savings for the down payment. You'll want reserves for closing costs, moving expenses, and the surprises that come with owning a home (like the AC breaking in July in Arizona)."),
        ("h3", "Understanding Closing Costs"),
        ("p", "Closing costs are the fees and charges due when you officially become a homeowner. They're separate from your down payment, and many first-time buyers don't hear about them until late in the process. Your lender will give you a written estimate of them early on. They generally include:"),
        ("ul", [
            "Lender fees: origination, underwriting, credit report, and the appraisal.",
            "Title and escrow fees: title search, title insurance, and settlement charges.",
            "Prepaid items: homeowner's insurance, prorated property taxes, and prepaid interest.",
            "Recording fees: the county's charge to record the deed.",
            "HOA transfer fees: if the home is in an HOA community.",
        ]),
        ("tip", "Sometimes a seller agrees to cover part of a buyer's closing costs as part of the deal. That's called a seller concession. Whether it makes sense depends on the home and the market, and I'll help you think it through when the time comes."),
        ("h3", "Getting Pre-Approved"),
        ("p", "Pre-approval is one of the most important steps you can take before touring homes:"),
        ("ol", [
            "You'll know your real budget, based on what a lender has reviewed, not an online estimate.",
            "Sellers take your offer seriously. An offer without pre-approval is often passed over.",
            "You won't fall in love with a home that's out of range.",
            "Any credit issues surface early, while there's time to address them.",
        ]),
        ("p", "You'll typically provide pay stubs, tax returns, bank statements, and ID. It's a straightforward process, and I can introduce you to local lenders who will walk you through it."),

        ("h2", "Step 2: The Home Search"),
        ("p", "This is the fun part. Once you're pre-approved, we'll set up a custom MLS search based on what you're looking for, so you get alerts when matching homes come on the market."),
        ("h3", "What to Think About Before You Search"),
        ("ul", [
            "Location: commute, school options, shopping and dining, and the feel of the neighborhood.",
            "Home size: bedrooms, bathrooms, garage, and yard. What do you need now versus in three to five years?",
            "Must-haves versus nice-to-haves: single-story? Pool? Updated kitchen? Keep these separate from your wish list.",
            "HOA: many communities here have one. Dues and rules vary by community, so factor them into your monthly budget.",
            "New construction versus resale: new builds often come with builder incentives; resale homes may offer larger lots and mature landscaping.",
        ]),
        ("h3", "Where I Help"),
        ("p", "San Tan Valley and Florence are my specialty, and that's where I live and know the streets best. I also help buyers and sellers throughout the greater Phoenix area and across Arizona, so wherever you're looking, reach out. Prices move with the market, so instead of printing a number that will be out of date next month, I'll send you what has actually closed in the areas you're considering over the last 90 days. For a monthly look at San Tan Valley and Florence, download my free market report at thebutlerrealty.com/resources, and see my neighborhood guides at thebutlerrealty.com/neighborhoods."),

        ("h2", "Step 3: Making an Offer"),
        ("p", "When you find the right home, we'll put together a strong offer. Here's what goes into it:"),
        ("ul", [
            "Offer price: based on comparable sales, market conditions, and the home's condition. I'll advise you on what's competitive without overpaying.",
            "Earnest money deposit: a good-faith deposit that shows the seller you're serious. It's applied toward your costs at closing.",
            "Contingencies: inspection, appraisal, and financing contingencies protect you if something goes wrong. I'll explain each one and what it means to keep or give up protection.",
            "Closing timeline: often 30 to 45 days from accepted offer to closing, set by your contract.",
            "Seller concessions: we can ask the seller to help with some of your closing costs.",
        ]),

        ("h2", "Step 4: Under Contract, What Happens Next"),
        ("p", "Once your offer is accepted, the clock starts. Your contract sets the exact deadlines; this is a typical flow:"),
        ("table", ["Typical Timing", "Milestone", "What Happens"], [
            ["Right away", "Earnest money", "Your deposit is delivered to the title company."],
            ["First couple of weeks", "Home inspection", "A professional inspector examines the home. This is your chance to renegotiate or walk away if major problems turn up."],
            ["First couple of weeks", "Appraisal ordered", "Your lender orders an appraisal to confirm the home's value."],
            ["Weeks 2 to 4", "Loan processing", "Your lender processes your loan. Respond quickly when they ask for documents."],
            ["Near the end", "Clear to close", "Your lender issues final approval. You review your closing disclosure."],
            ["Closing day", "Sign and get keys", "You sign the paperwork, funds are recorded, and you officially become a homeowner."],
        ]),
        ("tip", "During this period, don't make big financial changes. Don't open new credit cards, make large purchases, change jobs, or move money around without talking to your lender first. Any of these can delay or derail your loan."),

        ("h2", "Step 5: Closing Day"),
        ("ol", [
            "Final walkthrough: we visit the home one last time, usually shortly before closing, to confirm it's in the condition you agreed to.",
            "Signing: you meet at the title company to sign your loan documents and closing paperwork. Bring a valid photo ID and any funds due, as your title company instructs.",
            "Funding: once everything is signed and your lender funds the loan, the title company records the deed with the county.",
            "Keys: you get your keys. Congratulations, you're a homeowner.",
        ]),
        ("p", "The signing appointment usually takes about an hour, and I'll be there with you."),

        ("h2", "Common Mistakes to Avoid"),
        ("ol", [
            "Skipping pre-approval and shopping above your budget.",
            "Making big financial changes during the loan process.",
            "Waiving the home inspection to win a competitive offer. It is rarely worth the risk.",
            "Falling for a home before doing the math on total monthly costs: mortgage, taxes, insurance, and HOA.",
            "Not planning for maintenance. A common rule of thumb is to set aside 1 to 2 percent of the home's value each year.",
            "Going it alone. A buyer's agent works for you, and I'll walk you through how my compensation works in our first conversation, before you sign anything.",
        ]),
    ]
    end = end_card("Ready to Get Started?",
                   "Whether you're six months out or ready to start looking this weekend, I'm here whenever you are. No pressure and no pitch, just a conversation about your goals. Down payment assistance options change often, so ask me and I'll connect you with a lender who can go over what's available.")
    return page("The First-Time Buyer's Guide to Homeownership", "Free Guide",
                "From pre-approval to keys in hand, in plain English.",
                "Serving Arizona, specializing in San Tan Valley & Florence.", render_blocks(blocks) + end)


# ------------------------------------------------------------ seller checklist

def seller_guide():
    blocks = [
        ("h2", "Why Preparation Matters"),
        ("p", "How a home is prepared can make a real difference in how buyers respond to it. This checklist walks through what to do before listing, organized by timeline."),
        ("p", "You don't need a major renovation. Focused effort on the right things matters more than spending a lot. When we meet, I'll tell you what is worth doing in your home and what isn't."),

        ("h2", "Phase 1: Declutter and Depersonalize (2 to 4 Weeks Before Listing)"),
        ("p", "Buyers need to picture their own life in your space, which is hard when they're looking at your family photos, collections, and clutter."),
        ("check", [
            "Remove personal photos, religious items, and political decor so the home has the broadest appeal.",
            "Clear kitchen counters of everything except one or two decorative items.",
            "Declutter closets. Buyers will open them. Aim for them to look roomy.",
            "Clear out the garage so buyers can see usable space.",
            "Remove excess furniture so rooms feel larger.",
            "Pack up seasonal items and anything you won't need before the move.",
            "Consider a small storage unit for overflow.",
        ]),

        ("h2", "Phase 2: Deep Clean (1 to 2 Weeks Before Listing)"),
        ("p", "A spotless home signals that it's been cared for. A dirty one makes buyers wonder what else has been neglected."),
        ("check", [
            "Consider a professional deep cleaning.",
            "Clean all windows inside and out. Natural light helps.",
            "Steam clean or replace worn carpet.",
            "Scrub grout in bathrooms and the kitchen.",
            "Clean light fixtures and ceiling fans. Arizona dust builds up fast.",
            "Wipe down baseboards, door frames, and light switches.",
            "Clean the oven, dishwasher, and other appliances inside and out.",
            "Check for pet odors. You may be used to them, so ask a friend to be honest.",
        ]),
        ("tip", "In Arizona, dust is relentless. Plan to dust and vacuum often while your home is on the market, especially during monsoon season."),

        ("h2", "Phase 3: Repairs and Touch-Ups (1 to 2 Weeks Before Listing)"),
        ("p", "Fix the small stuff. Buyers notice flaws, and small issues make them wonder about bigger ones."),
        ("check", [
            "Fix leaky faucets and running toilets.",
            "Repair or replace cracked or broken tile.",
            "Touch up paint: scuffs, nail holes, and high-traffic wear. Neutral colors photograph and show best.",
            "Replace burned-out bulbs and use consistent, warm-white bulbs throughout.",
            "Fix doors that stick, squeak, or don't latch.",
            "Repair or replace damaged window screens.",
            "Re-caulk around tubs, showers, and sinks where old caulk has yellowed or cracked.",
            "Address any obvious AC issues. Arizona buyers will test the AC right away.",
            "For an older home, ask me about a pre-listing inspection so you can address issues before buyers find them.",
        ]),

        ("h2", "Phase 4: Curb Appeal (1 Week Before Listing)"),
        ("p", "Buyers form their first impression before they walk through the door. In Arizona, curb appeal is its own thing."),
        ("check", [
            "Clean up desert landscaping: trim bushes, remove dead plants, and refresh rock or gravel areas.",
            "Edge walkways and driveways.",
            "Power wash the driveway, sidewalks, and patio.",
            "Paint or replace a tired front door. It's one of the most visible and affordable upgrades.",
            "Update house numbers and the mailbox if they look dated.",
            "Add a few potted plants or desert-friendly flowers near the entry.",
            "Clean the garage door. It's one of the largest visible surfaces on your home.",
            "Make sure exterior lighting works and looks inviting for evening showings.",
        ]),

        ("h2", "Phase 5: Stage and Photograph (Listing Week)"),
        ("check", [
            "Consider professional staging. At minimum, follow the decluttering steps above.",
            "Professional photography matters. Most buyers start their search online, and photos are their first showing.",
            "Open all blinds and turn on all lights for the photo shoot.",
            "Add fresh towels in the bathrooms and a fresh throw on the couch.",
            "Put out a few fresh flowers or a bowl of fruit. Small touches add up.",
            "Set the AC to a comfortable temperature for showings. Buyers notice.",
        ]),

        ("h2", "During Showings: Quick Checklist"),
        ("check", [
            "Leave during showings. Buyers are more comfortable without the seller present.",
            "Make beds, clear dishes, and tidy up before every showing.",
            "Secure valuables, medications, and personal documents.",
            "Take pets with you or arrange for them to be elsewhere.",
            "Leave lights on and blinds open.",
            "Set the AC to a comfortable temperature before you leave.",
        ]),
    ]
    end = end_card("Want a Walkthrough of Your Home?",
                   "I'll walk through your home with you at no cost or obligation and tell you what's worth doing and what isn't. I can also put together a free home value analysis based on recent sales near you at thebutlerrealty.com/home-value.")
    return page("The Home Seller's Preparation Checklist", "Free Checklist",
                "A room-by-room, week-by-week guide to getting market-ready.",
                "Serving Arizona, specializing in San Tan Valley & Florence.", render_blocks(blocks) + end)


# ------------------------------------------------------------ maintenance calendar

def maintenance_guide():
    blocks = [
        ("h2", "Why Maintenance Matters"),
        ("p", "Arizona's climate, with scorching summers, monsoon storms, and constant dust, puts unique demands on a home. Staying on top of regular maintenance protects your investment and helps you avoid expensive emergency repairs."),
        ("p", "This calendar is organized by season. Most tasks take an afternoon or less, and the ones that don't are worth hiring a professional for. Follow your equipment manufacturers' guidance and your own contractors' advice for specifics."),

        ("h2", "Spring (March to May)"),
        ("p", "Spring is your window to prepare for the Arizona summer. Focus on your cooling system, exterior, and landscaping."),
        ("h3", "HVAC"),
        ("check", [
            "Schedule a professional AC tune-up and inspection before the real heat arrives. Good HVAC companies book up fast in late spring.",
            "Replace air filters. Dust means they need attention more often than in many parts of the country.",
            "Clean the outdoor condenser unit: remove debris and rinse the coils gently with a hose.",
            "Check that all vents are open and unobstructed.",
            "If you have a smart thermostat, set up its summer schedule.",
        ]),
        ("h3", "Exterior"),
        ("check", [
            "Inspect the roof for cracked or missing tiles, common after winter windstorms.",
            "Check exterior caulking around windows and doors. The sun breaks it down quickly.",
            "Inspect stucco for cracks. Hairline cracks from heat expansion are common.",
            "Clean out gutters if your home has them.",
            "Power wash the driveway, sidewalks, and patio.",
        ]),
        ("h3", "Landscaping"),
        ("check", [
            "Adjust irrigation timers for rising temperatures.",
            "Trim trees and bushes away from the house and roof.",
            "Look for termite activity and schedule an annual termite inspection.",
            "Treat weeds in gravel and rock areas.",
        ]),
        ("h3", "Pool (If Applicable)"),
        ("check", [
            "Schedule a pool equipment inspection and startup service.",
            "Check the pool fence and gate to make sure they close and latch properly. This is a key safety feature.",
            "Clean the tile line and check water chemistry.",
        ]),

        ("h2", "Summer (June to August)"),
        ("p", "Summer means extreme heat and monsoon storms. Keep your AC running and protect against storm damage."),
        ("h3", "Monsoon Prep"),
        ("check", [
            "Clear yard drains and any drainage paths around your home.",
            "Trim trees near your roof and power lines. Monsoon winds snap branches.",
            "Secure or store loose patio furniture, umbrellas, and decorations before storms.",
            "Check your garage door seal. Dust and water get in during dust storms.",
            "Test your sump pump if you have one.",
            "Know where your main water shut-off is.",
            "Check for water intrusion after every major storm: ceilings, windows, and the garage.",
        ]),
        ("h3", "Interior"),
        ("check", [
            "Check AC filters more often during peak summer, when dust and pollen are intense.",
            "Make sure the AC drain line is clear. A clogged drain line is a common cause of summer AC trouble.",
            "Keep an eye on your electric bill. A sudden spike can signal an AC problem.",
            "Run ceiling fans counterclockwise (as viewed from below) to push air down.",
        ]),
        ("h3", "Pool"),
        ("check", [
            "Clean skimmer baskets often. Monsoon debris clogs them fast.",
            "Check water chemistry regularly. Intense sun uses up chlorine quickly.",
            "Make sure pool equipment is running properly.",
        ]),
        ("tip", "If your AC fails in July, it can take days to get a technician during peak season. That spring tune-up is worth it. If your system is getting old, start planning for replacement before it quits in August."),

        ("h2", "Fall (September to November)"),
        ("p", "Fall is the most comfortable season here and a great time for outdoor projects and winter preparation."),
        ("h3", "HVAC"),
        ("check", [
            "Test your heating system before you need it.",
            "Replace air filters.",
            "Consider duct cleaning if it's been several years. Dust accumulates inside ducts.",
        ]),
        ("h3", "Exterior"),
        ("check", [
            "Inspect the roof again after monsoon season for loose tiles, debris damage, or leaks.",
            "Touch up exterior paint where sun damage is visible.",
            "Check the irrigation system for leaks or broken heads.",
            "Clean and store monsoon prep supplies.",
        ]),
        ("h3", "Interior"),
        ("check", [
            "Check smoke and CO detectors and replace batteries.",
            "Test garage door safety sensors and lubricate moving parts.",
            "Check the water heater for sediment buildup. Flushing annually is common practice with hard water.",
            "Inspect under sinks for leaks.",
            "Check caulking around showers and tubs.",
        ]),

        ("h2", "Winter (December to February)"),
        ("p", "Arizona winters are mild, but freezing temperatures can happen overnight. A few precautions go a long way."),
        ("check", [
            "Protect outdoor pipes and hose bibs on nights that dip to freezing.",
            "Disconnect and drain garden hoses.",
            "Adjust irrigation timers for cooler weather. Overwatering in winter hurts desert plants.",
            "Service your fireplace or fire pit before heavy use.",
            "Check weather stripping on exterior doors. Cold air and dust both sneak through gaps.",
            "Clean the dryer vent. A clogged vent is a fire hazard, so do this annually.",
            "Schedule your annual termite inspection if it's due.",
            "Deep clean the interior to start the new year fresh.",
        ]),

        ("h2", "Annual Professional Services to Schedule"),
        ("table", ["Service", "When"], [
            ["AC tune-up", "Spring, before summer"],
            ["Termite inspection", "Spring or fall"],
            ["Roof inspection", "Fall, after monsoon season"],
            ["Pool service startup", "Spring"],
            ["Water heater flush", "Fall"],
            ["Dryer vent cleaning", "Winter"],
            ["Deep house cleaning", "Spring or winter"],
        ]),
        ("p", "Costs vary by provider and change over time, so get current quotes before you schedule."),
    ]
    end = end_card("Need a Contractor Recommendation?",
                   "Ask me. I'm happy to point you toward trusted local pros for any of the services above, whether or not we've worked together on a purchase.")
    return page("The Arizona Homeowner's Maintenance Calendar", "Free Guide",
                "A seasonal maintenance guide for Arizona homes.",
                "Protect your investment with the right care at the right time.", render_blocks(blocks) + end)


# ------------------------------------------------------------ neighborhood spotlights
# Built from the site's own neighborhood pages so it never says anything the
# site doesn't, and carries no prices (see CLAUDE.md "Neighborhoods section").

SECTIONS = [
    ("San Tan Valley", "neighborhoods/san-tan-valley.html", [
        "johnson-ranch", "solera-at-johnson-ranch", "encanterra", "pecan-creek", "copper-basin",
        "ironwood-crossing", "circle-cross-ranch", "san-tan-heights", "skyline-ranch", "rancho-bella-vista",
    ]),
    ("Florence", "neighborhoods/florence.html", [
        "historic-downtown-florence", "anthem-at-merrill-ranch-parkside", "sun-city-anthem-merrill-ranch",
        "magma-ranch-and-new-construction-corridor", "florence-gardens",
    ]),
]


def _clean(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def _main(path):
    s = path.read_text(encoding="utf-8")
    m = re.search(r"<main.*?</main>", s, re.S)
    if not m:
        raise ReportError(f"No <main> in {path}")
    return m.group(0)


def city_intro(path):
    """First two paragraphs after the 'Start here' heading."""
    m = _main(path)
    i = m.find("Start here")
    paras = re.findall(r"<p[^>]*>(.*?)</p>", m[i:], re.S)
    return [_clean(p) for p in paras[:2]]


def neighborhood(path):
    m = _main(path)
    title = _clean(re.search(r"<h1[^>]*>(.*?)</h1>", m, re.S).group(1))
    i = m.find("The short version")
    first = _clean(re.search(r"<p[^>]*>(.*?)</p>", m[i:], re.S).group(1))
    fit = {}
    for label in ("Good fit", "Look elsewhere if"):
        j = m.find(f">{label}<")
        if j == -1:
            raise ReportError(f"{path.name}: missing '{label}' section")
        fit[label] = _clean(re.search(r"<p[^>]*>(.*?)</p>", m[j:], re.S).group(1))
    return title, first, fit


OTHER_CITIES = [
    ("Gilbert", "Gilbert grew from a farming town into one of the East Valley's larger cities. Its Heritage District is a walkable downtown area with restaurants, bars, and shops, and its park system includes Freestone Park and the Riparian Preserve at Water Ranch, a popular spot for walking trails and bird watching. Community events include Gilbert Days and seasonal festivals.",
     "Parts of Gilbert are served by Gilbert Public Schools, Higley Unified, and Chandler Unified, so verify the assigned schools by address."),
    ("Mesa", "Mesa is the East Valley's largest city, with a wide range of home ages and styles, from established neighborhoods near downtown to newer master-planned communities in the southeast. Downtown Mesa has an arts district with museums and galleries, Mesa Riverview is a shopping and entertainment district, Sloan Park hosts Cactus League spring training, and Usery Mountain Regional Park offers hiking and mountain biking. Light rail runs through west Mesa into Tempe and Phoenix.",
     "Mesa Unified is the largest district; Gilbert and Queen Creek districts serve parts of east Mesa. Verify the assigned schools by address. With older homes anywhere, a thorough inspection of systems such as HVAC, roofing, and plumbing is worth planning for."),
    ("Chandler", "Chandler has a major technology and finance employment base and a walkable downtown with restaurants, boutiques, and entertainment venues. Tumbleweed Park and Veterans Oasis Park provide outdoor recreation, Chandler Fashion Center anchors the shopping, and annual events include the Ostrich Festival, the Chandler Jazz Festival, and the Tumbleweed Tree Lighting.",
     "Most of Chandler is served by Chandler Unified School District. Verify the assigned schools by address."),
    ("Queen Creek", "Queen Creek has grown from a farming community into a major new-construction market while keeping its agricultural roots. The Queen Creek Olive Mill, Schnepf Farms, pumpkin patches, and u-pick orchards give it a character you won't find elsewhere in the East Valley, and the town has trail systems and mountain access.",
     "Queen Creek Unified serves most of the town, and Higley Unified serves some western areas. Verify the assigned schools by address."),
    ("Apache Junction", "Apache Junction sits at the base of the Superstition Mountains. Lost Dutchman State Park offers hiking, the Apache Trail Scenic Drive is one of Arizona's best-known drives, and Canyon Lake and nearby Saguaro Lake offer boating and fishing. Retail is concentrated along the US-60 corridor, and housing includes a mix of site-built and manufactured homes.",
     "Apache Junction Unified School District serves the area. Verify the assigned schools by address."),
]


def neighborhoods_guide():
    body = []
    body.append("<h2>About This Guide</h2>")
    body.append("<p>San Tan Valley and Florence are my specialty. They're where I live and know the streets best, so those get the most detail here. I also help buyers and sellers throughout the greater Phoenix area and across Arizona, not only in these areas. Each San Tan Valley and Florence neighborhood below is summarized from my full neighborhood guides at thebutlerrealty.com/neighborhoods, where you'll find schools, getting around, and the tradeoffs to know about each one. Other East Valley cities follow at the end.</p>")
    body.append("<p><b>About prices:</b> Prices move with the market, so this guide doesn't print a number that would be out of date next month. Call or text me and I'll send you what has actually closed in the area or neighborhood you're considering over the last 90 days. For monthly numbers for San Tan Valley and Florence, download my free market report at thebutlerrealty.com/resources.</p>")
    count = 0
    for n, (city, city_page, slugs) in enumerate(SECTIONS):
        brk = " style='break-before:page'" if n else ""
        body.append(f"<h2{brk}>{esc(city)}</h2>")
        for para in city_intro(PROJECT_ROOT / city_page):
            body.append(f"<p>{esc(para)}</p>")
        folder = Path(city_page).with_suffix("")
        for slug in slugs:
            title, first, fit = neighborhood(PROJECT_ROOT / folder / f"{slug}.html")
            body.append(
                f"<div class='nb'><h3>{esc(title)}</h3><p>{esc(first)}</p>"
                f"<div class='fit'><div><b>Good fit</b>{esc(fit['Good fit'])}</div>"
                f"<div class='no'><b>Look elsewhere if</b>{esc(fit['Look elsewhere if'])}</div></div></div>"
            )
            count += 1
    body.append("<h2 style='break-before:page'>Elsewhere in the East Valley</h2>")
    body.append("<p>Here's a quick look at five other East Valley cities. Wherever you're looking, in these cities or anywhere else in Arizona, I'm glad to help. Tell me what matters to you and I'll help you compare areas.</p>")
    for city, para, schools in OTHER_CITIES:
        body.append(f"<div class='nb'><h3>{esc(city)}</h3><p>{esc(para)}</p><p>{esc(schools)}</p></div>")
    body.append(end_card("Not Sure Which Area Is Right for You?",
                         "That's what I'm here for. Tell me what matters most (schools, commute, space, amenities, budget) and I'll help you narrow it down. Sometimes the right neighborhood isn't the one you expected."))
    return page("East Valley Neighborhood Spotlights", "Free Guide",
                f"An insider's look at the East Valley, with {count} San Tan Valley and Florence neighborhoods in detail.",
                "Homes, schools, daily life, and the tradeoffs. I specialize in San Tan Valley & Florence.", "\n".join(body))


# ------------------------------------------------------------ main

GUIDES = {
    "buyer": ("first_time_buyer_guide.pdf", buyer_guide),
    "seller": ("home_seller_checklist.pdf", seller_guide),
    "maintenance": ("home_maintenance_calendar.pdf", maintenance_guide),
    "neighborhoods": ("neighborhood_spotlights.pdf", neighborhoods_guide),
}


def build(which=None):
    built = []
    for key in (which or GUIDES):
        filename, fn = GUIDES[key]
        built.append(html_to_pdf(fn(), DOWNLOADS / filename))
    return built


if __name__ == "__main__":
    keys = sys.argv[1:] or None
    bad = [k for k in (keys or []) if k not in GUIDES]
    if bad:
        print(f"Unknown guide(s) {bad}. Choose from: {', '.join(GUIDES)}")
        sys.exit(2)
    try:
        for p in build(keys):
            print(f"Built {p}")
    except ReportError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
