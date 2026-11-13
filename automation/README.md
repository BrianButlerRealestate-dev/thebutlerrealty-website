# Website-publish automation (added 2026-07-28)

## What this closes

Previously, `weekly-alerts-gbp-website` (and the monthly `market-intelligence`
skill) would compliance-check and polish an article, then commit it locally
in the Cowork sandbox and stop -- Cowork has no GitHub credentials, so
pushing was always a manual step Brian did himself from a Desktop Claude
Code session. This automation closes that gap the same way the
`butler-template-engine` project already closed the render-graphic gap: a
local Windows Task Scheduler watcher that runs the real subagent
(`website-publisher`) headlessly, so the compliance rules only ever live in
one place -- `.claude/agents/website-publisher.md` -- instead of being
copied into every scheduled task that produces an article.

## What runs

Windows Task Scheduler task **`ButlerWebsitePublishPoll`** fires
`poll_and_publish_website.py` three times a day (morning / afternoon /
evening -- see the exact registration command below). Unlike the
`butler-template-engine` watchers, this one has **no `.bat` wrapper** and is
launched directly via `pythonw.exe` (the windowless Python build) specifically
so no console window ever flashes on screen -- see "No visible window"
below for the full reasoning.

Each pass:

1. Scans `content-queue-articles/*.md` for files not yet in
   `content-queue-articles/.processed.json`, skipping `README.md` and
   anything modified in the last 2 minutes (guards against picking up a file
   mid-write by the scheduled task).
2. For each new file, invokes `claude -p` headlessly: *"Use the
   website-publisher subagent to publish content-queue-articles/[filename]."*
   -- the same subagent used interactively, with the same "stop and flag
   rather than guess" behavior (incomplete input, a compliance conflict, an
   unresolved slug collision). Only the exact tools website-publisher needs
   are pre-approved (see `ALLOWED_TOOLS` in the script); anything else is
   denied automatically since there's no one at the keyboard to approve a
   permission prompt.
3. Records the outcome in `content-queue-articles/.processed.json` so the
   file is never re-published automatically, and appends full detail to
   `content-queue-articles/publish-automation.log`.
4. Fires one Windows toast notification per poll run summarizing what
   happened. If nothing new was found, the script exits silently -- no
   notification, no Claude invocation, no log line.

website-publisher's own spec already ends every successful run with
`git push origin master:main` -- that's what actually gets the article live.
No separate push step exists anywhere in this automation; publishing *is*
the push.

## The hand-off file format

Three scheduled sources write into this same folder, and every file must
start with a `CONTENT TYPE` field so `website-publisher` knows which format
to build (see `.claude/agents/website-publisher.md` for the authoritative
page-building rules -- this section only documents what the upstream task
must supply):

- **`CONTENT TYPE: Community News`** -- written by `weekly-alerts-gbp-website`
  (STEP 9d) to `content-queue-articles/[date]-[slug].md`, with clearly
  labeled sections: HEADLINE, SUBHEAD, BYLINE, CATEGORY, PUBLISH DATE,
  PROPOSED SLUG, BODY, and FROM BRIAN CLOSING (omitted entirely if no take
  was given that week -- never a placeholder). Publishes to
  `community-news/{area}/{slug}.html`.
- **`CONTENT TYPE: Market Update`** -- written by `market-intelligence`
  (added 2026-08-03, closing a gap where this output previously only went
  to Google Drive with a manual "open Claude Code" reminder that Brian had
  no trigger to act on) to `content-queue-articles/[date]-[month]-[year]-market-update.md`,
  with: MONTH/YEAR, AREA, DATA PERIOD, COMPARED TO, SOURCE, METRICS TABLE,
  RECAP PARAGRAPH, BRIAN'S TAKE (omitted entirely if none given that cycle),
  PUBLISH DATE, PROPOSED SLUG, and a literal data-only headline. Publishes
  to `market-updates/{slug}.html` (flat, no area subfolder) and updates the
  `market-updates.html` card list instead of a community-news area index.
