#!/bin/bash
# Swole Code - Post-task hook
# macOS native dialog for exercise confirmation

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SWOLE_DIR="${SWOLE_CODE_DIR:-$HOME/.swole-code}"
PENDING_FILE="$SWOLE_DIR/pending.json"

# Check if there's a pending exercise
if [ ! -f "$PENDING_FILE" ]; then
  exit 0
fi

# Read pending exercise
EXERCISE=$(jq -r '.exercise' "$PENDING_FILE")
TASK_DESC=$(jq -r '.task_description // "task"' "$PENDING_FILE")

# Show macOS dialog (non-blocking, runs in background)
(
  RESPONSE=$(osascript -e "display dialog \"SWOLE CODE\n\nDid you do $EXERCISE?\" buttons {\"Skip\", \"Done!\"} default button \"Done!\" with title \"Swole Code\" giving up after 30" 2>/dev/null)

  if echo "$RESPONSE" | grep -q "Done!"; then
    "$SCRIPT_DIR/swole.py" log-complete
  else
    "$SCRIPT_DIR/swole.py" log-skip
  fi
) &

exit 0
