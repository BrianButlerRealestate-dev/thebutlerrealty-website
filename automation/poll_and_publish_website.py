"""
Content-queue-articles/ watcher for thebutlerrealty.com.

Run by Windows Task Scheduler three times a day (see the setup instructions
Brian was given alongside this file). Each run is a single pass: look for
.md hand-off files in content-queue-articles/ that haven't been published
yet, hand each one to the website-publisher subagent via a headless
`claude -p` call, record the result, and fire one desktop notification
summarizing the run. If nothing new is found, the script exits quietly --
no notification, no Claude invocation, no log line.

This intentionally has no .bat wrapper and is launched directly via
pythonw.exe (the windowless Python build) so no console window ever
flashes on screen -- see the setup instructions for the exact Task
Scheduler registration. The nested `claude -p` call is also launched with
CREATE_NO_WINDOW so its own process can't pop a window either.

State lives in content-queue-articles/.processed.json so a `success` file is
never re-published. A `flagged`/`error` file IS reconsidered on a later poll,
but only if it was edited (mtime) after the run that flagged it (`processed_at`)
-- added 2026-09-15 after a real incident: Brian fixed a flagged article by
hand-editing its .md, but nothing cleared its .processed.json entry, so three
more polls silently skipped straight past the fix. Editing the file is now
itself the signal to re-check it; an untouched flag is left alone rather than
re-spending a claude call on the same unresolved editorial question every poll.
Full output from every run is appended to content-queue-articles/publish-automation.log
for auditing when nobody's watching the toast notification.

Mirrors automation/poll_and_render.py in the butler-template-engine project
(same shape, same safety rules) -- see that file's docstring for the sibling
watcher this one is modeled on.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_QUEUE = PROJECT_ROOT / "content-queue-articles"
STATE_FILE = CONTENT_QUEUE / ".processed.json"
LOG_FILE = CONTENT_QUEUE / "publish-automation.log"
# One-shot free-text answers to a stop-and-ask flag, written by the Butler
# approval dashboard's "Website -- needs your input" panel (see
# butler-template-engine/automation/approval_dashboard.py). Consumed and
# deleted by publish_one() the next time the file is processed -- see
# "Re-queuing a flagged file" in automation/README.md.
GUIDANCE_DIR = CONTENT_QUEUE / ".guidance"

# Resolved explicitly rather than relying on PATH -- Task Scheduler's launch
# environment doesn't reliably inherit the interactive shell's PATH (same
# gotcha documented in butler-template-engine/automation/README.md).
# Order: CLAUDE_BIN env var, then the standard per-user install location
# (~/.local/bin/claude.exe, computed from the running user -- nothing personal
# is stored in the repo), then whatever PATH finds.
def _find_claude():
    env = os.environ.get("CLAUDE_BIN")
    if env:
        return env
    default = Path.home() / ".local" / "bin" / "claude.exe"
    if default.exists():
        return str(default)
    return shutil.which("claude") or "claude"


CLAUDE_BIN = _find_claude()

# Only the tools website-publisher actually needs (per
# .claude/agents/website-publisher.md): Read/Write/Edit/Grep/Glob for
# inspecting and writing the article + registration files, and Bash scoped
# to exactly the git subcommands its own spec calls for. Nothing else is
# pre-approved, so if a hand-off file somehow tried to make the agent do
# something outside its documented job, the tool call is denied
# automatically (headless = no prompt to approve it) instead of silently
# running.
ALLOWED_TOOLS = (
    "Task Read Write Edit Grep Glob "
    "Bash(git status:*) Bash(git add:*) Bash(git commit:*) Bash(git push:*)"
)

MAX_BUDGET_USD = "3.00"
TIMEOUT_SECONDS = 900
MIN_FILE_AGE_SECONDS = 120  # skip files still possibly being written by the scheduled task

# website-publisher's own spec ends every successful run with a real
# `git push origin master:main` and reports the final slug/URL -- look for
# either as evidence of a completed publish.
URL_RE = re.compile(r"https://thebutlerrealty\.com/community-news/[^\s`\"')]+")
PUSH_OK_RE = re.compile(r"\b[0-9a-f]{7,40}\.\.[0-9a-f]{7,40}\s+master\s*->\s*main\b|Everything up-to-date")

# Windows-only; harmless no-op flag value if this ever ran elsewhere.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(message):
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    if not STATE_FILE.exists():
        return {"processed": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log(f"! Could not read {STATE_FILE.name} ({e}) -- starting fresh, nothing lost since "
            f"nothing is deleted, only appended.")
        return {"processed": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _edited_since_flag(path, entry):
    """True if `path`'s mtime is newer than the run that flagged/errored it --
    i.e. someone (Brian, or a corrected hand-off) touched the file since, so
    it's worth another look. If processed_at can't be parsed, err toward
    re-checking rather than silently burying it forever."""
    processed_at = entry.get("processed_at") if isinstance(entry, dict) else None
    if not processed_at:
        return True
    try:
        flagged_ts = datetime.fromisoformat(processed_at).timestamp()
    except ValueError:
        return True
    try:
        return path.stat().st_mtime > flagged_ts
    except OSError:
        return False


def find_new_files(state):
    if not CONTENT_QUEUE.exists():
        return []
    now = time.time()
    candidates = []
    for path in sorted(CONTENT_QUEUE.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        entry = state["processed"].get(path.name)
        if entry is not None:
            status = entry.get("status") if isinstance(entry, dict) else entry
            if status not in ("flagged", "error"):
                continue  # success (or anything else terminal) -- never re-touch
            if not _edited_since_flag(path, entry):
                continue  # still flagged, still untouched -- don't re-spend on it
            log(f"re-checking previously {status} file (edited since the flag): {path.name}")
        age = now - path.stat().st_mtime
        if age < MIN_FILE_AGE_SECONDS:
            log(f"skip (too fresh, {int(age)}s old, waiting for the scheduled task to finish writing): {path.name}")
            continue
        candidates.append(path)
    return candidates


def _consume_guidance(path):
    """Read + delete the one-shot guidance file for `path`, if the dashboard
    left one. One-shot: read and removed together so it's never re-applied to
    a later, unrelated flag on the same file."""
    gpath = GUIDANCE_DIR / f"{path.name}.txt"
    try:
        text = gpath.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        gpath.unlink()
    except OSError:
        pass
    return text or None


def _git(*args):
    """Run a git command in the website repo; returns CompletedProcess or None."""
    try:
        return subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True,
            timeout=30, creationflags=NO_WINDOW,
        )
    except (subprocess.SubprocessError, OSError) as e:
        log(f"! git {' '.join(args)} failed to run ({e})")
        return None


def git_head():
    proc = _git("rev-parse", "HEAD")
    return proc.stdout.strip() if proc is not None and proc.returncode == 0 else None


def git_publish_evidence(head_before):
    """(committed, pushed, commit) -- what git says happened since `head_before`.

    committed: HEAD moved during the run. pushed: the new HEAD is reachable
    from origin/main (a successful `git push origin master:main` moves that
    ref). Wording in the agent's reply is deliberately not consulted."""
    head_after = git_head()
    if not head_after or not head_before or head_after == head_before:
        return False, False, None
    proc = _git("merge-base", "--is-ancestor", head_after, "origin/main")
    pushed = proc is not None and proc.returncode == 0
    return True, pushed, head_after[:7]