- **`CONTENT TYPE: Rate Update`** -- written by `social-publisher` (in the
  `butler-template-engine` repo, added 2026-08-14) to
  `content-queue-articles/[date]-weekly-mortgage-rate-update.md`, after it
  finishes posting that week's rate-update graphic to social -- same rate
  figures, no separate research step. Fields: WEEK OF, 30-YEAR RATE, 30-YEAR
  CHANGE, 15-YEAR RATE, 15-YEAR CHANGE, PILL STATUS, BRIAN'S TAKE. Unlike the
  other two types, this one has no PROPOSED SLUG and creates no new page --
  it edits the single existing `mortgage-rates.html` in place (updates the
  current snapshot, prepends a row to the rate history table).

Nothing writes HTML, touches sitemap.xml/llms.txt, or touches git except
website-publisher itself.

### Monthly Local Events articles (added 2026-09-02)

The `local-events-monthly-package` scheduled task in the `butler-template-engine`
repo drops two `CONTENT TYPE: Community News` hand-off files here each month (one
for San Tan Valley, one for Florence) at the top level of
`content-queue-articles/`, and this watcher publishes them like any other
community-news article — **no approval gate** (Brian's call). They use the normal
community-news shape: HEADLINE / SUBHEAD / BYLINE `Brian Butler, REALTOR®` /
CATEGORY / PUBLISH DATE / PROPOSED SLUG
`community-news/{area}/{month}-{year}-local-events` / BODY with `### ` subheads
and a closing `**Sources:**` line, optional FROM BRIAN CLOSING. The full
procedure that produces them is `butler-template-engine/local-events/RUNBOOK.md`.

### Monthly market report PDF (added 2026-11-13)

The free report the lead popup and `/resources` hand out is
`downloads/san_tan_valley_florence_market_report.pdf` (same filename every
month, so links never break). It is **generated, never hand-edited**:
`automation/build_market_report_pdf.py` reads the newest
`CONTENT TYPE: Market Update` hand-off (metrics table, recap, Brian's Take,
restatement note) and prints a 2-page PDF through headless Microsoft Edge (no
pip packages). After this watcher publishes a Market Update page successfully,
`refresh_market_report()` rebuilds the PDF from that same file, commits only
the PDF, and pushes `master:main`, then adds a second line to the toast. A
failure there never undoes the page publish; it shows up as "needs review".
It only commits from `master` (otherwise it builds the file and flags it).
The build refuses to run on an incomplete hand-off or if the retired
"The Butler Realty" wordmark / franchise language / a placeholder appears.

Manual rebuild any time: `python automation/build_market_report_pdf.py`
(add a hand-off path to build from a specific month).

### Evergreen guide PDFs (added 2026-11-13)

`automation/build_guide_pdfs.py` rebuilds the other four downloads
(`first_time_buyer_guide`, `home_seller_checklist`, `home_maintenance_calendar`,
`neighborhood_spotlights`). Not monthly: run it by hand
(`python automation/build_guide_pdfs.py`, or add `buyer|seller|maintenance|neighborhoods`)
after editing their text in that file or after adding/changing a page under
`neighborhoods/`, because the neighborhood guide is generated from those pages.
They carry no dollar figures and no named assistance programs by design.

## Task Scheduler registration (one-time)

Run this once, in a terminal or a Desktop Claude Code session (it's plain
Windows commands, no AI judgment involved):

```powershell
$action = New-ScheduledTaskAction -Execute "<PYTHONW_PATH>\pythonw.exe" `
  -Argument '"<WEBSITE_REPO>\automation\poll_and_publish_website.py"'
$trigger1 = New-ScheduledTaskTrigger -Daily -At 9:00AM
$trigger2 = New-ScheduledTaskTrigger -Daily -At 1:00PM
$trigger3 = New-ScheduledTaskTrigger -Daily -At 6:00PM
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
Register-ScheduledTask -TaskName "ButlerWebsitePublishPoll" -Action $action `
  -Trigger @($trigger1, $trigger2, $trigger3) -Principal $principal `
  -Description "Checks Website/content-queue-articles for new approved community-news articles and publishes them via the website-publisher subagent."
```

`-LogonType Interactive` matches the same "run only when logged on, no
stored password" choice already made for `ButlerRenderPoll` and
`ButlerIGPublishPoll` -- consistent with those, and needed for the toast
notification to render into a real desktop session.

To check, test, or change it:
```
Get-ScheduledTask -TaskName "ButlerWebsitePublishPoll" | Get-ScheduledTaskInfo
Start-ScheduledTask -TaskName "ButlerWebsitePublishPoll"    # trigger a pass immediately, don't wait for the next time slot
Disable-ScheduledTask -TaskName "ButlerWebsitePublishPoll"
Enable-ScheduledTask -TaskName "ButlerWebsitePublishPoll"
```

## No visible window

Console-subsystem programs (`python.exe`, `cmd.exe` running a `.bat`) pop a
visible window when Task Scheduler runs them in an interactive logged-on
session -- that's the flash Brian sees from the two `butler-template-engine`
watchers today. This script avoids it two ways:

1. Task Scheduler's action points straight at `pythonw.exe` (the windowless
   Python build) with the script as its only argument -- no `.bat`/`cmd.exe`
   layer at all, so there's nothing to flash before Python even starts.
2. The nested `claude -p` call inside the script is launched with
   `creationflags=subprocess.CREATE_NO_WINDOW`, so that child process can't
   pop a window either, even though `claude.exe` itself is a console-mode
   program.

If a flash is ever seen again, that's the first thing to check -- something
in the chain stopped going through `pythonw.exe` or lost the
`CREATE_NO_WINDOW` flag.

## RAM / background footprint

There is no persistent background process. Task Scheduler launches
`pythonw.exe`, it runs one pass (a file-listing check that takes well under
a second when there's nothing new), and exits completely -- releasing all
memory. The only time this uses meaningful RAM is the few minutes an actual
publish is running (a nested `claude.exe` process doing real work), and that
memory is released the moment it exits. Running the check 3x/day vs. hourly
makes no difference to RAM or cost when idle; it only changes how long an
approved article waits before going live (up to ~8 hours instead of up to 1).

## If a file gets flagged instead of published

Same philosophy as the render watcher: website-publisher stops and flags
rather than guessing (incomplete content, a compliance conflict, an
unresolved slug collision, etc. -- see `.claude/agents/website-publisher.md`).
A flagged file is still marked "processed" in `.processed.json` so the
automation doesn't retry it every pass and spam a notification each time.

**It self-heals once you edit the file (added 2026-09-15).** `find_new_files()`
re-checks a `flagged`/`error` entry automatically if the `.md` file's mtime is
newer than the `processed_at` on its `.processed.json` record -- i.e. editing
the hand-off file (fixing the content the agent flagged) is itself what
re-queues it, on the next poll, no manual step. Before this, an untouched
`.processed.json` entry blocked the file forever regardless of status, which
is exactly how a real incident happened: Brian hand-fixed a flagged article's
stale date reference, and three more polls silently skipped past it because
nothing ever cleared the entry -- he had to notice via the dashboard and
manually delete the key.

**The no-edit case is now a dashboard action too (added 2026-09-15).** A flag
that needs an *answer*, not a content edit -- "publish as-is," "use option 2,"
"hold this one" -- has no file change for the mtime check above to notice. The
Butler approval dashboard's **"Website — needs your input"** panel
(`http://localhost:8770`, butler-template-engine) now has two buttons on every
flagged item for exactly this:
- **Re-queue as-is** -- deletes the `.processed.json` entry, nothing else. The
  next poll re-evaluates the unedited file fresh (only makes sense if the
  underlying condition already resolved itself, e.g. a moved-past date, or
  you want the agent to take a fresh look).
- **Send guidance & re-queue** -- writes your typed answer to
  `content-queue-articles/.guidance/<filename>.md.txt`, then deletes the
  `.processed.json` entry. `publish_one()` reads and deletes that file
  one-shot on the next run and folds it verbatim into the agent's prompt as
  your direct instruction ("Brian directly answered the stop-and-ask flag...
  act on it: `<your text>`"). Consumed once, so it never leaks onto a later,
  unrelated flag on the same filename.

Both buttons are optimistic-concurrency guarded and logged the same way the
dashboard's other write actions are (see butler-template-engine/automation/README.md
→ "Approval dashboard"). The raw manual path -- deleting the key from
`content-queue-articles/.processed.json` yourself -- still works if the
dashboard is ever down.

## Logs

`content-queue-articles/publish-automation.log` has the full detail of
every poll, including silent "file too fresh, skipping" lines -- useful for
confirming the task is actually firing on schedule even when there's
nothing to do.
