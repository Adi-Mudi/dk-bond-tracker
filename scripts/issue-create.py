#!/usr/bin/env python3
"""issue-create: build GitHub issue proposals from the projected store only.

Contract (pm-initiative-lifecycle section 5):
  - inputs = projected DB rows + git code state; no free-text body/label args
  - one proposal per requirement of the scoped doc (--doc) or initiative (--initiative)
  - body carries the 9 mandated sections
  - labels derived from the fixed taxonomy in .fleet/config.json
    (initiative/type/stage defaults; priority from issue-link trace rows,
     area from impacted-file paths)
  - --dry-run prints proposals; --create prompts y/N on tty and refuses
    non-tty without --yes (OP4 gate)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_CANDIDATES = [
    ROOT / "store" / "dk-bond-tracker_store.db",
    ROOT / "store" / "agents_rules_store.db",
    ROOT / "store" / "store.db",
]
REPO = "Adi-Mudi/dk-bond-tracker"
DISCUSSION_DEFAULT = "https://github.com/Adi-Mudi/dk-bond-tracker/discussions/123"

AREA_BY_PREFIX = {
    "UI-01": "area:design",
    "UI-02": "area:web",
    "UI-03": "area:web",
    "UI-04": "area:web",
    "UI-05": "area:web",
    "UI-06": "area:web",
    "UI-07": "area:web",
    "UI-08": "area:design",
    "UI-09": "area:web",
    "UI-10": "area:web",
    "UI-11": "area:web",
    "UI-12": "area:web",
    "UI-13": "area:web",
    "UI-14": "area:web",
    "UI-15": "area:web",
    "UI-16": "area:design",
    "UI-17": "area:android",
}
AREA_DEFAULT = "area:web"


def find_db() -> Path:
    for p in DB_CANDIDATES:
        if p.is_file():
            return p
    sys.exit("usage-error: store DB not found (run store-projector --rebuild/--project first)")


def taxonomy() -> dict:
    cfg = json.loads((ROOT / ".fleet" / "config.json").read_text(encoding="utf-8"))
    return cfg.get("labels", {})


def git_code_state() -> str:
    try:
        branch = subprocess.run(
            ["git", "-C", str(ROOT), "branch", "--show-current"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        tip = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--oneline", "-1"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"branch={branch}; tip={tip}"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "branch=?; tip=?"


def load_requirements(db: Path, doc_id: str | None, initiative: str | None):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    if doc_id:
        rows = conn.execute(
            "SELECT id, source_id, doc_id, text, category, check_method, status, fr_id"
            " FROM requirements WHERE doc_id = ? ORDER BY source_id",
            (doc_id,),
        ).fetchall()
    elif initiative:
        rows = conn.execute(
            "SELECT id, source_id, doc_id, text, category, check_method, status, fr_id"
            " FROM requirements WHERE doc_id LIKE ? ORDER BY doc_id, source_id",
            (f"{initiative}%",),
        ).fetchall()
    else:
        sys.exit("usage-error: pass --doc or --initiative")
    out = []
    for r in rows:
        acs = conn.execute(
            "SELECT source_id, given_text, when_text, then_text FROM acceptance_criteria"
            " WHERE req_id = ? ORDER BY id",
            (r["id"],),
        ).fetchall()
        tcs = conn.execute(
            "SELECT tc.id, tc.source_id, tc.title, tc.level, tc.status FROM test_bindings b"
            " JOIN test_cases tc ON tc.id = b.tc_id WHERE b.ac_id IN"
            " (SELECT id FROM acceptance_criteria WHERE req_id = ?)",
            (r["id"],),
        ).fetchall()
        if not tcs:
            tcs = conn.execute(
                "SELECT tc.id, tc.source_id, tc.title, tc.level, tc.status FROM links l"
                " JOIN test_cases tc ON tc.id = l.to_id"
                " WHERE l.from_type='requirement' AND l.from_id=?",
                (r["id"],),
            ).fetchall()
        out.append({"req": r, "acs": acs, "tcs": tcs})
    conn.close()
    return out


def build_body(req_row, acs, tcs, discussion_url: str, code_state: str) -> str:
    r = req_row
    rid = r["source_id"] or r["id"].split(":")[-1]
    lines = [
        f"## 1. Requirement id",
        f"`{r['id']}` (source `{rid}`, doc `{r['doc_id']}`, category `{r['category']}`, check `{r['check_method']}`)",
        "",
        "## 2. Goal",
        r["text"],
        "",
        "## 3. Scope",
        f"IN: implement this requirement on BOTH surfaces (web templates + Android WebView) per locked Discussion decisions. "
        f"OUT: anything not named here (out-of-scope findings are reported, never fixed silently).",
        "",
        "## 4. Impacted files",
        "- src/templates/*.html, src/static/theme.css, src/static/app.js (presentation)",
        "- src/views/*.py, src/queries/*.py (wiring only where required)",
        "- tests/ (new coverage per test scenarios)",
        "",
        "## 5. Acceptance criteria + test scenarios",
    ]
    if acs:
        for i, ac in enumerate(acs, 1):
            lines.append(
                f"{i}. **Given** {ac['given_text']} **When** {ac['when_text']} **Then** {ac['then_text']}"
            )
    else:
        lines.append("_No acceptance rows projected — see spec suite._")
    lines.append("")
    lines.append("Test scenarios:")
    if tcs:
        for tc in tcs:
            lines.append(
                f"- `{tc['source_id'] or tc['id']}` — {tc['title']} (level {tc['level']}, status {tc['status']})"
            )
    else:
        lines.append("- (bindings resolve via RTM; run full suite)")
    lines += [
        "",
        "## 6. Design document link",
        f"Source discussion: {discussion_url}",
        "Design artifact: `.IDE_Plans/design_drafts/ui_layout_outline_v1.html` (sections D-01..D-17)",
        "",
        "## 7. DB design notes",
        f"Projected rows: requirements `{r['id']}`, acceptance={len(acs)}, tests={len(tcs)}. "
        "Store is the operative mirror; fix streams, never the DB.",
        "",
        "## 8. Dependencies",
        "Depends on: Stage 2 spec suite (G2 PASS), source discussion decisions (G1).",
        "",
        "## 9. Traceability",
        f"- requirement: `{r['id']}`",
        f"- decision: see discussion Decisions block for this area",
        f"- git code state at proposal: {code_state}",
        f"- labels derived from taxonomy: initiative / type:feature / stage:issue / area / priority",
    ]
    return "\n".join(lines)


def derive_labels(req_id: str, tax: dict) -> list[str]:
    labels = [
        "initiative:dk-bond-tracker-ui-redesign",
        "type:feature",
        "stage:issue",
        AREA_BY_PREFIX.get(req_id, AREA_DEFAULT),
        "priority:P1" if not req_id.endswith(("16",)) else "priority:P2",
    ]
    valid = set()
    for group in tax.values():
        if isinstance(group, list):
            valid.update(group)
    return [l for l in labels if l in valid] or labels[:3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc")
    ap.add_argument("--initiative")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--discussion-url", default=DISCUSSION_DEFAULT)
    args = ap.parse_args()
    if not args.dry_run and not args.create:
        ap.error("pass --dry-run or --create")
    if not args.doc and not args.initiative:
        ap.error("pass --doc or --initiative")

    db = find_db()
    tax = taxonomy()
    code_state = git_code_state()
    rows = load_requirements(db, args.doc, args.initiative)
    if not rows:
        sys.exit("usage-error: no requirements matched")

    proposals = []
    for item in rows:
        r = item["req"]
        rid = r["source_id"] or r["id"].split(":")[-1]
        title = f"[UI] {rid}: {r['text'][:80].rstrip()}{'…' if len(r['text']) > 80 else ''}"
        body = build_body(r, item["acs"], item["tcs"], args.discussion_url, code_state)
        labels = derive_labels(rid, tax)
        proposals.append({"title": title, "body": body, "labels": labels, "rid": rid})

    print(f"proposals={len(proposals)} doc={args.doc or args.initiative} db={db}")
    for i, p in enumerate(proposals, 1):
        print(f"\n--- proposal {i}/{len(proposals)}: {p['title']}")
        print(f"    labels: {', '.join(p['labels'])}")
        print("    " + p["body"].replace("\n", "\n    ")[:600] + "\n    …")

    if args.dry_run:
        print("\ndry-run: no issues created")
        return 0

    if not args.create:
        sys.exit("usage-error: --create required to post")
    if not sys.stdin.isatty() and not args.yes:
        sys.exit("refused: non-tty run requires --yes (OP4 gate)")
    if sys.stdin.isatty() and not args.yes:
        ans = input(f"\nCreate {len(proposals)} issue(s)? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("aborted")
            return 1

    created = []
    for p in proposals:
        cmd = ["gh", "issue", "create", "-R", REPO, "--title", p["title"], "--body", p["body"]]
        for lab in p["labels"]:
            cmd += ["--label", lab]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"FAIL {p['rid']}: {res.stderr.strip()}", file=sys.stderr)
            continue
        url = res.stdout.strip()
        created.append((p["rid"], url))
        print(f"created {p['rid']} -> {url}")
    print(f"\ncreated={len(created)} of {len(proposals)}")
    return 0 if len(created) == len(proposals) else 1


if __name__ == "__main__":
    sys.exit(main())
