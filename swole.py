#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import random
import argparse
import datetime
from pathlib import Path

# --- Configuration ---
SWOLE_DIR = Path(os.environ.get("SWOLE_CODE_DIR", Path.home() / ".swole-code"))
DB_PATH = SWOLE_DIR / "data.db"
LOG_FILE = SWOLE_DIR / "log.md"
PENDING_FILE = SWOLE_DIR / "pending.json"
CONFIG_FILE = SWOLE_DIR / "config.json"
EXERCISES_FILE = Path(__file__).parent / "exercises.json"

DEFAULT_CONFIG = {
    "enabled": True,
    "cooldown_minutes": 30,
    "categories": {
        "legs": True,
        "upper": True,
        "cardio": True,
        "core": True
    },
    "custom_exercises": [],
    "quiet_hours": {
        "enabled": False,
        "start": "22:00",
        "end": "08:00"
    }
}

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
            # Merge with defaults for any missing keys
            config = DEFAULT_CONFIG.copy()
            config.update(saved)
            return config
    return DEFAULT_CONFIG.copy()

def save_config(config):
    SWOLE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def is_quiet_time(config):
    if not config["quiet_hours"]["enabled"]:
        return False
    now = datetime.datetime.now().time()
    start = datetime.datetime.strptime(config["quiet_hours"]["start"], "%H:%M").time()
    end = datetime.datetime.strptime(config["quiet_hours"]["end"], "%H:%M").time()
    # Handle overnight ranges (e.g., 22:00 - 08:00)
    if start > end:
        return now >= start or now <= end
    return start <= now <= end

# --- Rich Integration ---
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.layout import Layout
    from rich.text import Text
    from rich.align import Align
    from rich.prompt import Prompt, Confirm
    from rich import box
    RICH_AVAILABLE = True
    console = Console(stderr=True) # Default to stderr for prompts to avoid pipe issues
except ImportError:
    RICH_AVAILABLE = False
    console = None

