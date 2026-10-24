# USA feed monitoring

`monitor.py` performs routine checks without an AI invocation. It reads the archived candidates in `usa-feed-watchlist.md`, retrieves each HLS manifest, verifies that the manifest contains a media/child-playlist reference, and retrieves the first referenced object. A candidate must pass two consecutive checks before it is eligible for restoration.

State is written outside the repository by `scripts/run-usa-monitor.sh` (under `$XDG_STATE_HOME/usa-network-feed-watch`, or `$HOME/.local/state/usa-network-feed-watch`). The state file records recent checks, timestamps, HTTP status, and validation details.

## Run once

```sh
python3 monitor.py --repo . --state /path/to/state.json
```

Add `--apply` to restore a confirmed candidate into the existing USA channel number. The operation is idempotent and does not remove active feeds after failures.

## Scheduling

The wrapper is suitable for ordinary cron or a systemd timer on the host that owns the persistent checkout:

```cron
*/15 * * * * /absolute/path/to/repository/scripts/run-usa-monitor.sh >> /absolute/path/to/usa-feed-monitor.log 2>&1
```

The monitor only changes files after two successful checks. Git commit/push remains a separate explicit deployment step so a scheduler cannot silently publish changes from an unreviewed checkout.

## Verification

```sh
python3 -m unittest -v tests/test_monitor.py
python3 -m py_compile monitor.py
```
