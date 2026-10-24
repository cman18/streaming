#!/usr/bin/env python3
"""Low-cost USA Network feed monitor and conservative playlist updater."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


@dataclass
class FeedResult:
    ok: bool
    status: int = 0
    detail: str = ""
    resolution: str = ""


def parse_watchlist(path: Path) -> list[tuple[str, str]]:
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and cells[1].startswith(("http://", "https://")):
            results.append((cells[0], cells[1]))
    return results


def fetch(url: str, timeout: float = 12.0) -> tuple[int, bytes, str]:
    request = Request(url, headers={"User-Agent": "usa-feed-watch/1.0", "Accept": "application/vnd.apple.mpegurl,*/*"})
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read(512 * 1024), response.headers.get("Content-Type", "")


def validate_hls(url: str, timeout: float = 12.0, retries: int = 2) -> FeedResult:
    last = "request failed"
    for attempt in range(retries + 1):
        try:
            status, body, _ = fetch(url, timeout)
            text = body.decode("utf-8", errors="replace")
            if status != 200 or "#EXTM3U" not in text:
                return FeedResult(False, status, "not an HLS manifest")
            media = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
            if not media:
                return FeedResult(False, status, "manifest has no media or child playlist")
            target = urljoin(url, media[0])
            segment_status, segment, _ = fetch(target, timeout)
            if segment_status != 200 or not segment:
                return FeedResult(False, status, "first media reference unavailable")
            resolution = ""
            match = re.search(r"RESOLUTION=(\d+x\d+)", text)
            if match:
                resolution = match.group(1)
            return FeedResult(True, status, "manifest and first reference verified", resolution)
        except Exception as exc:  # network conditions are expected during polling
            last = str(exc)
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    return FeedResult(False, 0, last)


def confirm_recovery(history: dict, result: FeedResult, required: int = 2) -> bool:
    return result.ok and int(history.get("successes", 0)) >= required


def _usa_number(label: str) -> int | None:
    match = re.search(r"USA\s+(\d+)", label, re.I)
    return int(match.group(1)) if match else None


def restore_feed(path: Path, label: str, url: str, number: int) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    if url in lines:
        return False
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF"):
            continue
        number_match = re.search(r'(?:tvg-chno|channel-number)="?' + str(number) + r'"?', line)
        if number_match and index + 1 < len(lines):
            lines[index] = line.rsplit(",", 1)[0] + "," + label
            lines[index + 1] = url
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
    insert_at = 1
    for index, line in enumerate(lines):
        if line.startswith("#EXTINF") and "USA " in line:
            insert_at = index + 2
    entry = [f'#EXTINF:-1 group-title="Sports" tvg-chno="{number}" channel-number="{number}",{label}', url]
    path.write_text("\n".join(lines[:insert_at] + entry + lines[insert_at:]) + "\n", encoding="utf-8")
    return True


def mark_watchlist_restored(path: Path, label: str, when: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("|") and label in line and "restored" not in line.lower():
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            cells.append(f"Restored {when[:10]}")
            lines[index] = "| " + " | ".join(cells) + " |"
    if lines:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(repo: Path, state_path: Path, apply_changes: bool = False, timeout: float = 12.0) -> int:
    watchlist = parse_watchlist(repo / "usa-feed-watchlist.md")
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"feeds": {}}
    changes = []
    now = datetime.now(timezone.utc).isoformat()
    for label, url in watchlist:
        item = state["feeds"].setdefault(url, {"label": label, "successes": 0, "failures": 0, "checks": []})
        result = validate_hls(url, timeout=timeout)
        if result.ok:
            item["successes"] = int(item.get("successes", 0)) + 1
            item["failures"] = 0
        else:
            item["successes"] = 0
            item["failures"] = int(item.get("failures", 0)) + 1
        item["last_status"] = "ok" if result.ok else "failed"
        item["last_checked"] = now
        item["checks"] = (item.get("checks", []) + [{"time": now, **asdict(result)}])[-20:]
        if confirm_recovery(item, result):
            number = _usa_number(label)
            if apply_changes and number is not None and restore_feed(repo / "us-filtered-houston.m3u", label, url, number):
                mark_watchlist_restored(repo / "usa-feed-watchlist.md", label, now)
                changes.append(label)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"checked": len(watchlist), "restored": changes, "state": str(state_path)}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).parent)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()
    state = args.state or args.repo / ".usa-feed-watch-state.json"
    return run(args.repo, state, args.apply, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
