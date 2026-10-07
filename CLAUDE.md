# Brian Butler — thebutlerrealty.com

Static HTML site (no build step) deployed on Netlify. Brian Butler is a real estate agent, not a developer — keep changes self-contained and don't introduce a build process.

## Brand name (compliance — do not regress)

Per a compliance call (2026-08-12), **"The Butler Realty" is retired as standalone
wording** — brokerage identity is **eXp Realty**, and the personal brand is
**"Brian Butler"**. The domain `thebutlerrealty.com`, Brian's email, and the
butler-with-house icon mark are all still fine. The site was swept clean of the
old wordmark; don't reintroduce "The Butler Realty" as visible text, in a logo,
in `<title>`/meta, or in JSON-LD `name` fields. Agent identity that must appear
on real estate content: `Brian Butler | eXp Realty | License SA701819000`.
Never add "Each office is independently owned and operated" — that's franchise
language and eXp is a single national brokerage.

## Deploy branch

Netlify builds from **`main`**. A local `master` branch can sit stale without
meaning anything is undeployed — check the live URL, or push explicitly
(`git push origin master:main` / `git push origin <local-branch>:main`).

## Adding any new page (market update, community news post, area page, listing page, etc.)

Every time a new page is added to the site, do these in the same change — don't leave them for later:

1. **`sitemap.xml`** — add a `<url>` entry with the page's clean canonical URL (see below), a `<lastmod>` of the actual publish/edit date, and `<changefreq>`/`<priority>` consistent with sibling pages already in the file.
2. **`llms.txt`** — add a line under `## Pages` with the same clean URL and a one-line description pulled from the page's real `<meta name="description">` — never invent or guess the description.
3. **`netlify.toml`** (and mirror in `_redirects`) — if the new page isn't already covered by an existing wildcard redirect (e.g. `/market-updates/*` and `/community-news/*` already cover their subpages), add a `[[redirects]]` rule so the clean URL resolves. Confirm the page's own `<link rel="canonical">` matches that clean URL.
4. **Nav / index page** — if the new page should be discoverable by users, link it from the relevant listing page (`market-updates.html`, `community-news.html`, `neighborhoods.html`) and/or nav.

## URL convention

Pages are served at clean URLs without `.html` (e.g. `/about`, `/market-updates/june-2026-san-tan-valley-florence`), each backed by a Netlify redirect. Always write `<loc>`/canonical/llms.txt URLs in this clean form, not `foo.html`.

## Neighborhoods section (renamed from "Areas" 2026-10-07)

`areas.html` / `areas/` became `neighborhoods.html` / `neighborhoods/`. `/areas`, `/areas.html`
and `/areas/*` 301 to the `/neighborhoods` equivalents in `netlify.toml` and `_redirects` — keep
those rules so old links and search results keep working. Structure:

- `neighborhoods.html` — index, lists every neighborhood grouped by city
- `neighborhoods/{city}.html` — city overview (San Tan Valley, Florence); carries the shared schema block
- `neighborhoods/{city}/{slug}.html` — one guide per neighborhood (BreadcrumbList + WebPage + FAQPage
  JSON-LD, not the shared agent block), with a keyless Google Maps embed

Neighborhood pages deliberately publish **no price ranges or HOA dollar amounts** — Brian chose
"call for the last 90 days of closed sales" over a number that goes stale. Florence Unified now uses
K-5 elementary + separate middle schools; don't reintroduce "K-8" school names. When a new
neighborhood page is added, link it from both its city page's guide grid and `neighborhoods.html`.

## Shared page structure

Every page shares the same `<nav>` and `<footer>` blocks (copy-pasted per file, not templated). When editing nav or footer copy, apply the change to every HTML file — grep for the string first to find all copies. Primary content lives inside `<main>` between `</nav>` and `<footer>`.

## JSON-LD LocalBusiness/RealEstateAgent schema

The same schema block (name, address, credentials, `openingHoursSpecification`, `aggregateRating`, `dateModified`, `author`) is duplicated across index.html, about.html, neighborhoods.html, buyers.html, contact.html, resources.html, reviews.html, sellers.html, neighborhoods/florence.html, and neighborhoods/san-tan-valley.html. Keep these in sync — if you update `aggregateRating`, `dateModified`, or opening hours in one, update all ten. Source `aggregateRating` and `openingHoursSpecification` from Google Business Profile, not guesses.
