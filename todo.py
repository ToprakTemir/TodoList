#!/usr/bin/env python3
import json
import time
import os
import shutil
import subprocess
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
import sys, tty, termios, select

console = Console()

# GLOBAL VARIABLES
hours_per_day = 8  # <-- This can be adjusted from the menu

# File paths – adjust these if needed
TASKS_FILE = "/Users/toprak/TodoList/tasks.json"
RECURRING_TEMPLATES_FILE = "/Users/toprak/TodoList/recurring_templates.json"
BASE_DIR = os.path.dirname(TASKS_FILE)
NOTES_DIR = os.path.join(BASE_DIR, "Notes")


class Task:
    def __init__(self, name):
        self.name = name
        self.type = None
        self.due_date = None  # in seconds since epoch
        self.remaining_days = None
        self.estimated_hours = None
        self.progress = 0.0  # percent of task completed, default 0
        self.percent_time_required = None
        self.panic_factor = None

    def __str__(self):
        ret = f"Task: {self.name}\n"
        if self.type:
            ret += f"Type: {self.type.upper()}\n"
        if self.due_date:
            ret += f"Due: {time.strftime('%Y-%m-%d', time.localtime(self.due_date))}\n"
        if self.estimated_hours is not None:
            ret += f"Estimated time in hours (total): {self.estimated_hours}\n"
        ret += f"Progress: {self.progress:.2f}%\n"
        if self.percent_time_required is not None:
            ret += f"% time required: {self.percent_time_required:.2f}%\n"
        if self.panic_factor is not None:
            ret += f"Panic factor: {self.panic_factor:.2f}\n"
        return ret

    def set_due_date(self, inp):
        try:
            if inp.lower() == "today":
                now = time.time()
                self.due_date = now - (now % 86400) + 86400
            elif inp.lower() == "tomorrow":
                now = time.time()
                self.due_date = now - (now % 86400) + 2 * 86400
            elif "days" in inp:
                days = int(inp.split()[0])
                now = time.time()
                self.due_date = now - (now % 86400) + days * 86400
            elif inp.lower() == "next week":
                now = time.time()
                self.due_date = now - (now % 86400) + 7 * 86400
            else:
                weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                if inp.lower() in weekdays:
                    current_time = time.localtime()
                    current_weekday = current_time.tm_wday  # Monday is 0
                    target_weekday = weekdays.index(inp.lower())
                    days_ahead = (target_weekday - current_weekday) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    self.due_date = time.time() - (time.time() % 86400) + days_ahead * 86400
                else:
                    for sep in ['/', '.', '-']:
                        if sep in inp:
                            parts = inp.split(sep)
                            if len(parts) == 3:
                                day, month, year = parts
                                self.due_date = time.mktime((int(year), int(month), int(day), 0, 0, 0, 0, 0, 0))
                                break
                    else:
                        console.print(
                            "[red]Invalid date format. Please use dd/mm/yyyy, dd-mm-yyyy, or dd.mm.yyyy.[/red]")
                        return
            self.complete_fields()
        except Exception as e:
            console.print(f"[red]Error setting due date: {e}[/red]")

    def complete_fields(self):
        try:
            now = time.time()
            if self.due_date:
                self.remaining_days = (self.due_date - now) / 86400
            if (self.estimated_hours is not None) and (self.estimated_hours > 0):
                remaining_hours = self.estimated_hours * (1 - self.progress / 100.0)
                if self.remaining_days and self.remaining_days > 0:
                    self.percent_time_required = (remaining_hours / (self.remaining_days * hours_per_day)) * 100
                else:
                    self.percent_time_required = 100.0 if remaining_hours > 0 else 0.0
                needed_days = remaining_hours / hours_per_day if hours_per_day else 0
                if needed_days > 0 and self.remaining_days:
                    panic_ratio = self.remaining_days / needed_days
                else:
                    panic_ratio = 0
                panic_ratio -= 1
                panic_ratio = max(0, panic_ratio)
                safety_interval_days = 10
                max_panic = 10
                panic_ratio /= (safety_interval_days - 1)
                panic_ratio = max(0, 1 - (panic_ratio ** 1.5))
                self.panic_factor = panic_ratio * max_panic
            else:
                self.percent_time_required = 0.0
                self.panic_factor = 0.0
        except Exception as e:
            console.print(f"[red]Error completing fields: {e}[/red]")

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "due_date": self.due_date,
            "remaining_days": self.remaining_days,
            "estimated_hours": self.estimated_hours,
            "progress": self.progress,
            "percent_time_required": self.percent_time_required,
            "panic_factor": self.panic_factor,
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(data["name"])
        task.type = data.get("type")
        task.due_date = float(data.get("due_date")) if data.get("due_date") is not None else None
        task.remaining_days = float(data.get("remaining_days")) if data.get("remaining_days") is not None else None
        task.estimated_hours = float(data.get("estimated_hours")) if data.get("estimated_hours") is not None else None
        task.progress = float(data.get("progress")) if data.get("progress") is not None else 0.0
        task.percent_time_required = float(data.get("percent_time_required")) if data.get(
            "percent_time_required") is not None else None
        task.panic_factor = float(data.get("panic_factor")) if data.get("panic_factor") is not None else None
        return task