# --- Database ---
def get_db():
    SWOLE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        count INTEGER,
        unit TEXT,
        category TEXT,
        task_description TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed BOOLEAN
    )''')
    conn.commit()
    conn.close()

# --- Helpers ---
def load_exercises():
    if not EXERCISES_FILE.exists():
        return []
    with open(EXERCISES_FILE) as f:
        data = json.load(f)
        return data.get("exercises", [])

def get_recent_exercises(limit=5):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, count, unit, category, task_description, timestamp FROM exercises WHERE completed = 1 ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_stats_today():
    conn = get_db()
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute("SELECT name, count, unit, category FROM exercises WHERE completed = 1 AND date(timestamp) = ?", (today,))
    rows = c.fetchall()
    conn.close()
    
    stats = {
        "total_reps": 0,
        "exercises": len(rows),
        "by_category": {}
    }
    
    for r in rows:
        stats["total_reps"] += r['count']
        cat = r['category']
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + r['count']
        
    return stats

def update_markdown_log(exercise_name, count, unit, category, task_desc):
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w") as f:
            f.write("# Swole Code Workout Log\n\nTrack your vibe coding workouts.\n\n---\n")
            
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    header = f"## {today_str}"
    
    lines = []
    if LOG_FILE.exists():
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        
    has_header = any(header in l for l in lines)
    
    with open(LOG_FILE, "a") as f:
        if not has_header:
            f.write(f"\n{header}\n\n")
        
        timestamp = datetime.datetime.now().strftime("%H:%M")
        exercise_str = f"{count} {unit} {exercise_name}" if unit != "reps" else f"{count} {exercise_name}"
        f.write(f"- [x] {timestamp} - **{exercise_str}** [{category}] (during: \"{task_desc}\")\n")

# --- Commands ---

def cmd_suggest(args):
    config = load_config()

    # Check if enabled
    if not config.get("enabled", True):
        return

    # Check quiet hours
    if is_quiet_time(config):
        return

    # Check cooldown (don't suggest if we suggested recently)
    cooldown = config.get("cooldown_minutes", 30)
    last_suggested_file = SWOLE_DIR / "last_suggested"
    if last_suggested_file.exists():
        last_time = datetime.datetime.fromisoformat(last_suggested_file.read_text().strip())
        if (datetime.datetime.now() - last_time).total_seconds() < cooldown * 60:
            return

    exercises = load_exercises()

    # Add custom exercises from config
    custom = config.get("custom_exercises", [])
    exercises = exercises + custom

    if not exercises:
        return

    # Filter by enabled categories
    enabled_cats = [cat for cat, enabled in config.get("categories", {}).items() if enabled]
    if enabled_cats:
        exercises = [e for e in exercises if e.get("category", "general") in enabled_cats]

    if not exercises:
        return

    recent_rows = get_recent_exercises(3)
    recent_names = [r['name'] for r in recent_rows]

    available = [e for e in exercises if e['name'] not in recent_names]
    if not available:
        available = exercises

    choice = random.choice(available)
    count = choice['count']
    unit = choice.get('unit', 'reps')
    name = choice['name']
    
    text = f"{count} {unit} {name}" if unit != "reps" else f"{count} {name}"
    
    pending_data = {
        "exercise": text,
        "data": choice,
        "suggested_at": datetime.datetime.now().isoformat()
    }
    
    if args.task:
        pending_data["task_description"] = args.task

    with open(PENDING_FILE, "w") as f:
        json.dump(pending_data, f)

    # Save last suggested time for cooldown
    last_suggested_file = SWOLE_DIR / "last_suggested"
    last_suggested_file.write_text(datetime.datetime.now().isoformat())

    print(text)

def cmd_confirm(args):
    if not PENDING_FILE.exists():
        return

    with open(PENDING_FILE) as f:
        pending = json.load(f)

    exercise_text = pending['exercise']
    task_desc = pending.get('task_description', 'Unknown task')
    data = pending['data']

    if RICH_AVAILABLE:
        panel = Panel(
            Align.center(
                f"[bold white]Did you do[/] [bold green]{exercise_text}[/]?\n\n"
                f"[dim]Task: {task_desc}[/]"
            ),
            title="[bold cyan]SWOLE CODE[/]",
            border_style="cyan",
            padding=(1, 2)
        )
        console.print(panel)

        response = Prompt.ask("Confirm?", choices=["y", "n", "skip"], default="y", console=console)
        confirmed = (response == "y")
    else:
        # Fallback
        print(f"SWOLE CODE: Did you do {exercise_text}? [y/n]", file=sys.stderr)
        response = input().strip().lower()
        confirmed = (response == 'y')

    if confirmed:
        log_exercise(data, task_desc)
    else:
        if RICH_AVAILABLE:
            console.print("[yellow]Skipped.[/]")
        else:
            print("Skipped.")

    if PENDING_FILE.exists():
        os.remove(PENDING_FILE)

def log_exercise(data, task_desc):
    """Log a completed exercise to DB and markdown."""
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO exercises (name, count, unit, category, task_description, completed) VALUES (?, ?, ?, ?, ?, ?)",
              (data['name'], data['count'], data.get('unit', 'reps'), data.get('category', 'general'), task_desc, True))
    conn.commit()
    conn.close()

    update_markdown_log(data['name'], data['count'], data.get('unit', 'reps'), data.get('category', 'general'), task_desc)

def cmd_log_complete(args):
    """Non-interactive: log the pending exercise as complete."""
    if not PENDING_FILE.exists():
        return

    with open(PENDING_FILE) as f:
        pending = json.load(f)

    data = pending['data']
    task_desc = pending.get('task_description', 'Unknown task')

    log_exercise(data, task_desc)

    # macOS notification for feedback
    stats = get_stats_today()
    os.system(f'''osascript -e 'display notification "Today: {stats["total_reps"]} reps" with title "Swole Code" subtitle "Logged!"' ''')

    if PENDING_FILE.exists():
        os.remove(PENDING_FILE)

def cmd_log_skip(args):
    """Non-interactive: skip the pending exercise."""
    if PENDING_FILE.exists():
        os.remove(PENDING_FILE)

# --- TUI Dashboard ---
def render_dashboard():
    if not RICH_AVAILABLE:
        print("Rich library not installed. Cannot render TUI.")
        return

    # Clear screen
    console.clear()
    
    # Layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    
    # Header
    title = Text("SWOLE CODE", style="bold cyan")
    layout["header"].update(Panel(Align.center(title), style="cyan"))
    
    # Stats
    stats = get_stats_today()
    stats_table = Table(title="Today's Gains", box=box.SIMPLE)
    stats_table.add_column("Category", style="cyan")
    stats_table.add_column("Count", justify="right", style="green")
    
    for cat, count in stats['by_category'].items():
        stats_table.add_row(cat.title(), str(count))
        
    stats_table.add_section()
    stats_table.add_row("Total Reps", str(stats['total_reps']), style="bold white")

    # Recent Log
    recent = get_recent_exercises(5)
    log_table = Table(title="Recent Activity", box=box.SIMPLE)
    log_table.add_column("Time", style="dim")
    log_table.add_column("Exercise", style="white")
    log_table.add_column("Task", style="dim")
    
    for r in recent:
        dt = datetime.datetime.fromisoformat(r['timestamp'])
        time_str = dt.strftime("%H:%M")
        desc = (r['task_description'][:20] + '..') if len(r['task_description']) > 20 else r['task_description']
        exercise = f"{r['count']} {r['unit']} {r['name']}"
        log_table.add_row(time_str, exercise, desc)

    # Body Split
    layout["body"].split_row(
        Layout(Panel(stats_table, title="Stats", border_style="blue")),
        Layout(Panel(log_table, title="History", border_style="blue"))
    )
    
    # Footer
    layout["footer"].update(Align.center("[bold]q[/] Quit  [bold]c[/] Config  [bold]r[/] Refresh", vertical="middle"))
    
    console.print(layout)

def render_config():
    """Render the config screen."""
    config = load_config()

    console.clear()

    # Header
    header = Panel(
        Align.center(Text("SWOLE CODE CONFIG", style="bold magenta")),
        style="magenta"
    )
    console.print(header)
    console.print()

    # Main toggle
    status = "[bold green]ON[/]" if config["enabled"] else "[bold red]OFF[/]"
    console.print(f"  [1] Swole Code: {status}")
    console.print()

    # Categories
    console.print("  [bold]Categories:[/]")
    cats = config.get("categories", {})
    for i, (cat, enabled) in enumerate(cats.items(), start=2):
        check = "[green]✓[/]" if enabled else "[red]✗[/]"
        console.print(f"    [{i}] {check} {cat.title()}")
    console.print()

    # Cooldown
    cooldown = config.get("cooldown_minutes", 10)
    console.print(f"  [6] Cooldown: [cyan]{cooldown}[/] minutes between prompts")
    console.print()

    # Quiet hours
    qh = config.get("quiet_hours", {})
    qh_status = "[green]ON[/]" if qh.get("enabled") else "[dim]OFF[/]"
    console.print(f"  [7] Quiet hours: {qh_status} ({qh.get('start', '22:00')} - {qh.get('end', '08:00')})")
    console.print()

    # Custom exercises
    custom = config.get("custom_exercises", [])
    console.print(f"  [8] Custom exercises: [cyan]{len(custom)}[/] defined")
    console.print()

    console.print("  [bold dim]───────────────────────────────[/]")
    console.print("  [s] Save & Back  [b] Back (discard)")
    console.print()

    return config

def config_loop():
    """Interactive config editor."""
    if not RICH_AVAILABLE:
        print("Config requires 'rich' library.")
        return

    config = load_config()
    modified = False

    while True:
        console.clear()

        # Header
        header = Panel(
            Align.center(Text("SWOLE CODE CONFIG", style="bold magenta")),
            style="magenta"
        )
        console.print(header)
        console.print()

        # Main toggle
        status = "[bold green]ON[/]" if config["enabled"] else "[bold red]OFF[/]"
        console.print(f"  [bold white]1[/] Swole Code: {status}")
        console.print()

        # Categories
        console.print("  [bold]Categories:[/]")
        cats = config.get("categories", {})
        cat_keys = list(cats.keys())
        for i, cat in enumerate(cat_keys):
            enabled = cats[cat]
            check = "[green]✓[/]" if enabled else "[red]✗[/]"
            console.print(f"    [bold white]{i+2}[/] {check} {cat.title()}")
        console.print()

        # Cooldown
        cooldown = config.get("cooldown_minutes", 10)
        console.print(f"  [bold white]6[/] Cooldown: [cyan]{cooldown}[/] min")
        console.print()

        # Quiet hours
        qh = config.get("quiet_hours", {})
        qh_status = "[green]ON[/]" if qh.get("enabled") else "[dim]OFF[/]"
        console.print(f"  [bold white]7[/] Quiet hours: {qh_status} ({qh.get('start', '22:00')}-{qh.get('end', '08:00')})")
        console.print()

        # Custom exercises
        custom = config.get("custom_exercises", [])
        console.print(f"  [bold white]8[/] Custom exercises: [cyan]{len(custom)}[/]")
        console.print()

        console.print("  [dim]───────────────────────────────[/]")
        mod_marker = "[yellow]*[/] " if modified else ""
        console.print(f"  {mod_marker}[bold white]s[/] Save  [bold white]b[/] Back")
        console.print()

        choice = Prompt.ask("Option", console=console)

        if choice == "1":
            config["enabled"] = not config["enabled"]
            modified = True
        elif choice in ["2", "3", "4", "5"]:
            idx = int(choice) - 2
            if idx < len(cat_keys):
                cat = cat_keys[idx]
                config["categories"][cat] = not config["categories"][cat]
                modified = True
        elif choice == "6":
            try:
                new_cd = Prompt.ask("Cooldown (minutes)", default=str(cooldown), console=console)
                config["cooldown_minutes"] = int(new_cd)
                modified = True
            except ValueError:
                pass
        elif choice == "7":
            # Toggle quiet hours or edit times
            qh = config.get("quiet_hours", {"enabled": False, "start": "22:00", "end": "08:00"})
            sub = Prompt.ask("Toggle [t] or Edit times [e]?", choices=["t", "e"], default="t", console=console)
            if sub == "t":
                qh["enabled"] = not qh["enabled"]
            else:
                qh["start"] = Prompt.ask("Start time (HH:MM)", default=qh.get("start", "22:00"), console=console)
                qh["end"] = Prompt.ask("End time (HH:MM)", default=qh.get("end", "08:00"), console=console)
            config["quiet_hours"] = qh
            modified = True
        elif choice == "8":
            # Custom exercises submenu
            custom_exercises_menu(config)
            modified = True
        elif choice.lower() == "s":
            save_config(config)
            console.print("[green]Config saved![/]")
            import time
            time.sleep(0.5)
            break
        elif choice.lower() == "b":
            if modified:
                if Confirm.ask("Discard changes?", console=console):
                    break
            else:
                break

def custom_exercises_menu(config):
    """Submenu for managing custom exercises."""
    while True:
        console.clear()
        console.print(Panel(Align.center(Text("CUSTOM EXERCISES", style="bold cyan")), style="cyan"))
        console.print()

        custom = config.get("custom_exercises", [])
        if custom:
            for i, ex in enumerate(custom, 1):
                unit = ex.get("unit", "reps")
                console.print(f"  [{i}] {ex['count']} {unit} {ex['name']} [{ex.get('category', 'general')}]")
        else:
            console.print("  [dim]No custom exercises yet.[/]")

        console.print()
        console.print("  [a] Add  [d] Delete  [b] Back")
        console.print()

        choice = Prompt.ask("Option", console=console)

        if choice.lower() == "a":
            name = Prompt.ask("Exercise name", console=console)
            count = int(Prompt.ask("Count", default="10", console=console))
            unit = Prompt.ask("Unit", choices=["reps", "seconds"], default="reps", console=console)
            category = Prompt.ask("Category", choices=["legs", "upper", "cardio", "core"], default="general", console=console)
            custom.append({"name": name, "count": count, "unit": unit, "category": category})
            config["custom_exercises"] = custom
        elif choice.lower() == "d":
            if custom:
                idx = Prompt.ask("Delete which? (number)", console=console)
                try:
                    del custom[int(idx) - 1]
                    config["custom_exercises"] = custom
                except (ValueError, IndexError):
                    pass
        elif choice.lower() == "b":
            break

def tui_loop():
    if not RICH_AVAILABLE:
        print("TUI requires 'rich' library.")
        return

    while True:
        render_dashboard()
        action = Prompt.ask("", choices=["q", "c", "r"], show_choices=False, console=console)

        if action == "q":
            break
        elif action == "c":
            config_loop()
        elif action == "r":
            continue

def cmd_tui(args):
    tui_loop()

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    
    p_suggest = subparsers.add_parser('suggest')
    p_suggest.add_argument('--task', help='Task description')
    
    p_confirm = subparsers.add_parser('confirm')
    
    p_status = subparsers.add_parser('status')

    p_tui = subparsers.add_parser('tui')

    p_config = subparsers.add_parser('config')

    p_log_complete = subparsers.add_parser('log-complete')
    p_log_skip = subparsers.add_parser('log-skip')
    
    args = parser.parse_args()
    
    init_db()
    
    if args.command == 'suggest':
        cmd_suggest(args)
    elif args.command == 'confirm':
        cmd_confirm(args)
    elif args.command == 'status':
        # If rich is available, show the TUI (one-shot), else plain text
        if RICH_AVAILABLE:
            tui_loop() # Or just render_dashboard() once? TUI loop implies interaction. 
                       # Let's default 'swole status' to one-shot TUI render if no TUI command used.
                       # But user asked for "/swole" to open TUI.
            pass
        else:
            # Fallback status
            stats = get_stats_today()
            print(f"Today's Reps: {stats['total_reps']}")
    elif args.command == 'tui':
        tui_loop()
    elif args.command == 'config':
        if RICH_AVAILABLE:
            config_loop()
        else:
            print("Config requires 'rich' library.")
    elif args.command == 'log-complete':
        cmd_log_complete(args)
    elif args.command == 'log-skip':
        cmd_log_skip(args)
    else:
        # Default to TUI if no args
        if len(sys.argv) == 1:
            if RICH_AVAILABLE:
                tui_loop()
            else:
                parser.print_help()
        else:
            parser.print_help()

if __name__ == "__main__":
    main()