# Swole Code

**Micro-workouts while your AI agent works.**

Turn vibe coding wait times into gains. When [Claude Code](https://github.com/anthropics/claude-code) launches a longer task (research, tests, builds), Swole Code prompts you with a quick exercise. Log your reps when the task completes.

We're shaving years off our lives watching spinning wheels. Might as well do some squats.

## The Insight

Developers resist breaks because they fear momentum loss. Swole Code solves this with **assured progress**: if you *know* meaningful work continues while you exercise, the resistance evaporates.

## How It Works

**1. Task starts → Exercise prompt appears:**

<img width="1024" height="1024" alt="Exercise prompt" src="https://github.com/user-attachments/assets/74839be1-5c84-49e6-83a7-55bb32a53282" />

**2. Task ends → Confirmation dialog:**

<img width="1024" height="1024" alt="Confirmation" src="https://github.com/user-attachments/assets/fbe2e878-34f6-44f6-9bfa-c7dd19555d3d" />

**3. Track your gains:**

```
swole
```

Opens a TUI dashboard with today's stats, recent history, and access to all features.

## Features

### Exercises (Snacks)
Quick movements during short waits:
- **45 exercises** built-in across legs, upper, cardio, core, mobility
- **Morning Park** movements: horse stance, body waves, Cossack squats
- **Equipment-aware**: kettlebell, pull-up bar, resistance bands
- **Intensity levels**: gentle, moderate, intense

### Routines (Meals)
Structured sessions for longer autonomous work:
- **HIIT**, Pilates, Barre, Yoga, Kettlebell flows
- **YouTube integration**: save favorite workout videos
- **Custom routines**: add your own with duration and intensity

### Weekly Patterns
Schedule your workout focus:
- **Freestyle**: random selection
- **Upper/Lower Split**: alternate focus days
- **Push/Pull/Legs**: classic 3-way split
- **Daily Mobility + Intensity**: light movement daily, one hard session
- **Morning Park Daily**: gentle movements every day

### Routine Matching
For longer autonomous tasks, browse routines matched to your available time:
- 2-5 min: "Two Minute Reset", "Eye Reset"
- 5-10 min: "Posture Reset", "Quick Pump", "Standing Flow"
- 10-20 min: YouTube video workouts from popular creators
- 20+ min: Full HIIT, strength, or yoga sessions

## Requirements

- macOS (uses native notifications)
- [Claude Code](https://github.com/anthropics/claude-code)
- Python 3.8+
- [Rich](https://github.com/Textualize/rich) (`pip install rich`) - for the TUI

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

## Commands

| Command | Description |
|---------|-------------|
| `swole` | Open TUI dashboard (stats, log, config, history) |
| `swole suggest --task "desc"` | Get exercise suggestion for a task |
| `swole log-complete` | Log pending exercise as completed |
| `swole log-skip` | Clear pending exercise without logging |

## Configuration

Run `swole setup` on first run, or `swole config` anytime:

| Option | Description |
|--------|-------------|
| **Equipment** | What you have (kettlebell, pull-up bar, etc.) |
| **Intensity** | Gentle / Moderate / Intense / Mixed |
| **Weekly Pattern** | How to structure your week |
| **Categories** | Toggle legs, upper, cardio, core, mobility |
| **Cooldown** | Minutes between prompts (default: 30) |
| **Quiet Hours** | No prompts during set hours |
| **Custom Exercises** | Add your own movements |

## What Triggers Swole Code?

**Agent tasks:**
- `Explore` agents (codebase research)
- `Plan` agents (architecture planning)
- Background tasks
- Prompts containing: "research", "analyze", "comprehensive", "investigate"

**Bash commands:**
- `npm test`, `yarn test`, `pytest`, `cargo test`, `go test`
- `cargo build`, `npm run build`, `docker build`, `make`

## Workout Log

Completions are logged to:
- **SQLite**: `~/.swole-code/data.db`
- **Markdown**: `~/.swole-code/log.md`

```markdown
## 2026-02-04
- [x] 14:23 - **10 airsquats** [legs] (moderate) (during: "Research auth patterns")
- [x] 15:47 - **Horse Stance Flow** [morning_park] (10 min) (during: "npm test")
```

## Exercise Categories

| Category | Examples |
|----------|----------|
| **Legs** | Squats, lunges, calf raises, horse stance |
| **Upper** | Pushups, tricep dips, pull-ups |
| **Cardio** | Jumping jacks, high knees, burpees |
| **Core** | Plank, dead bug, bird dog |
| **Mobility** | Hip circles, wrist circles, cat-cow |

## Intensity Levels

| Level | Description | Examples |
|-------|-------------|----------|
| **Gentle** | Morning park vibes, joint-friendly | Horse stance, body waves, wrist circles |
| **Moderate** | Real work, sustainable | Pushups, squats, kettlebell swings |
| **Intense** | Heart rate up, sweat likely | Burpees, jump squats, mountain climbers |

## YouTube Creators

The TUI includes links to great workout channels:
- **Caroline Girvan** - HIIT, strength, kettlebell
- **Blogilates** - Pilates, barre
- **Yoga With Adriene** - Yoga, mobility
- **GMB Fitness** - Movement quality
- **Tom Merrick** - Deep flexibility

## Contributing

PRs welcome! Some ideas:
- Linux support (notifications)
- Windows support
- More exercises and routines
- Streak tracking / achievements
- Health app integrations
- Integration with Claude's upcoming swarm capabilities

## License

MIT

---

*Get swole while you code.*