def classify_run(is_error, committed, pushed):
    """(status, reason). Done only when the run committed AND pushed; an errored
    run, a run that committed but never pushed, or one that made no commit
    (the agent stopped to ask a question / offer options) needs Brian."""
    if is_error:
        return "error", "the run reported an error"
    if committed and pushed:
        return "success", "committed and pushed"
    if committed:
        return "flagged", "committed locally but not pushed to origin/main"
    return "flagged", "no commit was made -- the agent stopped without publishing"


_QUESTION_PHRASES_RE = re.compile(
    r"needs? your (?:call|input|decision|ok|ok?ay|approval)|let me know|"
    r"want me to|would you like|do you want|which (?:one|option|do you)|"
    r"\boption\s+(?:[a-c1-3])\b|or would you",
    re.IGNORECASE,
)


def detect_question(text):
    """First sentence in the agent's reply that asks Brian something or offers
    options to choose from, else None. Used even when the run committed and
    pushed: a published article whose reply also needs an answer still needs
    Brian to see it."""
    clean = re.sub(r"`[^`]*`|https?://\S+", " ", text or "")
    for sentence in re.split(r"(?<=[.?!])\s+|\n+", clean):
        s = sentence.strip(" *-•#>")
        if s and ("?" in s or _QUESTION_PHRASES_RE.search(s)):
            return s[:300]
    return None


def decide_run(is_error, committed, pushed, result_text):
    """(status, needs_input, reason). Git decides `status`; a run that did
    commit + push but whose reply also asks a question / offers options is
    still published (status stays success) yet needs_input, with the question
    as the reason."""
    status, reason = classify_run(is_error, committed, pushed)
    needs_input = status != "success"
    if status == "success":
        question = detect_question(result_text)
        if question:
            needs_input, reason = True, f"published, but the agent asked: {question}"
    return status, needs_input, reason


