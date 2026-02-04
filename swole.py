#!/usr/bin/env python3
"""
SWOLE CODE - Micro-workouts while your AI agent works.

Interactive CLI with arrow-key navigation, inspired by Claude Code.
"""

import os
import sys
import json
import sqlite3
import random
import argparse
import datetime
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable

# --- Configuration ---
SWOLE_DIR = Path(os.environ.get("SWOLE_CODE_DIR", Path.home() / ".swole-code"))
DB_PATH = SWOLE_DIR / "data.db"
LOG_FILE = SWOLE_DIR / "log.md"
PENDING_FILE = SWOLE_DIR / "pending.json"
CONFIG_FILE = SWOLE_DIR / "config.json"
DAY_FILE = SWOLE_DIR / "day.json"
EXERCISES_FILE = Path(__file__).parent / "exercises.json"
ROUTINES_DEFAULTS_FILE = Path(__file__).parent / "routines.json"

DEFAULT_CONFIG = {
    "enabled": True,
    "cooldown_minutes": 30,
    "theme": "fire",  # fire, rainbow, ocean, matrix, mono
    "categories": {
        "legs": True, "upper": True, "cardio": True,
        "core": True, "mobility": True, "full": True
    },
    "intensity_preference": "mixed",
    "equipment": ["none"],
    "weekly_pattern": "freestyle",
    "custom_exercises": [],
    "custom_routines": [],
    "quiet_hours": {"enabled": False, "start": "22:00", "end": "08:00"}
}

# --- Try to import prompt_toolkit for interactive UI ---
try:
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, FormattedTextControl
    from prompt_toolkit.layout.dimension import D
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML, ANSI, FormattedText
    from prompt_toolkit.widgets import Frame, Label, Box
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

# Fallback to Rich for simple output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

# --- Data Loading ---

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(saved)
            return config
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    SWOLE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def load_routines_data() -> dict:
    if ROUTINES_DEFAULTS_FILE.exists():
        with open(ROUTINES_DEFAULTS_FILE) as f:
            return json.load(f)
    return {"routine_types": [], "equipment_types": [], "weekly_patterns": [], "sample_routines": []}

def load_exercises() -> List[dict]:
    if not EXERCISES_FILE.exists():
        return []
    with open(EXERCISES_FILE) as f:
        data = json.load(f)
        return data.get("exercises", [])


# --- Day State Management ---

DEFAULT_DAY_STATE = {
    "date": None,
    "morning": {
        "status": "pending",
        "completed_at": None,
        "routine_used": None
    },
    "workout_queue": {
        "queued": False,
        "routine_id": None,
        "routine_name": None,
        "duration_minutes": None,
        "trigger": None,
        "trigger_description": None,
        "queued_at": None,
        "triggered_at": None
    },
    "deep_work_start": None
}


def load_day_state() -> dict:
    """Load day state, resetting if it's a new day."""
    SWOLE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()

    if DAY_FILE.exists():
        with open(DAY_FILE) as f:
            state = json.load(f)
        # Reset if new day
        if state.get("date") != today:
            state = reset_day_if_needed(state)
    else:
        state = DEFAULT_DAY_STATE.copy()
        state["date"] = today
        save_day_state(state)

    return state


def save_day_state(state: dict):
    """Save day state to file."""
    SWOLE_DIR.mkdir(parents=True, exist_ok=True)
    with open(DAY_FILE, "w") as f:
        json.dump(state, f, indent=2)


def reset_day_if_needed(state: dict) -> dict:
    """Reset day state for a new day while preserving any useful data."""
    today = datetime.date.today().isoformat()
    new_state = {
        "date": today,
        "morning": {
            "status": "pending",
            "completed_at": None,
            "routine_used": None
        },
        "workout_queue": {
            "queued": False,
            "routine_id": None,
            "routine_name": None,
            "duration_minutes": None,
            "trigger": None,
            "trigger_description": None,
            "queued_at": None,
            "triggered_at": None
        },
        "deep_work_start": None
    }
    save_day_state(new_state)
    return new_state


def get_day_of_week() -> str:
    return datetime.datetime.now().strftime("%A").lower()

