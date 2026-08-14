#!/usr/bin/env python3
"""
Cursor IDE log scanner — extracts user prompts from Cursor agent transcripts.

Source: C:\\Users\\<user>\\.cursor\\projects\\<project-id>\\agent-transcripts\\<conv-id>\\<conv-id>.jsonl

Each transcript line is a JSON object. Emits one log entry per user message.

Usage:
  python scripts/log_cursor.py --auto            # default: last 24h
  python scripts/log_cursor.py --hours 168      # 7 days
  python scripts/log_cursor.py --all             # every conversation
  python scripts/log_cursor.py --dry-run         # preview only
  python scripts/log_cursor.py --project-path "C:\\Users\\ngant\\.cursor\\projects\\c-Users-ngant-P-086"

Env overrides:
  CURSOR_PROJECTS_DIR    parent of project folders (default: ~/.cursor/projects)
  AI_LOG_DIR             where session.jsonl is written (default: .ai-log)
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VN_TZ = timezone(timedelta(hours=7))


def _git(cmd: str) -> str:
    import subprocess
    try:
        return subprocess.check_output(
            cmd.split(), shell=False, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def _normalize(p: str) -> str:
    if not p:
        return ""
    return os.path.normpath(p.strip().lower()).replace("\\", "/").rstrip("/")


def get_logged_entry_ids(log_file: Path) -> set[str]:
    logged: set[str] = set()
    if not log_file.exists():
        return logged
    with open(log_file, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                eid = entry.get("entry_id", "")
                if eid:
                    logged.add(eid)
            except json.JSONDecodeError:
                continue
    return logged


def parse_timestamp(raw_text: str, mtime) -> str:
    """Extract timestamp from raw prompt text. Returns isoformat VN time."""
    import re
    # Cursor embeds: <timestamp>Tuesday, Aug 11, 2026, 12:15 PM (UTC+7)</timestamp>
    m = re.search(r"<timestamp>([^<]+)</timestamp>", raw_text)
    if m:
        ts_str = m.group(1).strip()
        try:
            # "Tuesday, Aug 11, 2026, 12:15 PM (UTC+7)"
            parsed = datetime.strptime(ts_str, "%A, %b %d, %Y, %I:%M %p (UTC+7)")
            return parsed.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return mtime.strftime("%Y-%m-%dT%H:%M:%S")


def extract_user_prompt(content) -> tuple[str, str]:
    """Extract clean text and raw text from various content formats.
    Returns (clean_prompt, raw_text_for_ts_parse)."""
    if not content:
        return "", ""
    if isinstance(content, str):
        raw = content
        clean = _strip_cursor_tags(content).strip()
        return clean, raw
    if isinstance(content, list):
        parts = []
        raw_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    t = item.get("text", "")
                    parts.append(t)
                    raw_parts.append(t)
                elif item.get("type") == "image":
                    parts.append("[image]")
                    raw_parts.append("[image]")
            elif isinstance(item, str):
                parts.append(item)
                raw_parts.append(item)
        raw = " ".join(raw_parts)
        clean = _strip_cursor_tags(" ".join(parts)).strip()
        return clean, raw
    raw = str(content)
    return _strip_cursor_tags(raw).strip(), raw


def _strip_cursor_tags(text: str) -> str:
    """Remove <timestamp>...</timestamp> and <user_query>...</user_query> wrappers."""
    import re
    text = re.sub(r"<timestamp>[^<]*</timestamp>\s*", "", text)
    text = re.sub(r"</?user_query>\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<image_files>[^<]*</image_files>\s*", "[image] ", text)
    return text.strip()


def iter_cursor_conversations(project_dir: Path, cutoff: datetime | None,
                               only_conv: str | None, repo_root_n: str):
    """Yield user-input dicts from Cursor agent transcripts."""
    transcripts_dir = project_dir / "agent-transcripts"
    if not transcripts_dir.exists():
        return

    for conv_dir in sorted(transcripts_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not conv_dir.is_dir():
            continue
        if only_conv and conv_dir.name != only_conv:
            continue

        # Find the transcript file (usually <uuid>.jsonl)
        transcript = None
        for f in conv_dir.iterdir():
            if f.suffix == ".jsonl" and f.stem == conv_dir.name:
                transcript = f
                break
        if not transcript or not transcript.exists() or transcript.stat().st_size == 0:
            continue

        # Check timestamp
        mtime = datetime.fromtimestamp(transcript.stat().st_mtime, tz=VN_TZ)
        if cutoff and mtime < cutoff:
            continue

        entries = []
        try:
            with open(transcript, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except OSError:
            continue

        # Extract user messages
        for i, entry in enumerate(entries):
            # Cursor format: role="user"
            role = entry.get("role", "")
            if role != "user":
                continue

            content = entry.get("message", {}).get("content", "")
            clean_prompt, raw_text = extract_user_prompt(content)
            if len(clean_prompt) < 2:
                continue

            ts = entry.get("timestamp", "")
            if not ts:
                ts = mtime.isoformat()

            yield {
                "conv_id": conv_dir.name,
                "msg_index": i,
                "timestamp": ts,
                "ts_parsed": parse_timestamp(raw_text, mtime),
                "text": clean_prompt[:5000],
            }


def build_entry(msg: dict, repo: str, branch: str, commit: str,
                student: str, project_id: str) -> dict:
    # Use parsed timestamp from prompt text for accuracy
    ts = msg.get("ts_parsed", "") or datetime.now(VN_TZ).strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "ts": ts,
        "tool": "cursor",
        "event": "UserPrompt",
        "entry_id": f"cursor-{msg['conv_id']}-{msg['msg_index']:05d}",
        "session_id": msg["conv_id"],
        "project_id": project_id,
        "model": "cursor",
        "repo": repo,
        "branch": branch,
        "commit": commit,
        "student": student,
        "prompt": msg["text"],
        "response_summary": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract user prompts from Cursor IDE agent transcripts "
                    "into .ai-log/session.jsonl."
    )
    parser.add_argument("--auto", action="store_true",
                        help="Default mode: scan recent conversations.")
    parser.add_argument("--hours", type=int, default=24,
                        help="Window in hours (default: 24).")
    parser.add_argument("--all", action="store_true",
                        help="Ignore the time window; scan everything.")
    parser.add_argument("--conv-id",
                        help="Limit to a single conversation id.")
    parser.add_argument("--project-path",
                        help="Cursor project directory (auto-detected if omitted).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be logged, don't write.")
    args = parser.parse_args()

    # Find project dir - match by repo name in transcript content
    if args.project_path:
        project_dir = Path(args.project_path)
    else:
        cwd = Path.cwd()
        cursor_projects = Path.home() / ".cursor" / "projects"
        project_dir = None
        
        if cursor_projects.exists():
            for proj in cursor_projects.iterdir():
                if not proj.is_dir():
                    continue
                transcripts_dir = proj / "agent-transcripts"
                if not transcripts_dir.exists():
                    continue
                # Check if any transcript mentions current repo name
                for conv_dir in transcripts_dir.iterdir():
                    if not conv_dir.is_dir():
                        continue
                    for f in conv_dir.iterdir():
                        if f.suffix == ".jsonl" and f.stem == conv_dir.name:
                            try:
                                content = f.read_text(encoding="utf-8", errors="ignore")[:2000]
                                # Look for repo/project identifiers in path
                                if any(x in content for x in [cwd.name.lower(), str(cwd).replace("\\", "/")]):
                                    project_dir = proj
                                    break
                            except Exception:
                                pass
                    if project_dir:
                        break
                if project_dir:
                    break
        
        if not project_dir:
            # Fallback: construct expected path
            user = os.environ.get("USERNAME", "ngant")
            project_dir = cursor_projects / f"c-Users-{user}-{cwd.name}"

    if not project_dir.exists():
        print(f"[cursor-log] Project dir not found: {project_dir}", file=sys.stderr)
        sys.exit(0)

    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "session.jsonl"
    logged_ids = get_logged_entry_ids(log_file)

    cutoff = None
    if not args.all:
        cutoff = datetime.now(tz=VN_TZ) - timedelta(hours=args.hours)

    repo = _git("git remote get-url origin").split("/")[-1].replace(".git", "") if _git("git remote get-url origin") else ""
    branch = _git("git rev-parse --abbrev-ref HEAD") or "unknown"
    commit = _git("git rev-parse --short HEAD") or "unknown"
    student = _git("git config user.email") or os.environ.get("USERNAME", os.environ.get("USER", "unknown"))

    project_id = project_dir.name
    repo_root_n = _normalize(str(Path.cwd()))

    new_entries: list[dict] = []
    for msg in iter_cursor_conversations(project_dir, cutoff, args.conv_id, repo_root_n):
        entry = build_entry(msg, repo or Path.cwd().name, branch, commit, student, project_id)
        if entry["entry_id"] in logged_ids:
            continue
        new_entries.append(entry)
        logged_ids.add(entry["entry_id"])

    if not new_entries:
        scope = "all" if args.all else f"{args.hours}h"
        print(f"[cursor-log] No new prompts (project={project_id}, window={scope}).",
              file=sys.stderr)
        sys.exit(0)

    if args.dry_run:
        print(f"\n[cursor-log] DRY RUN — would log {len(new_entries)} entries:\n")
        for e in new_entries:
            preview = e["prompt"].replace("\n", " ")[:120]
            print(f"  [{e['ts'][:19]}] {preview}")
        sys.exit(0)

    with open(log_file, "a", encoding="utf-8") as f:
        for e in new_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"[cursor-log] Logged {len(new_entries)} prompt(s) from Cursor IDE "
          f"(project={project_id}).", file=sys.stderr)


if __name__ == "__main__":
    main()
