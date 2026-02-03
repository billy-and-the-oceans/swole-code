#!/bin/bash
# Swole Code - Pre-task hook
# Suggests exercise when launching longer tasks

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

if [ "$TOOL_NAME" = "Task" ]; then
  SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // ""')
  PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // ""')
  DESCRIPTION=$(echo "$INPUT" | jq -r '.tool_input.description // ""')
  RUN_BG=$(echo "$INPUT" | jq -r '.tool_input.run_in_background // false')

  # High confidence: Explore, Plan, or background tasks
  if [[ "$SUBAGENT_TYPE" =~ ^(Explore|Plan|general-purpose)$ ]] || [ "$RUN_BG" = "true" ]; then
    IS_SWOLE_WORTHY=true
  fi

  # Check prompt for keywords
  if echo "$PROMPT $DESCRIPTION" | grep -iE "research|analyze|comprehensive|deep.?dive|investigate|thorough" > /dev/null 2>&1; then
    IS_SWOLE_WORTHY=true
  fi

elif [ "$TOOL_NAME" = "Bash" ]; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

  # Check for build/test commands
  if echo "$COMMAND" | grep -E "(npm test|pytest|cargo (build|test)|make|docker build|yarn test|go test)" > /dev/null 2>&1; then
    IS_SWOLE_WORTHY=true
    DESCRIPTION="$COMMAND"
  fi
fi

# Skip if not swole-worthy or if there's already a pending exercise
if [ "$IS_SWOLE_WORTHY" = false ]; then
  exit 0
fi

if [ -f "$SWOLE_DIR/pending.json" ]; then
  # Check if pending is stale (> 10 minutes old)
  if [ "$(find "$SWOLE_DIR/pending.json" -mmin -10 2>/dev/null)" ]; then
    exit 0
  fi
fi

# Pick a random exercise using swole.py
EXERCISE_TEXT=$("$SCRIPT_DIR/swole.py" suggest --task "$DESCRIPTION")

if [ -z "$EXERCISE_TEXT" ]; then
  exit 0
fi

# Show macOS dialog with Skip option (runs in background)
(
RESPONSE=$(osascript <<EOF
display dialog "Time to move!

$EXERCISE_TEXT" with title "SWOLE CODE" buttons {"Skip", "Let's go!"} default button 2 giving up after 10
EOF
)

# If skipped or timed out, remove pending.json so no confirmation dialog appears
if echo "$RESPONSE" | grep -q "Skip"; then
  rm -f "$SWOLE_DIR/pending.json"
elif echo "$RESPONSE" | grep -q "gave up:true"; then
  rm -f "$SWOLE_DIR/pending.json"
fi
) &

exit 0
