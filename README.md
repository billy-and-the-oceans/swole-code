# Swole Code

**Micro-workouts while your AI agent works.**

Turn vibe coding wait times into gains. When [Claude Code](https://github.com/anthropics/claude-code) launches a longer task (research, tests, builds), Swole Code prompts you with a quick exercise. Log your reps when the task completes.

We're shaving years off our lives watching spinning wheels. Might as well do some squats.

## How It Works

**1. Task starts → Exercise prompt appears:**

<img width="400" alt="Exercise prompt dialog" src="https://github.com/user-attachments/assets/placeholder-start.png">

**2. Task ends → Confirmation dialog:**

<img width="400" alt="Confirmation dialog" src="https://github.com/user-attachments/assets/placeholder-end.png">

**3. Track your gains:**

```
swole
```

Opens a TUI dashboard showing today's stats and recent history.

## Requirements

- macOS (uses native dialogs)
- [Claude Code](https://github.com/anthropics/claude-code)
- Python 3.8+
- [Rich](https://github.com/Textualize/rich) (`pip install rich`) - for the TUI dashboard

## Install

```bash
git clone https://github.com/billy-and-the-oceans/swole-code.git
cd swole-code
./install.sh
```

The installer will:
1. Copy hooks to `~/.claude/hooks/swole-code/`
2. Print the config to add to `~/.claude/settings.json`

Then add to your shell profile:
```bash
alias swole='~/.claude/hooks/swole-code/swole.py'
```

## What Triggers Swole Code?

**Agent tasks:**
- `Explore` agents (codebase research)
- `Plan` agents (architecture planning)
- Background tasks
- Prompts containing: "research", "analyze", "comprehensive", "investigate"

**Bash commands:**
- `npm test`, `yarn test`, `pytest`, `cargo test`, `go test`
- `cargo build`, `npm run build`, `docker build`, `make`

## Configuration

Run `swole config` or press `c` in the dashboard:

| Option | Description |
|--------|-------------|
| **Enable/Disable** | Turn Swole Code on/off globally |
| **Categories** | Toggle legs, upper, cardio, core |
| **Cooldown** | Minutes between prompts (default: 10) |
| **Quiet Hours** | No prompts during set hours (e.g., 22:00-08:00) |
| **Custom Exercises** | Add your own exercises |

## Workout Log

Completions are logged to:
- **SQLite**: `~/.swole-code/data.db`
- **Markdown**: `~/.swole-code/log.md`

```markdown
## 2026-02-03
- [x] 14:23 - **10 airsquats** [legs] (during: "Research auth patterns")
- [x] 15:47 - **10 pushups** [upper] (during: "npm test")
```

## Contributing

PRs welcome! Some ideas:
- Linux support (notifications)
- Windows support
- More exercises
- Streak tracking / achievements
- Health app integrations

## License

MIT

---

*Get swole while you code.*
