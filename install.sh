#!/bin/bash
# Swole Code installer

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$HOME/.claude/hooks/swole-code"
SWOLE_DIR="$HOME/.swole-code"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo "Installing Swole Code..."
echo ""

# Create directories
mkdir -p "$HOOKS_DIR"
mkdir -p "$SWOLE_DIR"

# Copy hook scripts
cp "$SCRIPT_DIR/pre-task.sh" "$HOOKS_DIR/"
cp "$SCRIPT_DIR/post-task.sh" "$HOOKS_DIR/"
cp "$SCRIPT_DIR/exercises.json" "$HOOKS_DIR/"
cp "$SCRIPT_DIR/swole.py" "$HOOKS_DIR/"

# Make executable
chmod +x "$HOOKS_DIR/pre-task.sh"
chmod +x "$HOOKS_DIR/post-task.sh"
chmod +x "$HOOKS_DIR/swole.py"

echo "Hooks installed to: $HOOKS_DIR"
echo "Data directory: $SWOLE_DIR"
echo ""

# Check if settings.json exists
if [ -f "$SETTINGS_FILE" ]; then
  echo "Found existing settings.json"
  echo ""
  echo "Add this to your hooks configuration:"
else
  echo "Create $SETTINGS_FILE with:"
fi

cat << 'CONFIG'

{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/swole-code/pre-task.sh"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/swole-code/pre-task.sh"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/swole-code/post-task.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/swole-code/post-task.sh"
          }
        ]
      }
    ]
  }
}

CONFIG

echo ""
echo "Installation complete!"
echo ""
echo "To use the CLI stats dashboard, add this alias to your shell profile:"
echo "alias swole='$HOOKS_DIR/swole.py'"
echo ""
echo "Customize exercises: $HOOKS_DIR/exercises.json"
echo "View workout log: $SWOLE_DIR/log.md"
echo ""
echo "Get swole while you code."