def get_todays_focus(config: dict) -> Optional[List[str]]:
    routines_data = load_routines_data()
    pattern_id = config.get("weekly_pattern", "freestyle")
    for pattern in routines_data.get("weekly_patterns", []):
        if pattern["id"] == pattern_id:
            schedule = pattern.get("schedule")
            if schedule:
                return schedule.get(get_day_of_week(), [])
    return None

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
        name TEXT, count INTEGER, unit TEXT, category TEXT, intensity TEXT,
        task_description TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, completed BOOLEAN
    )''')
    c.execute("PRAGMA table_info(exercises)")
    columns = [col[1] for col in c.fetchall()]
    if 'intensity' not in columns:
        c.execute("ALTER TABLE exercises ADD COLUMN intensity TEXT DEFAULT 'moderate'")
    c.execute('''CREATE TABLE IF NOT EXISTS routine_completions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        routine_id TEXT, routine_name TEXT, routine_type TEXT, duration_minutes INTEGER,
        intensity TEXT, task_description TEXT, youtube_url TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, exercises_logged TEXT
    )''')
    conn.commit()
    conn.close()

def get_stats_today() -> dict:
    conn = get_db()
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute("SELECT count FROM exercises WHERE completed = 1 AND date(timestamp) = ?", (today,))
    exercise_rows = c.fetchall()
    c.execute("SELECT duration_minutes FROM routine_completions WHERE date(timestamp) = ?", (today,))
    routine_rows = c.fetchall()
    conn.close()
    return {
        "total_reps": sum(r['count'] for r in exercise_rows),
        "exercise_count": len(exercise_rows),
        "routine_count": len(routine_rows),
        "total_routine_minutes": sum(r['duration_minutes'] or 0 for r in routine_rows),
    }

def log_exercise_db(name: str, count: int, unit: str = "reps", category: str = "general",
                    intensity: str = "moderate", task_desc: str = "manual"):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO exercises (name, count, unit, category, intensity, task_description, completed)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (name, count, unit, category, intensity, task_desc, True))
    conn.commit()
    conn.close()
    _log_to_markdown(f"{count} {unit if unit != 'reps' else ''} {name}".strip(), category, intensity)

def log_routine_db(routine: dict, task_desc: str = "manual"):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO routine_completions (routine_id, routine_name, routine_type, duration_minutes, intensity, task_description)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (routine.get('id', str(uuid.uuid4())), routine['name'], routine.get('type', 'custom'),
               routine.get('duration_minutes', 0), routine.get('intensity', 'moderate'), task_desc))
    conn.commit()
    conn.close()
    _log_to_markdown(f"{routine['name']} ({routine.get('duration_minutes', '?')} min)", routine.get('type', 'routine'), routine.get('intensity', 'moderate'))

def _log_to_markdown(text: str, category: str, intensity: str):
    SWOLE_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    header = f"## {today_str}"

    if not LOG_FILE.exists():
        with open(LOG_FILE, "w") as f:
            f.write("# Swole Code Workout Log\n\n---\n")

    content = LOG_FILE.read_text()
    if header not in content:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n{header}\n\n")

    with open(LOG_FILE, "a") as f:
        timestamp = datetime.datetime.now().strftime("%H:%M")
        f.write(f"- [x] {timestamp} - **{text}** [{category}] ({intensity})\n")

# --- Interactive Menu System ---

class InteractiveMenu:
    """Arrow-key navigable menu with Esc to cancel."""

    def __init__(self, title: str, items: List[Tuple[str, str, Any]],
                 multi_select: bool = False, selected: set = None):
        """
        items: List of (label, description, value)
        multi_select: Allow multiple selections with space
        selected: Pre-selected values for multi_select
        """
        self.title = title
        self.items = items
        self.multi_select = multi_select
        self.selected = selected or set()
        self.cursor = 0
        self.result = None
        self.cancelled = False

    def run(self) -> Any:
        """Run the interactive menu, returns selected value(s) or None if cancelled."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return self._fallback_menu()

        kb = KeyBindings()

        @kb.add('up')
        @kb.add('k')
        def move_up(event):
            self.cursor = max(0, self.cursor - 1)

        @kb.add('down')
        @kb.add('j')
        def move_down(event):
            self.cursor = min(len(self.items) - 1, self.cursor + 1)

        @kb.add('enter')
        def select(event):
            if self.multi_select:
                self.result = self.selected
            else:
                self.result = self.items[self.cursor][2]
            event.app.exit()

        @kb.add('space')
        def toggle(event):
            if self.multi_select:
                val = self.items[self.cursor][2]
                if val in self.selected:
                    self.selected.discard(val)
                else:
                    self.selected.add(val)

        @kb.add('escape')
        @kb.add('q')
        def cancel(event):
            self.cancelled = True
            event.app.exit()

        def get_formatted_text():
            lines = []
            lines.append(('class:title', f'  {self.title}\n'))
            lines.append(('', '\n'))

            for i, (label, desc, val) in enumerate(self.items):
                is_selected = i == self.cursor

                # Selection marker
                marker = '› ' if is_selected else '  '

                # Checkbox for multi-select (only check membership for hashable values)
                if self.multi_select:
                    try:
                        is_checked = val in self.selected
                    except TypeError:
                        # Unhashable type (like dict), use index instead
                        is_checked = i in self.selected
                    check = '✓ ' if is_checked else '○ '
                else:
                    check = ''

                style = 'class:selected' if is_selected else ''

                lines.append((style, f'{marker}{check}{label}'))
                if desc:
                    lines.append(('class:dim', f'  {desc}'))
                lines.append(('', '\n'))

            lines.append(('', '\n'))
            if self.multi_select:
                lines.append(('class:hint', '↑↓ navigate · Space toggle · Enter confirm · Esc cancel'))
            else:
                lines.append(('class:hint', '↑↓ navigate · Enter select · Esc cancel'))

            return FormattedText(lines)

        style = Style.from_dict({
            'title': 'bold cyan',
            'selected': 'bold reverse',
            'dim': '#888888',
            'hint': '#666666',
        })

        layout = Layout(Window(FormattedTextControl(get_formatted_text)))
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)

        app.run()

        if self.cancelled:
            return None
        return self.result

    def _fallback_menu(self) -> Any:
        """Fallback for when prompt_toolkit isn't available."""
        print(f"\n  {self.title}\n")
        for i, (label, desc, val) in enumerate(self.items):
            check = '✓' if val in self.selected else ' ' if self.multi_select else ''
            prefix = f"[{check}]" if self.multi_select else f"[{i+1}]"
            print(f"  {prefix} {label}")
            if desc:
                print(f"      {desc}")
        print()

        try:
            if self.multi_select:
                inp = input("Enter numbers to toggle (comma-separated), or Enter to confirm: ").strip()
                if inp:
                    for n in inp.split(','):
                        try:
                            idx = int(n.strip()) - 1
                            if 0 <= idx < len(self.items):
                                val = self.items[idx][2]
                                if val in self.selected:
                                    self.selected.discard(val)
                                else:
                                    self.selected.add(val)
                        except ValueError:
                            pass
                return self.selected
            else:
                inp = input("Select (number or Enter for first): ").strip()
                if not inp:
                    return self.items[0][2]
                try:
                    idx = int(inp) - 1
                    if 0 <= idx < len(self.items):
                        return self.items[idx][2]
                except ValueError:
                    pass
                return None
        except (EOFError, KeyboardInterrupt):
            return None


class InputPrompt:
    """Simple input with Esc to cancel."""

    def __init__(self, prompt: str, default: str = ""):
        self.prompt = prompt
        self.default = default
        self.result = None
        self.cancelled = False

    def run(self) -> Optional[str]:
        if not PROMPT_TOOLKIT_AVAILABLE:
            return self._fallback()

        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()

        @kb.add('escape')
        def cancel(event):
            self.cancelled = True
            event.app.exit(result=None)

        try:
            result = pt_prompt(f'{self.prompt}: ', default=self.default, key_bindings=kb)
            if self.cancelled:
                return None
            return result
        except (EOFError, KeyboardInterrupt):
            return None

    def _fallback(self) -> Optional[str]:
        try:
            default_hint = f" [{self.default}]" if self.default else ""
            result = input(f"{self.prompt}{default_hint}: ").strip()
            return result if result else self.default
        except (EOFError, KeyboardInterrupt):
            return None


class TabbedView:
    """Horizontal tab navigation with ←/→ or Tab to cycle."""

    def __init__(self, tabs: List[Tuple[str, Callable]], title: str = ""):
        """
        tabs: List of (tab_label, content_renderer_function)
        content_renderer_function takes no args and returns a string to display
        """
        self.tabs = tabs
        self.title = title
        self.current_tab = 0

    def run(self):
        """Run the tabbed view until Esc is pressed."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return self._fallback()

        kb = KeyBindings()

        @kb.add('left')
        @kb.add('h')
        def prev_tab(event):
            self.current_tab = (self.current_tab - 1) % len(self.tabs)

        @kb.add('right')
        @kb.add('l')
        @kb.add('tab')
        def next_tab(event):
            self.current_tab = (self.current_tab + 1) % len(self.tabs)

        @kb.add('escape')
        @kb.add('q')
        def exit_view(event):
            event.app.exit()

        def get_formatted_text():
            lines = []

            # Title row with tabs
            tab_row = []
            for i, (label, _) in enumerate(self.tabs):
                if i == self.current_tab:
                    tab_row.append(('class:tab-active', f' {label} '))
                else:
                    tab_row.append(('class:tab', f' {label} '))
                tab_row.append(('', '  '))

            tab_row.append(('class:hint', '  (←/→ to switch · Esc to exit)'))
            lines.extend(tab_row)
            lines.append(('', '\n\n'))

            # Render current tab content
            _, renderer = self.tabs[self.current_tab]
            content = renderer()
            lines.append(('', content))

            return FormattedText(lines)

        style = Style.from_dict({
            'tab': '#888888',
            'tab-active': 'bold reverse',
            'hint': '#666666',
        })

        layout = Layout(Window(FormattedTextControl(get_formatted_text)))
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

    def _fallback(self):
        """Fallback for when prompt_toolkit isn't available."""
        while True:
            print("\033[2J\033[H", end="")  # Clear screen

            # Show tabs
            tab_str = ""
            for i, (label, _) in enumerate(self.tabs):
                if i == self.current_tab:
                    tab_str += f"[{label}]  "
                else:
                    tab_str += f" {label}   "
            print(f"  {tab_str}")
            print()

            # Show content
            _, renderer = self.tabs[self.current_tab]
            print(renderer())

            print()
            print("  ←/→ or n/p to switch tabs, q to exit")

            try:
                key = input("  > ").strip().lower()
                if key in ('q', 'quit', 'exit', ''):
                    break
                elif key in ('n', 'right', 'l'):
                    self.current_tab = (self.current_tab + 1) % len(self.tabs)
                elif key in ('p', 'left', 'h'):
                    self.current_tab = (self.current_tab - 1) % len(self.tabs)
            except (EOFError, KeyboardInterrupt):
                break


def press_any_key(message: str = ""):
    """Wait for any key, then clear screen. Accepts Esc, Enter, or any key."""
    if message:
        if RICH_AVAILABLE:
            console.print(f"  {message}")
        else:
            print(f"  {message}")

    if RICH_AVAILABLE:
        console.print("  [dim](press any key)[/dim]")
    else:
        print("  (press any key)")

    if PROMPT_TOOLKIT_AVAILABLE:
        from prompt_toolkit import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        kb = KeyBindings()

        @kb.add('<any>')
        def _(event):
            event.app.exit()

        app = Application(
            layout=Layout(Window(FormattedTextControl(''))),
            key_bindings=kb,
            full_screen=False
        )
        app.run()
    else:
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass

    # Clear screen for clean next render
    print("\033[2J\033[H", end="")


# --- Main Menu Actions ---

def show_stats(config: dict) -> dict:
    stats = get_stats_today()
    focus = get_todays_focus(config)

    print()
    print(f"  Today's Gains")
    print(f"  ─────────────")
    print(f"  {stats['total_reps']} reps · {stats['exercise_count']} exercises · {stats['routine_count']} routines", end="")
    if stats['total_routine_minutes'] > 0:
        print(f" · {stats['total_routine_minutes']} min")
    else:
        print()

    if focus:
        print(f"  Focus: {', '.join(focus)}")
    print()

    press_any_key()
    return config


def log_exercise(config: dict) -> dict:
    exercises = load_exercises() + config.get("custom_exercises", [])

    # Build menu items
    items = []
    for e in exercises:
        unit = e.get('unit', 'reps')
        count_str = f"{e['count']} {unit}" if unit != 'reps' else str(e['count'])
        intensity = e.get('intensity', 'moderate')
        items.append((
            e['name'],
            f"{count_str} · {e.get('category', 'general')} · {intensity}",
            e
        ))

    menu = InteractiveMenu("Select exercise to log", items)
    exercise = menu.run()

    if exercise is None:
        return config

    # Get count
    prompt = InputPrompt("How many?", str(exercise['count']))
    count_str = prompt.run()

    if count_str is None:
        return config

    try:
        count = int(count_str)
    except ValueError:
        count = exercise['count']

    log_exercise_db(
        exercise['name'], count,
        exercise.get('unit', 'reps'),
        exercise.get('category', 'general'),
        exercise.get('intensity', 'moderate')
    )

    print(f"\n  ✓ Logged: {count} {exercise['name']}\n")
    stats = get_stats_today()
    print(f"  Today: {stats['total_reps']} reps, {stats['exercise_count']} exercises")
    print()
    press_any_key()
    return config


def log_routine(config: dict) -> dict:
    routines_data = load_routines_data()
    routines = routines_data.get("sample_routines", []) + config.get("custom_routines", [])

    items = []
    for r in routines:
        has_link = '🔗' if r.get('url') else ''
        items.append((
            f"{r['name']} {has_link}".strip(),
            f"{r.get('duration_minutes', '?')} min · {r.get('type', 'custom')} · {r.get('intensity', 'moderate')}",
            r
        ))

    menu = InteractiveMenu("Select routine to log", items)
    routine = menu.run()

    if routine is None:
        return config

    # Show routine details before logging
    print()
    print(f"  {routine['name']}")
    print(f"  ─────────────────────")
    print(f"  {routine.get('duration_minutes', '?')} min · {routine.get('intensity', 'moderate')}")

    if routine.get('url'):
        print(f"  Link: {routine['url']}")

    if routine.get('exercises'):
        print(f"  Exercises:")
        for ex in routine['exercises']:
            unit = ex.get('unit', 'reps')
            print(f"    • {ex['count']} {unit} {ex['name']}")

    if routine.get('description'):
        print(f"  {routine['description']}")

    print()

    # Confirm logging
    confirm_menu = InteractiveMenu("", [
        ("Log completion", "Mark this routine as done", "log"),
        ("Back", "Return without logging", "back"),
    ])
    choice = confirm_menu.run()

    if choice != "log":
        return config

    log_routine_db(routine)

    print(f"\n  ✓ Logged: {routine['name']} ({routine.get('duration_minutes', '?')} min)\n")
    press_any_key()
    return config


def suggest_exercise(config: dict) -> dict:
    exercises = load_exercises() + config.get("custom_exercises", [])

    # Filter by equipment
    user_equipment = set(config.get("equipment", ["none"]))
    user_equipment.add("none")
    exercises = [e for e in exercises if not e.get("equipment") or
                 any(eq in user_equipment for eq in e.get("equipment", []))]

    # Filter by intensity
    intensity_pref = config.get("intensity_preference", "mixed")
    if intensity_pref != "mixed":
        filtered = [e for e in exercises if e.get("intensity", "moderate") == intensity_pref]
        if filtered:
            exercises = filtered

    if not exercises:
        print("\n  No exercises match current filters.\n")
        press_any_key()
        return config

    exercise = random.choice(exercises)
    count = exercise['count']
    unit = exercise.get('unit', 'reps')
    name = exercise['name']

    display = f"{count} {unit} {name}" if unit != 'reps' else f"{count} {name}"

    print()
    print(f"  ╭─ Try This ─────────────────────╮")
    print(f"  │  {display:<31} │")
    print(f"  ╰─────────────────────────────────╯")
    print(f"  {exercise.get('category', 'general')} · {exercise.get('intensity', 'moderate')}")
    print()

    items = [
        ("Log it", "Record this exercise", "log"),
        ("Another", "Get a different suggestion", "another"),
        ("Back", "Return to main menu", "back"),
    ]

    menu = InteractiveMenu("", items)
    choice = menu.run()

    if choice == "log":
        log_exercise_db(name, count, unit, exercise.get('category', 'general'), exercise.get('intensity', 'moderate'))
        print(f"\n  ✓ Logged: {display}\n")
        press_any_key()
    elif choice == "another":
        return suggest_exercise(config)

    return config


def configure_equipment(config: dict) -> dict:
    routines_data = load_routines_data()
    equipment_types = routines_data.get("equipment_types", [])

    items = []
    current = set(config.get('equipment', ['none']))

    for eq in equipment_types:
        items.append((eq['name'], eq['description'], eq['id']))

    menu = InteractiveMenu("Select your equipment", items, multi_select=True, selected=current)
    result = menu.run()

    if result is not None:
        config['equipment'] = list(result) if result else ['none']
        save_config(config)
        print(f"\n  ✓ Equipment updated\n")
        press_any_key()

    return config


def configure_intensity(config: dict) -> dict:
    items = [
        ("Gentle", "Morning park vibes, mobility, easy movement", "gentle"),
        ("Moderate", "Real work, but sustainable", "moderate"),
        ("Intense", "Heart rate up, sweat expected", "intense"),
        ("Mixed", "Vary based on time available", "mixed"),
    ]

    menu = InteractiveMenu("Select intensity preference", items)
    result = menu.run()

    if result is not None:
        config['intensity_preference'] = result
        save_config(config)
        print(f"\n  ✓ Intensity set to {result}\n")
        press_any_key()

    return config


def configure_pattern(config: dict) -> dict:
    routines_data = load_routines_data()
    patterns = routines_data.get("weekly_patterns", [])

    items = []
    for p in patterns:
        items.append((p['name'], p['description'], p['id']))

    menu = InteractiveMenu("Select weekly pattern", items)
    result = menu.run()

    if result is not None:
        config['weekly_pattern'] = result
        save_config(config)
        # Find pattern name
        name = result
        for p in patterns:
            if p['id'] == result:
                name = p['name']
                break
        print(f"\n  ✓ Pattern set to {name}\n")
        press_any_key()

    return config


def configure_categories(config: dict) -> dict:
    cats = config.get('categories', {})

    items = []
    current = set(cat for cat, enabled in cats.items() if enabled)

    for cat in cats.keys():
        items.append((cat.title(), "", cat))

    menu = InteractiveMenu("Toggle categories", items, multi_select=True, selected=current)
    result = menu.run()

    if result is not None:
        for cat in cats:
            cats[cat] = cat in result
        config['categories'] = cats
        save_config(config)
        print(f"\n  ✓ Categories updated\n")
        press_any_key()

    return config


def configure_theme(config: dict) -> dict:
    """Select color theme."""
    items = []
    for theme_id, theme in THEMES.items():
        items.append((theme['name'], theme['description'], theme_id))

    menu = InteractiveMenu("Select color theme", items)
    result = menu.run()

    if result is not None:
        config['theme'] = result
        save_config(config)

        # Show preview
        print("\033[2J\033[H", end="")  # Clear screen
        if RICH_AVAILABLE:
            console.print()
            console.print(render_logo(config))
            console.print()
            console.print(render_dumbbell(config))
            console.print()
            theme = get_theme(config)
            console.print(f"[{theme['accent']}]✓ Theme set to {theme['name']}[/]")
            console.print()

        press_any_key()

    return config


def configure_custom_exercises(config: dict) -> dict:
    """Manage custom exercises."""
    while True:
        custom = config.get('custom_exercises', [])

        items = [("+ Add new exercise", "Create a custom exercise", "add")]

        for i, ex in enumerate(custom):
            unit = ex.get('unit', 'reps')
            count_str = f"{ex['count']} {unit}" if unit != 'reps' else str(ex['count'])
            items.append((
                ex['name'],
                f"{count_str} · {ex.get('category', 'general')} · {ex.get('intensity', 'moderate')}",
                f"edit:{i}"
            ))

        items.append(("Back", "Return to config", "back"))

        menu = InteractiveMenu("Custom Exercises", items)
        choice = menu.run()

        if choice is None or choice == "back":
            return config

        if choice == "add":
            config = add_custom_exercise(config)

        elif choice.startswith("edit:"):
            idx = int(choice.split(":")[1])
            config = edit_custom_exercise(config, idx)

    return config


def add_custom_exercise(config: dict) -> dict:
    """Add a new custom exercise."""
    print()
    print("  Add Custom Exercise")
    print("  ───────────────────")
    print()

    # Name
    name_prompt = InputPrompt("Exercise name")
    name = name_prompt.run()
    if not name:
        return config

    # Count type (reps or time)
    count_type_menu = InteractiveMenu("Count type", [
        ("Reps", "Count repetitions (e.g., 10 pushups)", "reps"),
        ("Seconds", "Timed hold (e.g., 30 second plank)", "seconds"),
        ("Each side", "Per-side count (e.g., 10 each side)", "each side"),
        ("Each direction", "Per-direction count (e.g., 10 each direction)", "each direction"),
    ])
    unit = count_type_menu.run()
    if unit is None:
        return config

    # Count
    count_prompt = InputPrompt(f"Default count ({unit})", "10")
    count_str = count_prompt.run()
    if not count_str:
        return config
    try:
        count = int(count_str)
    except ValueError:
        print("  ✗ Invalid number")
        press_any_key()
        return config

    # Category
    cat_menu = InteractiveMenu("Category", [
        ("Legs", "Lower body", "legs"),
        ("Upper", "Upper body", "upper"),
        ("Core", "Abs and back", "core"),
        ("Cardio", "Heart rate up", "cardio"),
        ("Mobility", "Stretching and flexibility", "mobility"),
        ("Full", "Full body movement", "full"),
    ])
    category = cat_menu.run()
    if category is None:
        return config

    # Intensity
    int_menu = InteractiveMenu("Intensity", [
        ("Gentle", "Easy, can do anytime", "gentle"),
        ("Moderate", "Real work, sustainable", "moderate"),
        ("Intense", "Heart rate up, sweat likely", "intense"),
    ])
    intensity = int_menu.run()
    if intensity is None:
        return config

    # Create exercise
    exercise = {
        "name": name,
        "count": count,
        "unit": unit if unit != "reps" else None,
        "category": category,
        "intensity": intensity,
        "custom": True
    }

    # Clean up None unit
    if exercise["unit"] is None:
        del exercise["unit"]

    custom = config.get('custom_exercises', [])
    custom.append(exercise)
    config['custom_exercises'] = custom
    save_config(config)

    print(f"\n  ✓ Added: {name}\n")
    press_any_key()
    return config


def edit_custom_exercise(config: dict, idx: int) -> dict:
    """Edit or delete a custom exercise."""
    custom = config.get('custom_exercises', [])
    if idx >= len(custom):
        return config

    ex = custom[idx]

    while True:
        # Build menu showing current values
        unit_display = ex.get('unit', 'reps')
        items = [
            (f"Name: {ex['name']}", "Change exercise name", "name"),
            (f"Count: {ex['count']} {unit_display}", "Change count and unit", "count"),
            (f"Category: {ex['category']}", "Change category", "category"),
            (f"Intensity: {ex['intensity']}", "Change intensity", "intensity"),
            ("Delete", "Remove this exercise", "delete"),
            ("Done", "Save and return", "done"),
        ]

        menu = InteractiveMenu(f"Edit: {ex['name']}", items)
        choice = menu.run()

        if choice is None or choice == "done":
            # Save changes
            custom[idx] = ex
            config['custom_exercises'] = custom
            save_config(config)
            return config

        elif choice == "name":
            name_prompt = InputPrompt("Exercise name", ex['name'])
            new_name = name_prompt.run()
            if new_name:
                ex['name'] = new_name

        elif choice == "count":
            # Count type
            current_unit = ex.get('unit', 'reps')
            count_type_menu = InteractiveMenu("Count type", [
                ("Reps", "Count repetitions", "reps"),
                ("Seconds", "Timed hold", "seconds"),
                ("Each side", "Per-side count", "each side"),
                ("Each direction", "Per-direction count", "each direction"),
            ])
            new_unit = count_type_menu.run()
            if new_unit:
                # Count
                count_prompt = InputPrompt(f"Default count ({new_unit})", str(ex['count']))
                count_str = count_prompt.run()
                if count_str:
                    try:
                        ex['count'] = int(count_str)
                        if new_unit == 'reps':
                            ex.pop('unit', None)
                        else:
                            ex['unit'] = new_unit
                    except ValueError:
                        print("  ✗ Invalid number")
                        press_any_key()

        elif choice == "category":
            cat_menu = InteractiveMenu("Category", [
                ("Legs", "Lower body", "legs"),
                ("Upper", "Upper body", "upper"),
                ("Core", "Abs and back", "core"),
                ("Cardio", "Heart rate up", "cardio"),
                ("Mobility", "Stretching and flexibility", "mobility"),
                ("Full", "Full body movement", "full"),
            ])
            new_cat = cat_menu.run()
            if new_cat:
                ex['category'] = new_cat

        elif choice == "intensity":
            int_menu = InteractiveMenu("Intensity", [
                ("Gentle", "Easy, can do anytime", "gentle"),
                ("Moderate", "Real work, sustainable", "moderate"),
                ("Intense", "Heart rate up, sweat likely", "intense"),
            ])
            new_int = int_menu.run()
            if new_int:
                ex['intensity'] = new_int

        elif choice == "delete":
            confirm_menu = InteractiveMenu(f"Delete {ex['name']}?", [
                ("Yes, delete", "Remove permanently", "yes"),
                ("No, keep", "Cancel deletion", "no"),
            ])
            if confirm_menu.run() == "yes":
                custom.pop(idx)
                config['custom_exercises'] = custom
                save_config(config)
                print(f"\n  ✓ Deleted: {ex['name']}\n")
                press_any_key()
                return config

    return config


def configure_custom_routines(config: dict) -> dict:
    """Manage custom routines."""
    while True:
        custom = config.get('custom_routines', [])

        items = [("+ Add new routine", "Create a custom routine", "add")]

        for i, rt in enumerate(custom):
            duration = rt.get('duration_minutes', '?')
            rt_type = rt.get('type', 'custom')
            has_link = '🔗' if rt.get('url') else ''
            has_exercises = f"({len(rt.get('exercises', []))} exercises)" if rt.get('exercises') else ''
            items.append((
                f"{rt['name']} {has_link}",
                f"{duration} min · {rt_type} · {rt.get('intensity', 'moderate')} {has_exercises}",
                f"edit:{i}"
            ))

        items.append(("Back", "Return to config", "back"))

        menu = InteractiveMenu("Custom Routines", items)
        choice = menu.run()

        if choice is None or choice == "back":
            return config

        if choice == "add":
            config = add_custom_routine(config)

        elif choice.startswith("edit:"):
            idx = int(choice.split(":")[1])
            config = edit_custom_routine(config, idx)

    return config


def add_custom_routine(config: dict) -> dict:
    """Add a new custom routine."""
    print()
    print("  Add Custom Routine")
    print("  ──────────────────")
    print()

    # Name (required to start)
    name_prompt = InputPrompt("Routine name")
    name = name_prompt.run()
    if not name:
        return config

    # Create routine with defaults
    routine = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "type": "custom",
        "duration_minutes": 15,
        "intensity": "moderate",
        "custom": True
    }

    # Enter the edit loop for the new routine
    result = routine_editor(config, routine, is_new=True)

    if result is not None:
        custom = config.get('custom_routines', [])
        custom.append(result)
        config['custom_routines'] = custom
        save_config(config)
        print(f"\n  ✓ Added routine: {result['name']}\n")
        press_any_key()

    return config


def routine_editor(config: dict, routine: dict, is_new: bool = False) -> Optional[dict]:
    """
    Edit a routine's fields. Returns the modified routine, or None if cancelled.
    For new routines, returns None to cancel creation.
    For existing routines, returns the routine (possibly modified).
    """
    routines_data = load_routines_data()

    # Get type name for display
    def get_type_name(type_id):
        for rt in routines_data.get("routine_types", []):
            if rt['id'] == type_id:
                return rt['name']
        return type_id.title()

    while True:
        # Display current routine state
        print()
        print(f"  {routine['name']}")
        print(f"  ─────────────────────────────")
        print(f"  Type:      {get_type_name(routine.get('type', 'custom'))}")
        print(f"  Duration:  {routine.get('duration_minutes', '?')} min")
        print(f"  Intensity: {routine.get('intensity', 'moderate')}")
        if routine.get('url'):
            print(f"  Link:      {routine['url']}")
        if routine.get('exercises'):
            print(f"  Exercises: {len(routine['exercises'])}")
            for ex in routine['exercises']:
                unit = ex.get('unit', 'reps')
                print(f"    • {ex['count']} {unit} {ex['name']}")
        print()

        # Build menu items
        items = [
            ("Name", f"Currently: {routine['name']}", "name"),
            ("Type", f"Currently: {get_type_name(routine.get('type', 'custom'))}", "type"),
            ("Duration", f"Currently: {routine.get('duration_minutes', '?')} min", "duration"),
            ("Intensity", f"Currently: {routine.get('intensity', 'moderate')}", "intensity"),
            ("Link", f"{'Edit: ' + routine['url'][:30] + '...' if routine.get('url') and len(routine.get('url', '')) > 30 else 'Set: ' + routine.get('url', '(none)')}", "url"),
            ("Exercises", f"{len(routine.get('exercises', []))} exercises", "exercises"),
        ]

        if is_new:
            items.append(("Save", "Create this routine", "save"))
            items.append(("Cancel", "Discard and go back", "cancel"))
        else:
            items.append(("Delete", "Remove this routine", "delete"))
            items.append(("Done", "Save changes", "done"))

        menu = InteractiveMenu("Edit routine", items)
        choice = menu.run()

        if choice is None or choice == "cancel":
            return None

        if choice == "save" or choice == "done":
            return routine

        if choice == "delete":
            return "DELETE"  # Special signal to delete

        if choice == "name":
            prompt = InputPrompt("Routine name", routine['name'])
            result = prompt.run()
            if result:
                routine['name'] = result

        elif choice == "type":
            type_items = []
            for rt in routines_data.get("routine_types", []):
                type_items.append((rt['name'], rt['description'], rt['id']))
            type_items.append(("Custom", "Define your own type", "custom"))

            type_menu = InteractiveMenu("Routine type", type_items)
            result = type_menu.run()
            if result:
                routine['type'] = result

        elif choice == "duration":
            prompt = InputPrompt("Duration (minutes)", str(routine.get('duration_minutes', 15)))
            result = prompt.run()
            if result:
                try:
                    routine['duration_minutes'] = int(result)
                except ValueError:
                    print("  ✗ Invalid number")
                    press_any_key()

        elif choice == "intensity":
            int_menu = InteractiveMenu("Intensity", [
                ("Gentle", "Easy, restorative", "gentle"),
                ("Moderate", "Steady work", "moderate"),
                ("Intense", "High effort", "intense"),
            ])
            result = int_menu.run()
            if result:
                routine['intensity'] = result

        elif choice == "url":
            current_url = routine.get('url', '')
            if current_url:
                url_menu = InteractiveMenu("Link options", [
                    ("Edit", "Change the URL", "edit"),
                    ("Remove", "Clear the link", "remove"),
                    ("Keep", "Leave as is", "keep"),
                ])
                url_choice = url_menu.run()
                if url_choice == "edit":
                    prompt = InputPrompt("Video/link URL", current_url)
                    result = prompt.run()
                    if result:
                        routine['url'] = result
                elif url_choice == "remove":
                    del routine['url']
            else:
                prompt = InputPrompt("Video/link URL")
                result = prompt.run()
                if result:
                    routine['url'] = result

        elif choice == "exercises":
            routine['exercises'] = routine.get('exercises', [])
            config = build_routine_exercises(config, routine)

    return routine


def build_routine_exercises(config: dict, routine: dict) -> dict:
    """Build the exercise list for a routine."""
    all_exercises = load_exercises() + config.get('custom_exercises', [])

    while True:
        current = routine.get('exercises', [])

        print()
        print(f"  Building: {routine['name']}")
        print(f"  ─────────────────────────")
        if current:
            print("  Current exercises:")
            for i, ex in enumerate(current, 1):
                unit = ex.get('unit', 'reps')
                print(f"    {i}. {ex['count']} {unit} {ex['name']}")
        else:
            print("  [No exercises yet]")
        print()

        items = [
            ("+ Add from library", "Choose existing exercise", "library"),
            ("+ Add custom", "Create new exercise for this routine", "custom"),
        ]
        if current:
            items.append(("Remove last", "Remove the last exercise", "remove"))
        items.append(("Done", "Finish building routine", "done"))
        items.append(("Cancel", "Discard this routine", "cancel"))

        menu = InteractiveMenu("Add exercises", items)
        choice = menu.run()

        if choice is None or choice == "cancel":
            routine['exercises'] = []
            return config

        if choice == "done":
            return config

        if choice == "remove" and current:
            current.pop()
            routine['exercises'] = current
            continue

        if choice == "library":
            # Show exercise picker
            ex_items = []
            for ex in all_exercises:
                unit = ex.get('unit', 'reps')
                count_str = f"{ex['count']} {unit}" if unit else str(ex['count'])
                ex_items.append((
                    ex['name'],
                    f"{count_str} · {ex.get('category', 'general')}",
                    ex
                ))

            ex_menu = InteractiveMenu("Select exercise", ex_items)
            selected = ex_menu.run()

            if selected:
                # Ask for count override
                unit = selected.get('unit', 'reps')
                count_prompt = InputPrompt(f"Count ({unit})", str(selected['count']))
                count_str = count_prompt.run()
                if count_str:
                    try:
                        count = int(count_str)
                        routine_ex = {
                            "name": selected['name'],
                            "count": count,
                        }
                        if selected.get('unit'):
                            routine_ex['unit'] = selected['unit']
                        current.append(routine_ex)
                        routine['exercises'] = current
                    except ValueError:
                        pass

        elif choice == "custom":
            # Quick add custom exercise
            name_prompt = InputPrompt("Exercise name")
            name = name_prompt.run()
            if not name:
                continue

            unit_menu = InteractiveMenu("Count type", [
                ("Reps", "", "reps"),
                ("Seconds", "", "seconds"),
                ("Each side", "", "each side"),
            ])
            unit = unit_menu.run()
            if unit is None:
                continue

            count_prompt = InputPrompt(f"Count ({unit})", "10")
            count_str = count_prompt.run()
            if not count_str:
                continue

            try:
                count = int(count_str)
                routine_ex = {"name": name, "count": count}
                if unit != "reps":
                    routine_ex['unit'] = unit
                current.append(routine_ex)
                routine['exercises'] = current
            except ValueError:
                pass

    return config


def edit_custom_routine(config: dict, idx: int) -> dict:
    """Edit or delete a custom routine."""
    custom = config.get('custom_routines', [])
    if idx >= len(custom):
        return config

    rt = custom[idx]

    # Use the routine editor
    result = routine_editor(config, rt, is_new=False)

    if result == "DELETE":
        custom.pop(idx)
        config['custom_routines'] = custom
        save_config(config)
        print(f"\n  ✓ Deleted: {rt['name']}\n")
        press_any_key()
    elif result is not None:
        # Save any changes
        custom[idx] = result
        config['custom_routines'] = custom
        save_config(config)

    return config


def get_history_data(period: str) -> dict:
    """Get exercise and routine data for a time period."""
    conn = get_db()
    c = conn.cursor()

    today = datetime.date.today()

    if period == "today":
        date_filter = "date(timestamp) = ?"
        date_param = today.isoformat()
    elif period == "week":
        # Start of week (Monday)
        start_of_week = today - datetime.timedelta(days=today.weekday())
        date_filter = "date(timestamp) >= ?"
        date_param = start_of_week.isoformat()
    elif period == "month":
        start_of_month = today.replace(day=1)
        date_filter = "date(timestamp) >= ?"
        date_param = start_of_month.isoformat()
    else:  # all time
        date_filter = "1=1"
        date_param = None

    # Get exercises
    if date_param:
        c.execute(f"""SELECT name, count, unit, category, intensity, timestamp FROM exercises
                     WHERE completed = 1 AND {date_filter}
                     ORDER BY timestamp DESC""", (date_param,))
    else:
        c.execute("""SELECT name, count, unit, category, intensity, timestamp FROM exercises
                     WHERE completed = 1 ORDER BY timestamp DESC""")
    exercises = c.fetchall()

    # Get routines
    if date_param:
        c.execute(f"""SELECT routine_name, routine_type, duration_minutes, intensity, timestamp
                     FROM routine_completions WHERE {date_filter}
                     ORDER BY timestamp DESC""", (date_param,))
    else:
        c.execute("""SELECT routine_name, routine_type, duration_minutes, intensity, timestamp
                     FROM routine_completions ORDER BY timestamp DESC""")
    routines = c.fetchall()

    conn.close()

    # Aggregate by category
    category_reps = {}
    for ex in exercises:
        cat = ex['category'] or 'other'
        category_reps[cat] = category_reps.get(cat, 0) + (ex['count'] or 0)

    # Aggregate by day for the period
    daily_reps = {}
    for ex in exercises:
        day = ex['timestamp'][:10]
        daily_reps[day] = daily_reps.get(day, 0) + (ex['count'] or 0)

    return {
        "exercises": exercises,
        "routines": routines,
        "category_reps": category_reps,
        "daily_reps": daily_reps,
        "total_reps": sum(ex['count'] or 0 for ex in exercises),
        "total_routines": len(routines),
        "total_routine_minutes": sum(r['duration_minutes'] or 0 for r in routines),
    }


def render_bar_chart(data: dict, max_width: int = 30) -> str:
    """Render a horizontal bar chart."""
    if not data:
        return "  [No data]\n"

    max_val = max(data.values()) if data.values() else 1
    lines = []

    # Sort by value descending
    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)

    for label, value in sorted_items:
        bar_width = int((value / max_val) * max_width) if max_val > 0 else 0
        bar = "█" * bar_width
        lines.append(f"  {label:12} {bar} {value}")

    return "\n".join(lines)


def render_history_tab(period: str, config: dict) -> str:
    """Render the content for a history tab."""
    data = get_history_data(period)
    theme = get_theme(config)
    lines = []

    # Summary stats
    lines.append(f"  ╭─ Summary ─────────────────────────────────╮")
    lines.append(f"  │  {data['total_reps']} reps · {data['total_routines']} routines · {data['total_routine_minutes']} min  │")
    lines.append(f"  ╰────────────────────────────────────────────╯")
    lines.append("")

    # Category breakdown bar chart
    if data['category_reps']:
        lines.append("  By Category:")
        lines.append(render_bar_chart(data['category_reps']))
        lines.append("")

    # Daily breakdown for week/month/all
    if period != "today" and data['daily_reps']:
        lines.append("  By Day:")
        # Show last 7 days max
        daily_items = sorted(data['daily_reps'].items(), reverse=True)[:7]
        daily_dict = dict(reversed(daily_items))
        lines.append(render_bar_chart(daily_dict, max_width=20))
        lines.append("")

    # Recent activity log
    lines.append("  Recent Activity:")
    lines.append("  ─────────────────")

    exercises = data['exercises'][:8]  # Limit to 8 most recent
    routines = data['routines'][:4]    # Limit to 4 most recent

    if exercises:
        for ex in exercises:
            dt = datetime.datetime.fromisoformat(ex['timestamp'])
            if period == "today":
                time_str = dt.strftime("%H:%M")
            else:
                time_str = dt.strftime("%m/%d %H:%M")
            unit = ex['unit'] or 'reps'
            ex_str = f"{ex['count']} {unit} {ex['name']}" if unit != 'reps' else f"{ex['count']} {ex['name']}"
            lines.append(f"  {time_str}  {ex_str}")

    if routines:
        lines.append("")
        for r in routines:
            dt = datetime.datetime.fromisoformat(r['timestamp'])
            if period == "today":
                time_str = dt.strftime("%H:%M")
            else:
                time_str = dt.strftime("%m/%d %H:%M")
            lines.append(f"  {time_str}  🏋️ {r['routine_name']} ({r['duration_minutes'] or '?'} min)")

    if not exercises and not routines:
        lines.append("  No activity yet.")

    return "\n".join(lines)


def show_history(config: dict) -> dict:
    """Show history with tabbed view."""
    print("\033[2J\033[H", end="")  # Clear screen

    tabs = [
        ("Today", lambda: render_history_tab("today", config)),
        ("This Week", lambda: render_history_tab("week", config)),
        ("This Month", lambda: render_history_tab("month", config)),
        ("All Time", lambda: render_history_tab("all", config)),
    ]

    view = TabbedView(tabs)
    view.run()

    return config


def show_config(config: dict) -> dict:
    routines_data = load_routines_data()
    theme = get_theme(config)

    equipment_names = {e['id']: e['name'] for e in routines_data.get("equipment_types", [])}
    eq_display = [equipment_names.get(e, e) for e in config.get('equipment', ['none'])]

    pattern_id = config.get('weekly_pattern', 'freestyle')
    pattern_name = pattern_id
    for p in routines_data.get("weekly_patterns", []):
        if p['id'] == pattern_id:
            pattern_name = p['name']
            break

    enabled_cats = [c for c, e in config.get('categories', {}).items() if e]

    if RICH_AVAILABLE:
        console.print()
        console.print(f"[bold]Current Configuration[/]")
        console.print(f"[dim]─────────────────────[/]")
        console.print(f"[{theme['accent']}]Theme:[/]      {theme['name']}")
        console.print(f"[{theme['accent']}]Equipment:[/]  {', '.join(eq_display)}")
        console.print(f"[{theme['accent']}]Intensity:[/]  {config.get('intensity_preference', 'mixed')}")
        console.print(f"[{theme['accent']}]Pattern:[/]    {pattern_name}")
        console.print(f"[{theme['accent']}]Categories:[/] {', '.join(enabled_cats)}")
        console.print(f"[{theme['accent']}]Cooldown:[/]   {config.get('cooldown_minutes', 30)} min")
        console.print()
    else:
        print()
        print("  Current Configuration")
        print("  ─────────────────────")
        print(f"  Theme:      {theme['name']}")
        print(f"  Equipment:  {', '.join(eq_display)}")
        print(f"  Intensity:  {config.get('intensity_preference', 'mixed')}")
        print(f"  Pattern:    {pattern_name}")
        print(f"  Categories: {', '.join(enabled_cats)}")
        print(f"  Cooldown:   {config.get('cooldown_minutes', 30)} min")
        print()

    custom_ex_count = len(config.get('custom_exercises', []))
    custom_rt_count = len(config.get('custom_routines', []))

    items = [
        ("Theme", "Change color theme", "theme"),
        ("Equipment", "Manage your equipment", "equipment"),
        ("Intensity", "Set intensity preference", "intensity"),
        ("Pattern", "Set weekly pattern", "pattern"),
        ("Categories", "Toggle exercise categories", "categories"),
        ("Custom Exercises", f"Add/remove exercises ({custom_ex_count} custom)", "custom_exercises"),
        ("Custom Routines", f"Add/remove routines ({custom_rt_count} custom)", "custom_routines"),
        ("Back", "Return to main menu", "back"),
    ]

    menu = InteractiveMenu("Edit configuration", items)
    choice = menu.run()

    if choice == "theme":
        return configure_theme(config)
    elif choice == "equipment":
        return configure_equipment(config)
    elif choice == "intensity":
        return configure_intensity(config)
    elif choice == "pattern":
        return configure_pattern(config)
    elif choice == "categories":
        return configure_categories(config)
    elif choice == "custom_exercises":
        return configure_custom_exercises(config)
    elif choice == "custom_routines":
        return configure_custom_routines(config)

    return config


# --- ASCII Art Logo ---

# --- Color Themes ---

THEMES = {
    "fire": {
        "name": "Fire",
        "description": "Orange and red - classic fitness energy",
        "gradient": ["red", "bright_red", "orange1", "orange3", "yellow", "bright_yellow"],
        "accent": "orange1",
        "weight_color": "red",
    },
    "rainbow": {
        "name": "Rainbow",
        "description": "Full spectrum pride vibes",
        "gradient": ["red", "yellow", "green", "cyan", "blue", "magenta"],
        "accent": "magenta",
        "weight_color": "magenta",
    },
    "ocean": {
        "name": "Ocean",
        "description": "Cool blues and teals",
        "gradient": ["bright_cyan", "cyan", "dodger_blue2", "blue", "blue1", "dark_blue"],
        "accent": "cyan",
        "weight_color": "blue",
    },
    "matrix": {
        "name": "Matrix",
        "description": "Green terminal aesthetic",
        "gradient": ["bright_green", "green", "green3", "dark_green", "green4", "chartreuse4"],
        "accent": "bright_green",
        "weight_color": "green",
    },
    "mono": {
        "name": "Monochrome",
        "description": "Clean black and white",
        "gradient": ["white", "bright_white", "grey84", "grey70", "grey58", "grey46"],
        "accent": "white",
        "weight_color": "white",
    },
}

LOGO_LINES = [
    "   ███████╗██╗    ██╗ ██████╗ ██╗     ███████╗",
    "   ██╔════╝██║    ██║██╔═══██╗██║     ██╔════╝",
    "   ███████╗██║ █╗ ██║██║   ██║██║     █████╗",
    "   ╚════██║██║███╗██║██║   ██║██║     ██╔══╝",
    "   ███████║╚███╔███╔╝╚██████╔╝███████╗███████╗",
    "   ╚══════╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝╚══════╝",
    "    ██████╗ ██████╗ ██████╗ ███████╗",
    "   ██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    "   ██║     ██║   ██║██║  ██║█████╗",
    "   ██║     ██║   ██║██║  ██║██╔══╝",
    "   ╚██████╗╚██████╔╝██████╔╝███████╗",
    "    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
]

LOGO_MINI_LINES = [
    "┏━┓╻ ╻┏━┓╻  ┏━╸ ┏━╸┏━┓╺┳┓┏━╸",
    "┗━┓┃╻┃┃ ┃┃  ┣╸  ┃  ┃ ┃ ┃┃┣╸ ",
    "┗━┛┗┻┛┗━┛┗━╸┗━╸ ┗━╸┗━┛╺┻┛┗━╸",
]

DUMBBELL_LINES = [
    "┏━━━┓───────┏━━━┓",
    "┃███┃═══════┃███┃",
    "┗━━━┛───────┗━━━┛",
]

def get_theme(config: dict) -> dict:
    """Get the current theme."""
    theme_id = config.get("theme", "fire")
    return THEMES.get(theme_id, THEMES["fire"])

def render_logo(config: dict) -> str:
    """Render the full logo with current theme colors."""
    theme = get_theme(config)
    colors = theme["gradient"]

    lines = []
    for i, line in enumerate(LOGO_LINES):
        color = colors[i % len(colors)]
        lines.append(f"[bold {color}]{line}[/]")
    return "\n".join(lines)

def render_logo_mini(config: dict) -> str:
    """Render the mini logo with current theme colors."""
    theme = get_theme(config)
    colors = theme["gradient"]

    lines = []
    for i, line in enumerate(LOGO_MINI_LINES):
        color = colors[i % len(colors)]
        lines.append(f"[bold {color}]{line}[/]")
    return "\n".join(lines)

def render_dumbbell(config: dict) -> str:
    """Render the dumbbell with current theme colors."""
    theme = get_theme(config)
    weight_color = theme["weight_color"]

    return f"""[bold white]┏━━━┓───────┏━━━┓[/]
[bold white]┃[/][on {weight_color}]███[/][bold white]┃═══════┃[/][on {weight_color}]███[/][bold white]┃[/]
[bold white]┗━━━┛───────┗━━━┛[/]"""

def print_welcome(config: dict):
    """Print welcome screen with dramatic logo."""
    # Clear screen
    print("\033[2J\033[H", end="")

    if RICH_AVAILABLE:
        console.print()

        # Print the themed logo
        console.print(render_logo(config))

        console.print()
        console.print("[dim]        Micro-workouts while your AI agent works[/]")
        console.print()

        # Dumbbell with themed weights
        console.print(render_dumbbell(config))
        console.print()

        # Quick stats
        stats = get_stats_today()
        if stats['total_reps'] > 0 or stats['routine_count'] > 0:
            theme = get_theme(config)
            console.print(f"[{theme['accent']}]        Today: {stats['total_reps']} reps · {stats['exercise_count']} exercises · {stats['routine_count']} routines[/]")
            console.print()
    else:
        # Plain text fallback
        for line in LOGO_LINES:
            print(line)
        print()
        print("        Micro-workouts while your AI agent works")
        print()

    import time
    time.sleep(1.0)  # Dramatic pause


# --- Main Menu ---

def main_menu():
    init_db()
    config = load_config()

    # Show welcome logo on first launch
    print_welcome(config)

    while True:
        # Clear screen
        print("\033[2J\033[H", end="")

        # Header with mini logo
        stats = get_stats_today()
        focus = get_todays_focus(config)
        theme = get_theme(config)

        if RICH_AVAILABLE:
            console.print()
            console.print(render_logo_mini(config))
            console.print()
            console.print(f"[{theme['accent']}]Today:[/] {stats['total_reps']} reps · {stats['exercise_count']} exercises · {stats['routine_count']} routines")
            if focus:
                console.print(f"[{theme['accent']}]Focus:[/] {', '.join(focus)}")
            console.print()
        else:
            print()
            print("  SWOLE CODE")
            print(f"  Today: {stats['total_reps']} reps · {stats['exercise_count']} exercises · {stats['routine_count']} routines")
            if focus:
                print(f"  Focus: {', '.join(focus)}")
            print()

        items = [
            ("Log Exercise", "Record a completed exercise", "log_exercise"),
            ("Log Routine", "Record a completed routine", "log_routine"),
            ("Suggest", "Get a random exercise suggestion", "suggest"),
            ("", "", ""),
            ("Stats", "View today's workout stats", "stats"),
            ("History", "View recent activity", "history"),
            ("", "", ""),
            ("Config", "View and edit configuration", "config"),
            ("", "", ""),
            ("Quit", "Exit Swole Code", "quit"),
        ]

        # Filter out empty items for navigation but keep for display
        nav_items = [(l, d, v) for l, d, v in items if l]

        menu = InteractiveMenu("", nav_items)
        choice = menu.run()

        if choice is None or choice == "quit":
            print("\n  Stay swole! 💪\n")
            break
        elif choice == "log_exercise":
            config = log_exercise(config)
        elif choice == "log_routine":
            config = log_routine(config)
        elif choice == "suggest":
            config = suggest_exercise(config)
        elif choice == "stats":
            config = show_stats(config)
        elif choice == "history":
            config = show_history(config)
        elif choice == "config":
            config = show_config(config)


# --- Hook Commands (for Claude Code integration) ---

def cmd_hook_suggest(args):
    config = load_config()
    if not config.get("enabled", True):
        return

    cooldown = config.get("cooldown_minutes", 30)
    last_suggested_file = SWOLE_DIR / "last_suggested"
    if last_suggested_file.exists():
        last_time = datetime.datetime.fromisoformat(last_suggested_file.read_text().strip())
        if (datetime.datetime.now() - last_time).total_seconds() < cooldown * 60:
            return

    exercises = load_exercises() + config.get("custom_exercises", [])
    user_equipment = set(config.get("equipment", ["none"]))
    user_equipment.add("none")
    exercises = [e for e in exercises if not e.get("equipment") or
                 any(eq in user_equipment for eq in e.get("equipment", []))]

    if not exercises:
        return

    exercise = random.choice(exercises)
    count = exercise['count']
    unit = exercise.get('unit', 'reps')
    name = exercise['name']
    text = f"{count} {unit} {name}" if unit != "reps" else f"{count} {name}"

    SWOLE_DIR.mkdir(parents=True, exist_ok=True)
    with open(PENDING_FILE, "w") as f:
        json.dump({
            "type": "exercise", "exercise": text, "data": exercise,
            "task_description": args.task if args.task else "task",
            "suggested_at": datetime.datetime.now().isoformat()
        }, f)

    last_suggested_file.write_text(datetime.datetime.now().isoformat())
    print(text)

def cmd_hook_log_complete(args):
    if not PENDING_FILE.exists():
        return
    with open(PENDING_FILE) as f:
        pending = json.load(f)
    data = pending.get('data', {})
    if pending.get('type') == 'exercise':
        log_exercise_db(data.get('name', 'unknown'), data.get('count', 0),
                       data.get('unit', 'reps'), data.get('category', 'general'),
                       data.get('intensity', 'moderate'), pending.get('task_description', 'hook'))
    stats = get_stats_today()
    send_notification("Swole Code", "Logged!", f"Today: {stats['total_reps']} reps")
    os.remove(PENDING_FILE)

def cmd_hook_log_skip(args):
    if PENDING_FILE.exists():
        os.remove(PENDING_FILE)


# --- Morning Commands ---

def cmd_morning(args):
    """Main morning command handler."""
    if args.status:
        cmd_morning_status()
    elif args.complete:
        cmd_morning_complete(args.routine)
    elif args.skip:
        cmd_morning_skip()
    else:
        # Default: show status
        cmd_morning_status()


def cmd_morning_status():
    """Output morning status as JSON for skill parsing."""
    state = load_day_state()
    morning = state.get("morning", {})
    config = load_config()
    focus = get_todays_focus(config)

    output = {
        "date": state.get("date"),
        "status": morning.get("status", "pending"),
        "completed_at": morning.get("completed_at"),
        "routine_used": morning.get("routine_used"),
        "todays_focus": focus,
        "day_of_week": get_day_of_week()
    }
    print(json.dumps(output, indent=2))


def cmd_morning_complete(routine_name: Optional[str] = None):
    """Mark morning routine as completed."""
    state = load_day_state()
    state["morning"]["status"] = "completed"
    state["morning"]["completed_at"] = datetime.datetime.now().isoformat()
    if routine_name:
        state["morning"]["routine_used"] = routine_name
    save_day_state(state)
    print(json.dumps({"success": True, "status": "completed", "routine": routine_name}))


def cmd_morning_skip():
    """Mark morning routine as skipped."""
    state = load_day_state()
    state["morning"]["status"] = "skipped"
    save_day_state(state)
    print(json.dumps({"success": True, "status": "skipped"}))


# --- Queue Commands ---

def cmd_queue(args):
    """Main queue command handler."""
    if args.trigger:
        cmd_queue_trigger()
    elif args.cancel:
        cmd_queue_cancel()
    elif args.routine_id:
        cmd_queue_add(args.routine_id, args.trigger_type, args.description)
    else:
        cmd_queue_show()


def cmd_queue_show():
    """Show current queue status as JSON."""
    state = load_day_state()
    queue = state.get("workout_queue", {})
    print(json.dumps(queue, indent=2))


def cmd_queue_add(routine_id: str, trigger: str = "big_task", description: Optional[str] = None):
    """Queue a routine for later execution."""
    # Find the routine
    routines_data = load_routines_data()
    config = load_config()
    all_routines = routines_data.get("sample_routines", []) + config.get("custom_routines", [])

    routine = None
    for r in all_routines:
        if r.get("id") == routine_id or r.get("name", "").lower() == routine_id.lower():
            routine = r
            break

    if not routine:
        print(json.dumps({"success": False, "error": f"Routine not found: {routine_id}"}))
        return

    state = load_day_state()
    state["workout_queue"] = {
        "queued": True,
        "routine_id": routine.get("id", routine_id),
        "routine_name": routine.get("name"),
        "duration_minutes": routine.get("duration_minutes"),
        "trigger": trigger,
        "trigger_description": description,
        "queued_at": datetime.datetime.now().isoformat(),
        "triggered_at": None
    }
    save_day_state(state)

    print(json.dumps({
        "success": True,
        "queued": True,
        "routine_name": routine.get("name"),
        "duration_minutes": routine.get("duration_minutes"),
        "trigger": trigger,
        "trigger_description": description
    }))


def send_notification(title: str, subtitle: str, message: str, sound: str = "Glass"):
    """Send a macOS notification using terminal-notifier (preferred) or osascript fallback."""
    import shutil
    if shutil.which("terminal-notifier"):
        # terminal-notifier is more reliable for notifications
        cmd = ["terminal-notifier", "-title", title, "-subtitle", subtitle, "-message", message, "-sound", sound]
        import subprocess
        subprocess.run(cmd, capture_output=True)
    else:
        # Fallback to osascript (may require permissions)
        os.system(f'''osascript -e 'display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "{sound}"' ''')


def cmd_queue_trigger():
    """Trigger the queued workout (show notification)."""
    state = load_day_state()
    queue = state.get("workout_queue", {})

    if not queue.get("queued"):
        print(json.dumps({"success": False, "error": "No workout queued"}))
        return

    routine_name = queue.get("routine_name", "workout")
    duration = queue.get("duration_minutes", "?")
    trigger_desc = queue.get("trigger_description", "")

    # Mark as triggered
    state["workout_queue"]["triggered_at"] = datetime.datetime.now().isoformat()
    save_day_state(state)

    # Show macOS notification
    subtitle = f"{duration} min"
    message = trigger_desc if trigger_desc else "Time to move!"
    send_notification("SWOLE CODE - Workout Time!", subtitle, routine_name, "Glass")

    print(json.dumps({
        "success": True,
        "triggered": True,
        "routine_name": routine_name,
        "duration_minutes": duration
    }))


def cmd_queue_cancel():
    """Clear the queued workout."""
    state = load_day_state()
    state["workout_queue"] = {
        "queued": False,
        "routine_id": None,
        "routine_name": None,
        "duration_minutes": None,
        "trigger": None,
        "trigger_description": None,
        "queued_at": None,
        "triggered_at": None
    }
    save_day_state(state)
    print(json.dumps({"success": True, "cancelled": True}))


# --- Day Command ---

def cmd_day():
    """Output full day state as JSON."""
    state = load_day_state()
    print(json.dumps(state, indent=2))


# --- Main ---

def cmd_config_get():
    """Output current config as JSON."""
    config = load_config()
    print(json.dumps(config, indent=2))


def cmd_config_set(key: str, value: str):
    """Set a config value. Supports dot notation and JSON values."""
    config = load_config()

    # Parse value - try JSON first, then string
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        # Check for boolean strings
        if value.lower() == 'true':
            parsed_value = True
        elif value.lower() == 'false':
            parsed_value = False
        else:
            parsed_value = value

    # Handle dot notation (e.g., "quiet_hours.enabled")
    keys = key.split('.')
    target = config
    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]

    target[keys[-1]] = parsed_value
    save_config(config)
    print(f"Set {key} = {json.dumps(parsed_value)}")


def cmd_config_add(key: str, value: str):
    """Add a value to a list config (e.g., equipment, categories)."""
    config = load_config()

    if key not in config:
        config[key] = []

    if not isinstance(config[key], list):
        print(f"Error: {key} is not a list")
        return

    # Parse value
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value

    if parsed_value not in config[key]:
        config[key].append(parsed_value)
        save_config(config)
        print(f"Added {parsed_value} to {key}")
    else:
        print(f"{parsed_value} already in {key}")


def cmd_config_remove(key: str, value: str):
    """Remove a value from a list config."""
    config = load_config()

    if key not in config or not isinstance(config[key], list):
        print(f"Error: {key} is not a list")
        return

    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value

    if parsed_value in config[key]:
        config[key].remove(parsed_value)
        save_config(config)
        print(f"Removed {parsed_value} from {key}")
    else:
        print(f"{parsed_value} not in {key}")


def cmd_add_exercise(exercise_json: str):
    """Add a custom exercise from JSON."""
    config = load_config()

    try:
        exercise = json.loads(exercise_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")
        return

    # Validate required fields
    required = ['name', 'count', 'category', 'intensity']
    for field in required:
        if field not in exercise:
            print(f"Error: Missing required field '{field}'")
            return

    exercise['custom'] = True
    custom = config.get('custom_exercises', [])
    custom.append(exercise)
    config['custom_exercises'] = custom
    save_config(config)
    print(f"Added custom exercise: {exercise['name']}")


def cmd_stats_json():
    """Output today's stats as JSON."""
    init_db()  # Ensure tables exist
    today = datetime.date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()

    cur.execute('''
        SELECT COUNT(*), COALESCE(SUM(count), 0)
        FROM exercises
        WHERE completed = 1 AND date(timestamp) = ?
    ''', (today,))
    exercises_today, reps_today = cur.fetchone()

    cur.execute('''
        SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0)
        FROM routine_completions
        WHERE date(timestamp) = ?
    ''', (today,))
    routines_today, routine_mins = cur.fetchone()

    # Category breakdown
    cur.execute('''
        SELECT category, COUNT(*), SUM(count)
        FROM exercises
        WHERE completed = 1 AND date(timestamp) = ?
        GROUP BY category
    ''', (today,))
    categories = {row[0]: {'count': row[1], 'reps': row[2]} for row in cur.fetchall()}

    conn.close()

    stats = {
        'date': today,
        'exercises': exercises_today or 0,
        'reps': reps_today or 0,
        'routines': routines_today or 0,
        'routine_minutes': routine_mins or 0,
        'categories': categories
    }
    print(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Swole Code - Workouts while AI works")
    subparsers = parser.add_subparsers(dest='command')

    p_suggest = subparsers.add_parser('suggest', help='Suggest an exercise (for hooks)')
    p_suggest.add_argument('--task', help='Task description')
    subparsers.add_parser('log-complete', help='Log pending as complete (for hooks)')
    subparsers.add_parser('log-skip', help='Skip pending (for hooks)')

    # Config commands for programmatic access
    subparsers.add_parser('config-get', help='Output config as JSON')
    p_config_set = subparsers.add_parser('config-set', help='Set a config value')
    p_config_set.add_argument('key', help='Config key (dot notation supported)')
    p_config_set.add_argument('value', help='Value (JSON or string)')

    p_config_add = subparsers.add_parser('config-add', help='Add value to a list')
    p_config_add.add_argument('key', help='List key (e.g., equipment)')
    p_config_add.add_argument('value', help='Value to add')

    p_config_remove = subparsers.add_parser('config-remove', help='Remove value from a list')
    p_config_remove.add_argument('key', help='List key')
    p_config_remove.add_argument('value', help='Value to remove')

    p_add_ex = subparsers.add_parser('add-exercise', help='Add custom exercise from JSON')
    p_add_ex.add_argument('json', help='Exercise JSON')

    subparsers.add_parser('stats', help='Output today\'s stats as JSON')

    # Morning commands
    p_morning = subparsers.add_parser('morning', help='Morning planning flow')
    p_morning.add_argument('--status', action='store_true', help='Show morning status (JSON)')
    p_morning.add_argument('--complete', action='store_true', help='Mark morning as completed')
    p_morning.add_argument('--skip', action='store_true', help='Skip morning routine')
    p_morning.add_argument('--routine', help='Routine name used (for --complete)')

    # Queue commands
    p_queue = subparsers.add_parser('queue', help='Workout queue management')
    p_queue.add_argument('routine_id', nargs='?', help='Routine ID to queue')
    p_queue.add_argument('--trigger', action='store_true', help='Trigger queued workout')
    p_queue.add_argument('--cancel', action='store_true', help='Cancel queued workout')
    p_queue.add_argument('--trigger-type', default='big_task',
                        help='Trigger type: big_task, victory, manual (default: big_task)')
    p_queue.add_argument('--description', help='Description of what triggers the workout')

    # Day state command
    subparsers.add_parser('day', help='Output full day state as JSON')

    args = parser.parse_args()

    if args.command == 'suggest':
        cmd_hook_suggest(args)
    elif args.command == 'log-complete':
        cmd_hook_log_complete(args)
    elif args.command == 'log-skip':
        cmd_hook_log_skip(args)
    elif args.command == 'config-get':
        cmd_config_get()
    elif args.command == 'config-set':
        cmd_config_set(args.key, args.value)
    elif args.command == 'config-add':
        cmd_config_add(args.key, args.value)
    elif args.command == 'config-remove':
        cmd_config_remove(args.key, args.value)
    elif args.command == 'add-exercise':
        cmd_add_exercise(args.json)
    elif args.command == 'stats':
        cmd_stats_json()
    elif args.command == 'morning':
        cmd_morning(args)
    elif args.command == 'queue':
        cmd_queue(args)
    elif args.command == 'day':
        cmd_day()
    else:
        main_menu()

if __name__ == "__main__":
    main()
