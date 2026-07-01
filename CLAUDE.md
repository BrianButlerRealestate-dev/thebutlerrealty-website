# The Butler Realty — thebutlerrealty.com

Static HTML site (no build step) deployed on Netlify. Brian Butler is a real estate agent, not a developer — keep changes self-contained and don't introduce a build process.

## Adding any new page (market update, community news post, area page, listing page, etc.)

Every time a new page is added to the site, do these in the same change — don't leave them for later:

1. **`sitemap.xml`** — add a `<url>` entry with the page's clean canonical URL (see below), a `<lastmod>` of the actual publish/edit date, and `<changefreq>`/`<priority>` consistent with sibling pages already in the file.
2. **`llms.txt`** — add a line under `## Pages` with the same clean URL and a one-line description pulled from the page's real `<meta name="description">` — never invent or guess the description.
3. **`netlify.toml`** (and mirror in `_redirects`) — if the new page isn't already covered by an existing wildcard redirect (e.g. `/market-updates/*` and `/community-news/*` already cover their subpages), add a `[[redirects]]` rule so the clean URL resolves. Confirm the page's own `<link rel="canonical">` matches that clean URL.
4. **Nav / index page** — if the new page should be discoverable by users, link it from the relevant listing page (`market-updates.html`, `community-news.html`, `areas.html`) and/or nav.

## URL convention

Pages are served at clean URLs without `.html` (e.g. `/about`, `/market-updates/june-2026-san-tan-valley-florence`), each backed by a Netlify redirect. Always write `<loc>`/canonical/llms.txt URLs in this clean form, not `foo.html`.

## Shared page structure

Every page shares the same `<nav>` and `<footer>` blocks (copy-pasted per file, not templated). When editing nav or footer copy, apply the change to every HTML file — grep for the string first to find all copies. Primary content lives inside `<main>` between `</nav>` and `<footer>`.

## JSON-LD LocalBusiness/RealEstateAgent schema

The same schema block (name, address, credentials, `openingHoursSpecification`, `aggregateRating`, `dateModified`, `author`) is duplicated across index.html, about.html, areas.html, buyers.html, contact.html, resources.html, reviews.html, sellers.html, areas/florence.html, and areas/san-tan-valley.html. Keep these in sync — if you update `aggregateRating`, `dateModified`, or opening hours in one, update all ten. Source `aggregateRating` and `openingHoursSpecification` from Google Business Profile, not guesses.
