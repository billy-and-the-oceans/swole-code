#!/bin/bash
# Swole Code - Post-task hook
# Reminds user to log their exercise (non-blocking notification)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SWOLE_DIR="${SWOLE_CODE_DIR:-$HOME/.swole-code}"
PENDING_FILE="$SWOLE_DIR/pending.json"

# Check if there's a pending exercise
if [ ! -f "$PENDING_FILE" ]; then
  exit 0
fi

# Check if pending is fresh (within last 15 minutes)
if [ ! "$(find "$PENDING_FILE" -mmin -15 2>/dev/null)" ]; then
  # Stale pending, clean up
  rm -f "$PENDING_FILE"
  exit 0
fi

# Read pending exercise
EXERCISE=$(jq -r '.exercise' "$PENDING_FILE" 2>/dev/null)
COUNT=$(jq -r '.count // ""' "$PENDING_FILE" 2>/dev/null)
NAME=$(jq -r '.name // ""' "$PENDING_FILE" 2>/dev/null)

if [ -z "$EXERCISE" ]; then
  exit 0
fi

# Show completion reminder notification (non-blocking)
osascript -e "display notification \"Did you do $EXERCISE? Run 'swole' to log it!\" with title \"SWOLE CODE\" subtitle \"Task complete!\" sound name \"Pop\""

exit 0