def load_tasks(filename=TASKS_FILE):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r") as f:
            tasks_data = json.load(f)
            return [Task.from_dict(task) for task in tasks_data]
    except json.JSONDecodeError:
        console.print("[red]Error decoding tasks.json. Starting with an empty task list.[/red]")
        return []
    except Exception as e:
        console.print(f"[red]Error loading tasks: {e}[/red]")
        return []


def save_tasks(tasks, filename=TASKS_FILE):
    try:
        with open(filename, "w") as f:
            json.dump([task.to_dict() for task in tasks], f, indent=4)
    except Exception as e:
        console.print(f"[red]Error saving tasks: {e}[/red]")


def add_task():
    name = Prompt.ask("Name of the task").strip()
    if not name:
        console.print("[red]Task name cannot be empty.[/red]")
        return None

    task = Task(name)
    task_type = Prompt.ask("Type of the task (or press Enter to skip)", default="")
    if task_type:
        task.type = task_type

    estimated_hours_input = Prompt.ask("Estimated hours of the task (or press Enter to skip)", default="")
    if estimated_hours_input:
        try:
            task.estimated_hours = float(estimated_hours_input)
        except ValueError:
            console.print("[red]Invalid input for estimated hours. Please enter a number.[/red]")
            return None

    task.progress = 0
    due_date = Prompt.ask(
        "Due date of the task (e.g., today, tomorrow, Monday, dd/mm/yyyy) or press Enter to skip",
        default=""
    ).strip()
    if due_date:
        task.set_due_date(due_date)

    task.complete_fields()
    console.print("[green]Task added successfully![/green]")
    return task


def panic_to_rgb(panic):
    panic = max(0, min(10, panic))
    if panic <= 5:
        fraction = panic / 5.0
        r = int(0 + (255 - 0) * fraction)
        g = 255
        b = 0
    else:
        fraction = (panic - 5.0) / 5.0
        r = 255
        g = int(255 - (255 * fraction))
        b = 0
    return r, g, b


