#!/bin/bash
# Swole Code - Pre-task hook
# Suggests exercise when launching longer tasks (non-blocking notification)

set -e

SWOLE_DIR="${SWOLE_CODE_DIR:-$HOME/.swole-code}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$SWOLE_DIR"

# Read hook input
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')

# Check if this is a swole-worthy task
IS_SWOLE_WORTHY=false
TASK_TYPE=""

if [ "$TOOL_NAME" = "Task" ]; then
  SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // ""')
  PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // ""')
  DESCRIPTION=$(echo "$INPUT" | jq -r '.tool_input.description // ""')
  RUN_BG=$(echo "$INPUT" | jq -r '.tool_input.run_in_background // false')

  # High confidence: Explore, Plan, or background tasks
  if [[ "$SUBAGENT_TYPE" =~ ^(Explore|Plan|general-purpose)$ ]] || [ "$RUN_BG" = "true" ]; then
    IS_SWOLE_WORTHY=true
    TASK_TYPE="$SUBAGENT_TYPE"
  fi

  # Check prompt for keywords
  if echo "$PROMPT $DESCRIPTION" | grep -iE "research|analyze|comprehensive|deep.?dive|investigate|thorough" > /dev/null 2>&1; then
    IS_SWOLE_WORTHY=true
    TASK_TYPE="research"
  fi

elif [ "$TOOL_NAME" = "Bash" ]; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

  # Check for build/test commands
  if echo "$COMMAND" | grep -E "(npm test|pytest|cargo (build|test)|make|docker build|yarn test|go test|mvn|gradle|flutter build|xcodebuild)" > /dev/null 2>&1; then
    IS_SWOLE_WORTHY=true
    TASK_TYPE="build/test"
    DESCRIPTION="$COMMAND"
  fi
fi

# Skip if not swole-worthy or if there's already a pending exercise
if [ "$IS_SWOLE_WORTHY" = false ]; then
  exit 0
fi

# Check if this big task should trigger queued workout
DAY_FILE="$SWOLE_DIR/day.json"
if [ -f "$DAY_FILE" ]; then
  QUEUED=$(jq -r '.workout_queue.queued // false' "$DAY_FILE")
  TRIGGER=$(jq -r '.workout_queue.trigger // ""' "$DAY_FILE")
  TRIGGERED_AT=$(jq -r '.workout_queue.triggered_at // null' "$DAY_FILE")

  # Trigger if queued for big_task and not yet triggered today
  if [ "$QUEUED" = "true" ] && [ "$TRIGGER" = "big_task" ] && [ "$TRIGGERED_AT" = "null" ]; then
    "$SCRIPT_DIR/swole.py" queue --trigger
    exit 0  # Don't also suggest snack
  fi
fi

if [ -f "$SWOLE_DIR/pending.json" ]; then
  # Check if pending is stale (> 10 minutes old)
  if [ "$(find "$SWOLE_DIR/pending.json" -mmin -10 2>/dev/null)" ]; then
    exit 0
  fi
fi

# Check quiet hours
CONFIG_FILE="$SWOLE_DIR/config.json"
if [ -f "$CONFIG_FILE" ]; then
  QUIET_ENABLED=$(jq -r '.quiet_hours.enabled // false' "$CONFIG_FILE")
  if [ "$QUIET_ENABLED" = "true" ]; then
    QUIET_START=$(jq -r '.quiet_hours.start // "22:00"' "$CONFIG_FILE")
    QUIET_END=$(jq -r '.quiet_hours.end // "08:00"' "$CONFIG_FILE")

    # Get current time as minutes since midnight
    CURRENT_HOUR=$(date +%H)
    CURRENT_MIN=$(date +%M)
    NOW_MINS=$((10#$CURRENT_HOUR * 60 + 10#$CURRENT_MIN))

    # Parse start/end times
    START_HOUR=${QUIET_START%%:*}
    START_MIN=${QUIET_START##*:}
    START_MINS=$((10#$START_HOUR * 60 + 10#$START_MIN))

    END_HOUR=${QUIET_END%%:*}
    END_MIN=${QUIET_END##*:}
    END_MINS=$((10#$END_HOUR * 60 + 10#$END_MIN))

    # Check if in quiet period (handles midnight crossing)
    if [ "$START_MINS" -gt "$END_MINS" ]; then
      # Spans midnight (e.g., 22:00 to 08:00)
      if [ "$NOW_MINS" -ge "$START_MINS" ] || [ "$NOW_MINS" -lt "$END_MINS" ]; then
        exit 0
      fi
    else
      # Same day (e.g., 09:00 to 17:00)
      if [ "$NOW_MINS" -ge "$START_MINS" ] && [ "$NOW_MINS" -lt "$END_MINS" ]; then
        exit 0
      fi
    fi
  fi
fi

# Check cooldown (uses same file as Python's suggest command)
COOLDOWN_FILE="$SWOLE_DIR/last_suggested"
if [ -f "$COOLDOWN_FILE" ]; then
  # Python writes ISO format, we need to compare timestamps
  LAST_TIME_ISO=$(cat "$COOLDOWN_FILE")
  # Convert ISO to epoch seconds (macOS date command)
  LAST_TIME=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${LAST_TIME_ISO%%.*}" +%s 2>/dev/null || echo 0)
  NOW=$(date +%s)
  DIFF=$((NOW - LAST_TIME))
  # 10 minute cooldown between notifications
  if [ "$DIFF" -lt 600 ]; then
    exit 0
  fi
fi

# Pick a random exercise using swole.py
EXERCISE_TEXT=$("$SCRIPT_DIR/swole.py" suggest --task "$DESCRIPTION" 2>/dev/null)

if [ -z "$EXERCISE_TEXT" ]; then
  exit 0
fi

# Note: Python's suggest command already updates the cooldown file (last_suggested)
# so we don't need to write it here

# Show macOS notification (non-blocking, doesn't steal focus)
if command -v terminal-notifier &> /dev/null; then
  terminal-notifier -title "SWOLE CODE" -subtitle "Time to move!" -message "$EXERCISE_TEXT" -sound Glass
else
  osascript -e "display notification \"$EXERCISE_TEXT\" with title \"SWOLE CODE\" subtitle \"Time to move!\" sound name \"Glass\""
fi

exit 0