def publish_one(path):
    """Invoke the website-publisher subagent headlessly for a single hand-off file."""
    guidance = _consume_guidance(path)
    prompt = f"Use the website-publisher subagent to publish content-queue-articles/{path.name}."
    if guidance:
        prompt += (
            " Brian directly answered the stop-and-ask flag from the previous run on "
            f"this file -- this is his instruction, act on it: {guidance}"
        )
        log(f"   applying Brian's guidance for {path.name}: {guidance[:300]}")
    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--allowedTools", ALLOWED_TOOLS,
        "--permission-mode", "default",
        "--max-budget-usd", MAX_BUDGET_USD,
        "--no-session-persistence",
    ]
    log(f"-> invoking claude for {path.name}")
    head_before = git_head()
    try:
        proc = subprocess.run(
            cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        log(f"! {path.name}: timed out after {TIMEOUT_SECONDS}s")
        return {"status": "error", "needs_input": True,
                "summary": f"Timed out after {TIMEOUT_SECONDS}s"}

    if proc.returncode != 0:
        stderr_tail = proc.stderr.strip()[-1000:]
        log(f"! {path.name}: claude exited {proc.returncode}\n{stderr_tail}")
        return {"status": "error", "needs_input": True,
                "summary": f"claude exited {proc.returncode}: {stderr_tail[:300]}"}

    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as e:
        log(f"! {path.name}: could not parse claude output ({e})\n{proc.stdout[-1000:]}")
        return {"status": "error", "needs_input": True,
                "summary": f"Unparseable claude output: {proc.stdout[-300:]}"}

    result_text = data.get("result", "") or ""
    log(f"<- {path.name} finished (is_error={data.get('is_error')}, "
        f"cost=${data.get('total_cost_usd', 0):.4f})\n{result_text}")

    denials = data.get("permission_denials") or []
    if denials:
        log(f"! {path.name}: {len(denials)} permission denial(s) -- something outside the "
            f"pre-approved website-publisher commands was attempted and blocked: {denials}")

    urls = URL_RE.findall(result_text)

    # Decide done-vs-needs-input from git, NOT from the agent's wording. The
    # old check required the reply to contain a raw `abc..def master -> main`
    # push line; the agent's prose summary ("committed as `fc48173` and pushed
    # to `main`") never does, so successful publishes were flagged
    # (2026-11-10, Gantzel Road article).
    committed, pushed, commit = git_publish_evidence(head_before)
    status, needs_input, reason = decide_run(
        bool(data.get("is_error")), committed, pushed, result_text)
    if needs_input:
        log(f"   {path.name}: needs input -- {reason}")

    return {
        "status": status,
        "needs_input": needs_input,
        "reason": reason,
        "git_verified": {"committed": committed, "pushed": pushed, "commit": commit},
        "summary": result_text[:1500],
        "url": urls[0] if urls else None,
        "cost_usd": data.get("total_cost_usd"),
        "session_id": data.get("session_id"),
        "permission_denials": len(denials),
    }


REPORT_PDF_REL = "downloads/san_tan_valley_florence_market_report.pdf"


def _is_market_update(path):
    try:
        head = path.read_text(encoding="utf-8")[:300]
    except OSError:
        return False
    return bool(re.search(r"^CONTENT TYPE:\s*Market Update\s*$", head, re.M))


def refresh_market_report(path):
    """After a Market Update page publishes, rebuild the downloadable market
    report PDF from that same hand-off, commit it, and push (added 2026-11-13).

    The PDF is what the lead popup and /resources hand out, so it must never lag
    the monthly page. Failure here never blocks or undoes the page publish -- it
    returns a `flagged` entry so the toast tells Brian the PDF needs attention.
    Only commits/pushes from `master`, the branch this automation's own
    website-publisher pushes from; on any other branch it builds the file and
    leaves committing to Brian rather than push unrelated work to main."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import build_market_report_pdf as report
        pdf, month = report.build(path)
    except Exception as e:  # ReportError or anything unexpected
        log(f"! market report PDF build failed for {path.name}: {e}")
        return {"status": "flagged", "needs_input": True,
                "summary": f"Market page published, but the downloadable PDF was NOT rebuilt: {e}"}
    log(f"   built market report PDF for {month}: {pdf}")

    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.stdout.strip() if branch is not None and branch.returncode == 0 else ""
    if branch != "master":
        log(f"! market report PDF built but repo is on '{branch}', not master -- not committing")
        return {"status": "flagged", "needs_input": True,
                "summary": f"{month} market report PDF built but NOT published: repo is on branch "
                           f"'{branch}'. Commit {REPORT_PDF_REL} and push to main."}

    _git("add", REPORT_PDF_REL)
    changed = _git("diff", "--cached", "--quiet", "--", REPORT_PDF_REL)
    if changed is not None and changed.returncode == 0:
        return {"status": "success", "needs_input": False, "url": None,
                "summary": f"{month} market report PDF already up to date"}
    commit = _git("commit", "-m", f"Update downloadable market report PDF: {month}", "--", REPORT_PDF_REL)
    push = _git("push", "origin", "master:main")
    if commit is None or commit.returncode != 0 or push is None or push.returncode != 0:
        err = (push.stderr if push is not None and push.returncode != 0 else
               commit.stderr if commit is not None else "")[-200:]
        log(f"! market report PDF commit/push failed: {err}")
        return {"status": "flagged", "needs_input": True,
                "summary": f"{month} market report PDF built but commit/push failed: {err}"}
    return {"status": "success", "needs_input": False, "url": None,
            "summary": f"{month} market report PDF rebuilt and published"}


def notify_summary(results):
    try:
        from win11toast import notify
    except ImportError:
        log("! win11toast not installed -- skipping desktop notification. "
            "Run: pip install win11toast")
        return

    def _needs(entry):
        return entry["status"] in ("error", "flagged") or entry.get("needs_input")

    needs_attention = any(_needs(entry) for _, entry in results)
    ordered = sorted(results, key=lambda r: 0 if _needs(r[1]) else 1)

    lines = []
    for filename, entry in ordered:
        if entry["status"] == "error":
            lines.append(f"\u2716 ERROR -- {filename}: {entry['summary'][:200]}")
        elif entry["status"] == "flagged":
            lines.append(f"\u26a0 NEEDS REVIEW -- {filename}: {entry['summary'][:200]}")
        elif entry.get("needs_input"):
            lines.append(f"\u26a0 PUBLISHED, NEEDS YOUR ANSWER -- {filename}: {entry.get('reason', '')[:200]}")
        else:
            lines.append(f"{filename}: published -> {entry['url']}" if entry.get("url")
                         else f"{filename}: {entry.get('summary', 'done')}")

    title = "\u26a0 Butler Website Publisher -- Needs Review" if needs_attention else "Butler Website Publisher"
    body = "\n".join(lines)[:750]
    kwargs = {"scenario": "urgent", "duration": "long"} if needs_attention else {}
    try:
        notify(title, body, **kwargs)
    except Exception as e:
        log(f"! desktop notification failed to fire: {e}")


def count_unpushed_commits():
    """Commits on local master not yet on origin/main.

    website-publisher's spec ends every run with `git push origin master:main`.
    If it built and committed a page but stopped without pushing (e.g. the model
    hesitated on the production push despite the spec), the page is committed
    locally but NOT live. Catch that here rather than letting it sit silently
    until someone notices the article never appeared on the site.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..master"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
            timeout=30, creationflags=NO_WINDOW,
        )
    except (subprocess.SubprocessError, OSError) as e:
        log(f"! could not check for un-pushed commits ({e})")
        return 0
    if proc.returncode != 0:
        log(f"! git rev-list check failed: {proc.stderr.strip()[:200]}")
        return 0
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return 0