def display_tasks(tasks):
    if not tasks:
        console.print("[yellow]No tasks to display.[/yellow]")
        return {}

    max_name_length = 0
    for t in tasks:
        max_name_length = max(max_name_length, len(t.name))
    name_col_width = max(15, max_name_length)
    tasks_by_type = {}
    for t in tasks:
        t_type = t.type if t.type else "N/A"
        tasks_by_type.setdefault(t_type, []).append(t)
    global_index = 1
    tasks_map = {}
    for t_type, tasks_in_group in tasks_by_type.items():
        table_title = f"\n[bold bright_white] Tasks: {t_type} [/bold bright_white]"
        table = Table(title=table_title, show_header=True, show_lines=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", justify="right", width=2)
        table.add_column("Name", style="bright_cyan", min_width=name_col_width, no_wrap=True)
        table.add_column("Rem. Days", style="bright_white", width=9, justify="right")
        table.add_column("Due Date", style="bright_yellow", width=8, justify="right")
        table.add_column("Hours", style="bright_blue", width=6, justify="right")
        table.add_column("Progress", style="bright_white", width=9, justify="right")
        table.add_column("% Time", style="bright_white", width=6, justify="right")
        table.add_column("Panic", style="bold bright_red", width=6, justify="right")

        for task in tasks_in_group:
            due_date_str = time.strftime("%d.%m.%y", time.localtime(task.due_date)) if task.due_date else "N/A"
            est_hours = f"{int(task.estimated_hours)}" if (task.estimated_hours is not None) else "N/A"
            days_remaining = f"{task.remaining_days:.2f}" if (task.remaining_days is not None) else "N/A"
            percent_time = f"{task.percent_time_required:.2f}%" if (task.percent_time_required is not None) else "N/A"
            progress_str = f"{task.progress:.2f}%"
            panic_level = task.panic_factor if task.panic_factor else 0
            r, g, b = panic_to_rgb(panic_level)
            panic_str = f"[rgb({r},{g},{b})]{panic_level:.2f}[/rgb({r},{g},{b})]"
            table.add_row(
                str(global_index),
                task.name,
                days_remaining,
                due_date_str,
                est_hours,
                progress_str,
                percent_time,
                panic_str
            )
            tasks_map[global_index] = task
            global_index += 1

        console.print(table)
    return tasks_map


def sort_tasks(tasks, primary_key, secondary_key="type"):
    def sort_key(task):
        def normalize_value(value):
            if isinstance(value, str):
                return value.lower()
            elif value is None:
                return -float('inf')
            return value

        primary = normalize_value(getattr(task, primary_key))
        secondary = normalize_value(getattr(task, secondary_key))
        return (primary, secondary)
    tasks.sort(key=sort_key, reverse=True)


def sort_tasks_custom(tasks):
    sort_fields = {
        "1": "name",
        "2": "type",
        "3": "due_date",
        "4": "estimated_hours",
        "5": "remaining_days",
        "6": "percent_time_required",
        "7": "panic_factor",
        "8": "progress"
    }
    sort_menu = Panel(
        "\n".join([
            "[bold]Sort by which field?[/bold]",
            " [1] Name",
            " [2] Type",
            " [3] Due Date",
            " [4] Estimated Hours",
            " [5] Days Remaining",
            " [6] % Time Required",
            " [7] Panic Factor",
            " [8] Progress %",
            " [q] Cancel"
        ]),
        title="Sort Options",
        border_style="blue"
    )
    console.print(sort_menu)
    choice = Prompt.ask("Enter your choice", default="").strip().lower()
    if choice == "q":
        console.print("[yellow]Sort canceled.[/yellow]")
        return
    if choice not in sort_fields:
        console.print("[red]Invalid choice. Sorting canceled.[/red]")
        return
    primary_key = sort_fields[choice]
    sort_tasks(tasks, primary_key, secondary_key="type")
    console.print(f"[green]Tasks sorted by {primary_key.replace('_', ' ').title()} and then by Type.[/green]")


def adjust_terminal_size():
    desired_columns = 100
    desired_rows = 42
    current_size = shutil.get_terminal_size()
    current_columns = current_size.columns
    current_rows = current_size.lines
    if current_columns < desired_columns or current_rows < desired_rows:
        os.system(f"printf '\033[8;{desired_rows};{desired_columns}t'")


def edit_task(tasks, tasks_map):
    if not tasks:
        console.print("[yellow]No tasks to edit.[/yellow]")
        return
    index_str = Prompt.ask("Task number to edit (global)", default="").strip()
    if not index_str.isdigit():
        console.print("[red]Please enter a valid number.[/red]")
        return
    index = int(index_str)
    if index not in tasks_map:
        console.print("[red]Invalid task number.[/red]")
        return
    task = tasks_map[index]
    console.print(f"[bold blue]Editing Task: {task.name}[/bold blue]")
    new_name = Prompt.ask(f"New name (or press Enter to keep: {task.name})", default=task.name).strip()
    task.name = new_name
    new_type = Prompt.ask(f"New type (or press Enter to keep: {task.type})", default=task.type or "").strip()
    task.type = new_type if new_type else None
    new_estimated_hours = Prompt.ask(
        f"New estimated hours (or press Enter to keep: {task.estimated_hours})",
        default=str(task.estimated_hours or "")
    ).strip()
    if new_estimated_hours:
        try:
            task.estimated_hours = float(new_estimated_hours)
        except ValueError:
            console.print("[red]Invalid input for estimated hours. Keeping the original value.[/red]")
    new_progress = Prompt.ask(
        f"New progress % (0-100) (or press Enter to keep: {task.progress})",
        default=str(task.progress)
    ).strip()
    if new_progress:
        try:
            progress_val = float(new_progress)
            if 0 <= progress_val <= 100:
                task.progress = progress_val
            else:
                console.print("[red]Progress must be between 0 and 100. Keeping the old value.[/red]")
        except ValueError:
            console.print("[red]Invalid input for progress. Keeping the original value.[/red]")
    new_due_date = Prompt.ask(
        f"New due date (e.g., today, tomorrow, Monday, dd/mm/yyyy, or press Enter to keep: "
        f"{time.strftime('%Y-%m-%d', time.localtime(task.due_date)) if task.due_date else 'N/A'})",
        default=""
    ).strip()
    if new_due_date:
        task.set_due_date(new_due_date)
    task.complete_fields()
    console.print("[green]Task updated successfully![/green]")
    save_tasks(tasks)


def delete_task(tasks, tasks_map):
    if not tasks:
        console.print("[yellow]No tasks to delete.[/yellow]")
        return
    index_str = Prompt.ask("Task number to delete (global)", default="").strip()
    if not index_str.isdigit():
        console.print("[red]Please enter a valid number.[/red]")
        return
    index = int(index_str)
    if index not in tasks_map:
        console.print("[red]Invalid task number.[/red]")
        return
    removed_task = tasks_map[index]
    tasks.remove(removed_task)
    save_tasks(tasks)
    console.print(f"[green]Deleted task: {removed_task.name}[/green]")


def sum_percent_time_required(tasks):
    return sum((task.percent_time_required or 0) for task in tasks)


def update_dates(tasks):
    for task in tasks:
        task.complete_fields()
    return tasks


# ----- New Functions for Recurring Tasks -----

def load_recurring_templates(filename=RECURRING_TEMPLATES_FILE):
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[red]Error loading recurring templates: {e}[/red]")
        return []


def save_recurring_templates(templates, filename=RECURRING_TEMPLATES_FILE):
    try:
        with open(filename, "w") as f:
            json.dump(templates, f, indent=4)
    except Exception as e:
        console.print(f"[red]Error saving recurring templates: {e}[/red]")


def check_and_generate_recurring_tasks(tasks):
    templates = load_recurring_templates()
    now = time.time()
    updated = False
    for template in templates:
        if not template.get("enabled", True):
            continue
        try:
            frequency = float(template.get("frequency", 24))
        except Exception:
            frequency = 24.0
        freq_sec = frequency * 3600
        last_creation = template.get("last_creation_date", 0)
        # If never generated before, assume starting from one period ago
        if not last_creation:
            last_creation = now - freq_sec
        next_time = last_creation + freq_sec
        # Generate tasks for each missed interval
        while next_time <= now:
            # Set due date to the end of the day (midnight) for the day of next_time
            due_date = next_time - (next_time % 86400) + 86400
            task = Task(template.get("name", "Recurring Task"))
            # Set the task type from the recurring template, so it won't be None.
            task.type = template.get("type", "recurring")
            task.estimated_hours = float(template.get("estimated_hours", 0.01667))
            task.due_date = float(due_date)
            task.complete_fields()
            tasks.append(task)
            next_time += freq_sec
            updated = True
        # Update last_creation_date to the last scheduled generation time (or now if none generated)
        template["last_creation_date"] = next_time - freq_sec if next_time > now else now
    if updated:
        save_recurring_templates(templates)


def manage_recurring_tasks():
    templates = load_recurring_templates()
    while True:
        console.print("\n[bold blue]Recurring Tasks Management[/bold blue]")
        if templates:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", justify="right")
            table.add_column("Name")
            table.add_column("Frequency")
            table.add_column("Enabled")
            table.add_column("Last Creation", justify="center")
            table.add_column("Estimated Hours", justify="right")
            for i, t in enumerate(templates, start=1):
                last_creation = time.strftime("%Y-%m-%d", time.localtime(t.get("last_creation_date", 0))) if t.get("last_creation_date") else "N/A"
                table.add_row(
                    str(i),
                    t.get("name", ""),
                    str(t.get("frequency", "")),  # Convert frequency float to string
                    str(t.get("enabled", True)),
                    last_creation,
                    str(t.get("estimated_hours", ""))
                )
            console.print(table)
        else:
            console.print("[yellow]No recurring task templates found.[/yellow]")

        panel = Panel("\n".join([
            "[bold]Options:[/bold]",
            " [A] Add a new recurring task template",
            " [M] Modify an existing template",
            " [T] Toggle enable/disable a template",
            " [D] Delete a template",
            " [Q] Quit recurring tasks management"
        ]), title="Recurring Tasks Options", border_style="blue")
        console.print(panel)

        choice = Prompt.ask("Enter your choice").strip().lower()
        if choice == "q":
            break
        elif choice == "a":
            name = Prompt.ask("Enter task name")
            frequency = Prompt.ask("Enter frequency (n hours)", default="24")
            try:
                frequency = float(frequency)
            except:
                console.print("[red]Invalid frequency. Using default 24 hours.[/red]")
                frequency = 24
            estimated_hours = Prompt.ask("Enter estimated hours", default="0.05")
            try:
                estimated_hours = float(estimated_hours)
            except:
                console.print("[red]Invalid estimated hours. Using default 0.05.[/red]")
                estimated_hours = 0.05
            new_template = {
                "name": name,
                "frequency": frequency,
                "enabled": True,
                "last_creation_date": 0,
                "estimated_hours": estimated_hours
            }
            templates.append(new_template)
            save_recurring_templates(templates)
            console.print("[green]New recurring task template added.[/green]")
        elif choice == "m":
            index = Prompt.ask("Enter template ID to modify")
            if not index.isdigit() or int(index) < 1 or int(index) > len(templates):
                console.print("[red]Invalid ID.[/red]")
                continue
            idx = int(index) - 1
            template = templates[idx]
            new_name = Prompt.ask("Enter new name", default=template.get("name", ""))
            new_frequency = Prompt.ask("Enter new frequency (in hours)", default=str(template.get("frequency", 24)))
            new_estimated_hours = Prompt.ask("Enter new estimated hours", default=str(template.get("estimated_hours", 0.01667)))
            try:
                new_frequency = float(new_frequency)
            except Exception:
                console.print("[red]Invalid frequency. Keeping original.[/red]")
                new_frequency = template.get("frequency", 24)
            try:
                new_estimated_hours = float(new_estimated_hours)
            except Exception:
                console.print("[red]Invalid estimated hours. Keeping original.[/red]")
                new_estimated_hours = template.get("estimated_hours", 0.01667)
            template["name"] = new_name
            template["frequency"] = new_frequency
            template["estimated_hours"] = new_estimated_hours
            save_recurring_templates(templates)
            console.print("[green]Template modified.[/green]")
        elif choice == "t":
            index = Prompt.ask("Enter template ID to toggle enable/disable")
            if not index.isdigit() or int(index) < 1 or int(index) > len(templates):
                console.print("[red]Invalid ID.[/red]")
                continue
            idx = int(index) - 1
            templates[idx]["enabled"] = not templates[idx].get("enabled", True)
            save_recurring_templates(templates)
            status = "enabled" if templates[idx]["enabled"] else "disabled"
            console.print(f"[green]Template {status}.[/green]")
        elif choice == "d":
            index = Prompt.ask("Enter template ID to delete")
            if not index.isdigit() or int(index) < 1 or int(index) > len(templates):
                console.print("[red]Invalid ID.[/red]")
                continue
            idx = int(index) - 1
            removed = templates.pop(idx)
            save_recurring_templates(templates)
            console.print(f"[green]Deleted template: {removed.get('name', '')}[/green]")
        else:
            console.print("[red]Invalid choice.[/red]")


# ----- New Functions for Notebook/Notes Feature -----

def manage_notes(current_path=NOTES_DIR):
    if not os.path.exists(current_path):
        os.makedirs(current_path)
    while True:
        console.print(f"\n[bold blue]Notes Management: {current_path}[/bold blue]")
        items = os.listdir(current_path)
        folders = [item for item in items if os.path.isdir(os.path.join(current_path, item))]
        notes = [item for item in items if os.path.isfile(os.path.join(current_path, item)) and item.endswith(".txt")]

        if folders:
            console.print("[bold]Folders:[/bold]")
            for i, folder in enumerate(folders, start=1):
                console.print(f"  [{i}] {folder}")
        else:
            console.print("[yellow]No subfolders found.[/yellow]")
        if notes:
            console.print("[bold]Notes:[/bold]")
            for i, note in enumerate(notes, start=1):
                console.print(f"  ({i}) {note}")
        else:
            console.print("[yellow]No notes found in this folder.[/yellow]")

        panel = Panel("\n".join([
            "[bold]Options:[/bold]",
            " [C] Create new note",
            " [E] Edit a note",
            " rm:    Delete a note",
            " mkdir: Create new folder",
            " cd:    Open a subfolder",
            " cd ..:  Go up one level",
            " [Q] Quit Notes"
        ]), title="Notes Options", border_style="green")
        console.print(panel)
        choice = Prompt.ask("Enter your choice").strip().lower()
        if choice == "q":
            break
        elif choice == "c":
            note_name = Prompt.ask("Enter new note name (without .txt)").strip()
            if not note_name:
                console.print("[red]Note name cannot be empty.[/red]")
                continue
            note_file = os.path.join(current_path, note_name + ".txt")
            if os.path.exists(note_file):
                console.print("[red]A note with that name already exists. Please choose a different name.[/red]")
                continue
            with open(note_file, "w") as f:
                f.write("")
            os.system(f"vim '{note_file}'")
        elif choice == "e":
            if not notes:
                console.print("[red]No notes to edit.[/red]")
                continue
            note_index = Prompt.ask("Enter note number to edit").strip()
            if not note_index.isdigit() or int(note_index) < 1 or int(note_index) > len(notes):
                console.print("[red]Invalid note number.[/red]")
                continue
            note_file = os.path.join(current_path, notes[int(note_index) - 1])
            os.system(f"vim '{note_file}'")
        elif choice == "rm":
            if not notes:
                console.print("[red]No notes to delete.[/red]")
                continue
            note_index = Prompt.ask("Enter note number to delete").strip()
            if not note_index.isdigit() or int(note_index) < 1 or int(note_index) > len(notes):
                console.print("[red]Invalid note number.[/red]")
                continue
            note_file = os.path.join(current_path, notes[int(note_index) - 1])
            confirm = Prompt.ask(f"Are you sure you want to delete {notes[int(note_index) - 1]}? (y/n)",
                                 default="n").strip().lower()
            if confirm == "y":
                os.remove(note_file)
                console.print("[green]Note deleted.[/green]")
        elif choice == "mkdir":
            new_folder = Prompt.ask("Enter new subfolder name").strip()
            if not new_folder:
                console.print("[red]Folder name cannot be empty.[/red]")
                continue
            new_folder_path = os.path.join(current_path, new_folder)
            if os.path.exists(new_folder_path):
                console.print("[red]Folder already exists.[/red]")
                continue
            os.makedirs(new_folder_path)
            console.print("[green]Subfolder created.[/green]")
        elif choice == "cd":
            if not folders:
                console.print("[red]No subfolders to open.[/red]")
                continue
            folder_index = Prompt.ask("Enter folder number to open").strip()
            if not folder_index.isdigit() or int(folder_index) < 1 or int(folder_index) > len(folders):
                console.print("[red]Invalid folder number.[/red]")
                continue
            new_path = os.path.join(current_path, folders[int(folder_index) - 1])
            manage_notes(new_path)
        elif choice == "cd ..":
            if os.path.abspath(current_path) == os.path.abspath(NOTES_DIR):
                console.print("[red]Already at root notes folder.[/red]")
            else:
                parent = os.path.dirname(current_path)
                manage_notes(parent)
                break
        elif choice.startswith("cd "):
            choice = choice.split()
            if len(choice) != 2:
                console.print("[red]Invalid choice.[/red]")
                continue
            folder_id = choice[1]
            if not folder_id.isdigit() or int(folder_id) < 1 or int(folder_id) > len(folders):
                console.print("[red]Invalid folder number.[/red]")
                continue
            new_path = os.path.join(current_path, folders[int(folder_id) - 1])
            manage_notes(new_path)
        else:
            console.print("[red]Invalid choice.[/red]")


# ----- Main Menu -----

def main_menu():
    global hours_per_day
    os.system('clear')
    adjust_terminal_size()
    tasks = load_tasks()
    tasks = update_dates(tasks)
    # Generate recurring tasks from templates (if any)
    check_and_generate_recurring_tasks(tasks)
    save_tasks(tasks)
    # Initial sort: by panic_factor then by type
    sort_tasks(tasks, primary_key="panic_factor")

    while True:
        console.print("\n[bold blue] One must imagine sisyphus happy [/bold blue]")
        tasks_map = display_tasks(tasks)
        total_percent = sum_percent_time_required(tasks)
        console.print(f"\n[bold green]working hours per day: {hours_per_day}[/bold green]")
        console.print(f"[bold green]Sum of % Time Required: {total_percent:.2f}%[/bold green]")

        menu_panel = Panel(
            "\n".join([
                "[bold]Options:[/bold]",
                " [A] Add a new task",
                " [D] Delete a task",
                " [E] Edit a task",
                " [S] Sort tasks",
                " [H] Set hours of work per day",
                " [N] Notes",
                " [R] Recurring Tasks",
                " [Q] Quit"
            ]),
            title="Menu",
            border_style="green"
        )
        console.print(menu_panel)
        choice = Prompt.ask("Enter your choice").strip().lower()
        if choice == "a":
            os.system('clear')
            task = add_task()
            if task:
                tasks.append(task)
                sort_tasks(tasks, primary_key="type", secondary_key="due_date")
                save_tasks(tasks)
        elif choice == "d":
            os.system('clear')
            display_tasks(tasks)
            delete_task(tasks, tasks_map)
        elif choice == "e":
            os.system('clear')
            display_tasks(tasks)
            edit_task(tasks, tasks_map)
        elif choice == "s":
            os.system('clear')
            display_tasks(tasks)
            sort_tasks_custom(tasks)
            save_tasks(tasks)
        elif choice == "h":
            os.system('clear')
            current_value = str(hours_per_day)
            new_value = Prompt.ask(
                f"Enter hours of work per day (current: {current_value})",
                default=current_value
            )
            try:
                hours_per_day = float(new_value)
                for t in tasks:
                    t.complete_fields()
                save_tasks(tasks)
                console.print(f"[green]Hours per day set to {hours_per_day}. Tasks updated accordingly![/green]")
            except ValueError:
                console.print("[red]Invalid input. Please enter a numeric value.[/red]")
        elif choice == "n":
            os.system('clear')
            manage_notes()
        elif choice == "r":
            os.system('clear')
            manage_recurring_tasks()
        elif choice == "q":
            console.print("[bold green]Goodbye![/bold green]")
            break
        else:
            console.print("[red]Invalid choice. Please select a valid option.[/red]")


if __name__ == "__main__":
    main_menu()