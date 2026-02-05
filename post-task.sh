#!/bin/bash
# Swole Code - Post-task hook (SubagentStop)
# Reminds user to log their exercise if they accepted one

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SWOLE_DIR="${SWOLE_CODE_DIR:-$HOME/.swole-code}"
PENDING_FILE="$SWOLE_DIR/pending.json"
SUGGESTION_FILE="$SWOLE_DIR/suggestion.json"

# Clean up stale suggestion (user didn't accept)
if [ -f "$SUGGESTION_FILE" ]; then
  # If suggestion is older than 15 minutes, remove it
  if [ ! "$(find "$SUGGESTION_FILE" -mmin -15 2>/dev/null)" ]; then
    rm -f "$SUGGESTION_FILE"
  fi
fi

# Check if user accepted an exercise (pending.json exists)
if [ ! -f "$PENDING_FILE" ]; then
  exit 0
fi

# Check if pending is fresh (within last 30 minutes)
if [ ! "$(find "$PENDING_FILE" -mmin -30 2>/dev/null)" ]; then
  # Stale pending, clean up
  rm -f "$PENDING_FILE"
  exit 0
fi

# Read pending exercise
EXERCISE=$(jq -r '.exercise // "your exercise"' "$PENDING_FILE" 2>/dev/null)

if [ -z "$EXERCISE" ] || [ "$EXERCISE" = "null" ]; then
  exit 0
fi

# Show interactive completion notification
# Clicking logs the exercise, dismissing skips it
if command -v terminal-notifier &> /dev/null; then
  terminal-notifier \
    -title "SWOLE CODE" \
    -subtitle "Click to log, close to skip" \
    -message "$EXERCISE" \
    -sound Pop \
    -group "swole-complete" \
    -sender com.apple.Terminal \
    -execute "$HOME/.local/bin/swole log-complete"
else
  osascript -e "display notification \"Did you do $EXERCISE? Run 'swole' to log it!\" with title \"SWOLE CODE\" subtitle \"Task complete!\" sound name \"Pop\""
fi

exit 0