def main():
    CONTENT_QUEUE.mkdir(exist_ok=True)
    state = load_state()
    new_files = find_new_files(state)

    if not new_files:
        return  # quiet no-op, per spec -- no log spam, no notification, no claude call

    log(f"=== poll found {len(new_files)} new file(s): {[p.name for p in new_files]} ===")
    results = []
    for path in new_files:
        entry = publish_one(path)
        entry["processed_at"] = datetime.now(timezone.utc).isoformat()
        state["processed"][path.name] = entry
        save_state(state)  # persist after every file so a crash mid-batch can't cause a re-publish
        results.append((path.name, entry))
        if entry["status"] == "success" and _is_market_update(path):
            pdf_entry = refresh_market_report(path)
            pdf_entry["processed_at"] = datetime.now(timezone.utc).isoformat()
            results.append((f"{path.name} (market report PDF)", pdf_entry))

    unpushed = count_unpushed_commits()
    if unpushed:
        log(f"! {unpushed} commit(s) on master NOT pushed to origin/main after this run -- "
            f"website-publisher committed but did not push. The page(s) above are committed "
            f"locally but NOT live. Fix: git push origin master:main")
        results.append((
            "(un-pushed commits)",
            {"status": "flagged",
             "summary": f"{unpushed} commit(s) committed locally but not pushed -- "
                        f"page is NOT live. Run: git push origin master:main"},
        ))

    notify_summary(results)
    log("=== poll complete ===")


if __name__ == "__main__":
    sys.exit(main())
