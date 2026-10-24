#!/bin/sh
set -eu
REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
STATE_DIR=${USA_FEED_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/usa-network-feed-watch}
mkdir -p "$STATE_DIR"
python3 "$REPO_DIR/monitor.py" --repo "$REPO_DIR" --state "$STATE_DIR/state.json" --apply

if ! git -C "$REPO_DIR" diff --quiet -- us-filtered-houston.m3u usa-feed-watchlist.md; then
    git -C "$REPO_DIR" config user.name "usa-feed-watch"
    git -C "$REPO_DIR" config user.email "usa-feed-watch@localhost"
    git -C "$REPO_DIR" add us-filtered-houston.m3u usa-feed-watchlist.md
    git -C "$REPO_DIR" commit -m "Restore verified USA feed"
    if [ -n "${GIT_SSH_KEY:-}" ] && [ -f "$GIT_SSH_KEY" ]; then
        GIT_SSH_COMMAND="ssh -i $GIT_SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git -C "$REPO_DIR" push origin HEAD
    else
        git -C "$REPO_DIR" push origin HEAD
    fi
fi
