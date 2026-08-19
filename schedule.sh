#!/usr/bin/env bash
# Run ssbot automatically on this Mac via launchd (macOS's cron).
#
#   ./schedule.sh install [minutes]   schedule it (default: every 15 minutes)
#   ./schedule.sh status              is it loaded? when did it last run?
#   ./schedule.sh logs                tail the log
#   ./schedule.sh uninstall           stop and remove the schedule
#   ./schedule.sh print [minutes]     print the plist without installing
#
# Why launchd and not Apps Script: ss.com drops traffic from datacenter IP
# ranges, so Google's servers cannot reach it. This Mac can. See README.md.
set -euo pipefail

cd "$(dirname "$0")"
DIR="$(pwd)"
LABEL="com.ssbot.watcher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# NOT $DIR/ssbot.log: macOS sandboxes xpcproxy (launchd's spawn helper) out of
# ~/Desktop, ~/Documents and ~/Downloads, and that block can't be lifted with a
# permission grant — xpcproxy itself is never eligible for Full Disk Access.
# If the project lives on Desktop and the log redirect target does too, every
# unattended launch fails at spawn time (posix_spawn error 0x1, exit 78) even
# though running the same command by hand works fine. Full Disk Access on the
# Python interpreter is still needed and still helps — it's what lets the
# script itself read .env/searches.py and write seen_listings.json once it's
# actually running — it just can't rescue xpcproxy's own setup step.
mkdir -p "$HOME/Library/Logs"
LOG="$HOME/Library/Logs/ssbot.log"

PYTHON="$DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

ACTION="${1:-}"
MINUTES="${2:-15}"

if ! [[ "$MINUTES" =~ ^[0-9]+$ ]] || [ "$MINUTES" -lt 1 ] || [ "$MINUTES" -gt 60 ]; then
  echo "Interval must be a whole number of minutes between 1 and 60 (got '$MINUTES')." >&2
  exit 1
fi
if [ $((60 % MINUTES)) -ne 0 ]; then
  echo "Interval must divide 60 evenly, so the schedule repeats cleanly every hour." >&2
  echo "Allowed: 1 2 3 4 5 6 10 12 15 20 30 60" >&2
  exit 1
fi

# StartCalendarInterval, not StartInterval. Per launchd.plist(5), a StartInterval
# firing that falls while the Mac is asleep "will be missed"; a calendar firing
# instead runs once on wake, coalescing however many were missed. That is the
# behaviour you want for a listing watcher on a laptop.
render_calendar_entries() {
  local minute=0
  while [ "$minute" -lt 60 ]; do
    printf '\t\t<dict><key>Minute</key><integer>%d</integer></dict>\n' "$minute"
    minute=$((minute + MINUTES))
  done
}

render_plist() {
  cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>$PYTHON</string>
		<string>$DIR/parser.py</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$DIR</string>
	<key>StartCalendarInterval</key>
	<array>
$(render_calendar_entries)
	</array>
	<key>RunAtLoad</key>
	<true/>
	<key>StandardOutPath</key>
	<string>$LOG</string>
	<key>StandardErrorPath</key>
	<string>$LOG</string>
	<key>ProcessType</key>
	<string>Background</string>
</dict>
</plist>
PLIST
}

case "$ACTION" in
  print)
    render_plist
    ;;

  install)
    if [ ! -f "$DIR/.env" ]; then
      echo "No .env found. Run: cp .env.example .env  and fill it in first." >&2
      exit 1
    fi
    mkdir -p "$HOME/Library/LaunchAgents"
    render_plist > "$PLIST"
    plutil -lint "$PLIST" >/dev/null

    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"

    echo "Installed: $LABEL runs every $MINUTES minute(s)."
    echo "  python:  $PYTHON"
    echo "  log:     $LOG"
    echo "  plist:   $PLIST"
    echo
    echo "It runs once immediately. Check with: ./schedule.sh logs"
    ;;

  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed $LABEL. The log at $LOG is left in place."
    ;;

  status)
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "Loaded."
      launchctl print "gui/$(id -u)/$LABEL" \
        | grep -E "state|last exit code|runs|program|interval" | sed 's/^[[:space:]]*/  /'
    else
      echo "Not loaded. Install it with: ./schedule.sh install"
    fi
    [ -f "$LOG" ] && echo && echo "Last log line: $(tail -1 "$LOG")"
    ;;

  logs)
    [ -f "$LOG" ] || { echo "No log yet at $LOG"; exit 0; }
    tail -f "$LOG"
    ;;

  *)
    sed -n '2,10p' "$0" | cut -c3-
    exit 1
    ;;
esac
