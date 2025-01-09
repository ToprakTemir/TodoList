#!/usr/bin/env python3
import json
import time
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
import os
import shutil

console = Console()

# GLOBAL VARIABLES
hours_per_day = 8  # <-- We will make this adjustable from the menu

class Task:
    def __init__(self, name):
        self.name = name
        self.type = None
        self.due_date = None  # in seconds since epoch
        self.remaining_days = None
        self.estimated_hours = None
        self.percent_time_required = None
        self.panic_factor = None

    def __str__(self):
        ret = f"Task: {self.name}\n"
        if self.type:
            ret += f"Type: {self.type.upper()}\n"
        if self.due_date:
            ret += f"Due: {time.strftime('%Y-%m-%d', time.localtime(self.due_date))}\n"
        if self.estimated_hours is not None:
            ret += f"Estimated time in hours: {self.estimated_hours}\n"
        if self.percent_time_required is not None:
            ret += f"% time required: {self.percent_time_required:.2f}%\n"
        if self.panic_factor is not None:
            ret += f"Panic factor: {self.panic_factor:.2f}\n"
        return ret

    def set_due_date(self, inp):
        try:
            if inp.lower() == "today":
                # set to midnight today
                now = time.time()
                self.due_date = now - (now % 86400) + 86400
            elif inp.lower() == "tomorrow":
                # set to midnight tomorrow
                now = time.time()
                self.due_date = now - (now % 86400) + 2 * 86400
            else:
                # Check if input is a weekday
                weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                if inp.lower() in weekdays:
                    current_time = time.localtime()
                    current_weekday = current_time.tm_wday  # Monday is 0
                    target_weekday = weekdays.index(inp.lower())
                    days_ahead = (target_weekday - current_weekday) % 7
                    if days_ahead == 0:
                        days_ahead = 7  # Next week
                    self.due_date = time.time() - (time.time() % 86400) + days_ahead * 86400
                else:
                    # Parse date in formats: dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy
                    for sep in ['/', '.', '-']:
                        if sep in inp:
                            parts = inp.split(sep)
                            if len(parts) == 3:
                                day, month, year = parts
                                self.due_date = time.mktime((int(year), int(month), int(day), 0, 0, 0, 0, 0, 0))
                                break
                    else:
                        console.print("[red]Invalid date format. Please use dd/mm/yyyy, dd-mm-yyyy, or dd.mm.yyyy.[/red]")
                        return
            self.complete_fields()
        except Exception as e:
            console.print(f"[red]Error setting due date: {e}[/red]")

    def complete_fields(self):
        """
        Recalculates fields (remaining_days, percent_time_required, panic_factor)
        based on current due_date, estimated_hours, and the global hours_per_day.
        """
        try:
            if self.due_date and self.estimated_hours:
                # Calculate remaining days based on work hours per day
                self.remaining_days = (self.due_date - time.time()) / 86400  # total days to deadline

                # Avoid division by zero or negative day counts
                if self.remaining_days > 0:
                    self.percent_time_required = (self.estimated_hours / (self.remaining_days * hours_per_day)) * 100
                else:
                    # If it's overdue or 0 days left, set to 100% for clarity
                    self.percent_time_required = 100.0

                max_panic = 10
                safety_interval_days = 10

                # panic_factor: tries to measure how 'compressed' the timeline is
                needed_days = self.estimated_hours / hours_per_day
                panic_factor = self.remaining_days / needed_days
                panic_factor -= 1
                panic_factor = max(0, panic_factor)  # no negative
                panic_factor /= (safety_interval_days - 1)
                panic_factor = max(0, 1 - (panic_factor ** 1.5))  # clamp between 0 and 1
                self.panic_factor = panic_factor * max_panic

            elif self.due_date:
                # If estimated_hours is not set, calculate remaining_days purely on due_date
                self.remaining_days = (self.due_date - time.time()) / 86400
        except Exception as e:
            console.print(f"[red]Error completing fields: {e}[/red]")

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "due_date": self.due_date,
            "remaining_days": self.remaining_days,
            "estimated_hours": self.estimated_hours,
            "percent_time_required": self.percent_time_required,
            "panic_factor": self.panic_factor,
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(data["name"])
        task.type = data.get("type")
        task.due_date = data.get("due_date")
        task.remaining_days = data.get("remaining_days")
        task.estimated_hours = data.get("estimated_hours")
        task.percent_time_required = data.get("percent_time_required")
        task.panic_factor = data.get("panic_factor")
        return task


def load_tasks(filename="/Users/toprak/TodoList/tasks.json"):
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


def save_tasks(tasks, filename="/Users/toprak/TodoList/tasks.json"):
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
    """
    Returns an (R, G, B) tuple for a panic level in [0..10].
    0  -> Green (0,255,0)
    5  -> Yellow (255,255,0)
    10 -> Red (255,0,0)
    """
    # Ensure panic is within bounds
    panic = max(0, min(10, panic))

    if panic <= 5:
        # Interpolate between Green (0,255,0) and Yellow (255,255,0)
        fraction = panic / 5.0
        r = int(0   + (255 - 0)   * fraction)
        g = int(255 + (255 - 255) * fraction)  # stays 255
        b = int(0   + (0   - 0)   * fraction)  # stays 0
    else:
        # Interpolate between Yellow (255,255,0) and Red (255,0,0)
        fraction = (panic - 5.0) / 5.0
        r = int(255 + (255 - 255) * fraction)  # stays 255
        g = int(255 - (255 - 0)   * fraction)  # 255 down to 0
        b = int(0   + (0   - 0)   * fraction)  # stays 0

    return r, g, b


def display_tasks(tasks):
    """
    Show tasks in separate tables, grouped by their type, but with a single
    global numbering that spans all tables.

    Returns:
        tasks_map (dict): A dictionary mapping [global_index -> Task object].
    """
    if not tasks:
        console.print("[yellow]No tasks to display.[/yellow]")
        return {}

    # 1) Determine the widest name length across *all* tasks
    max_name_length = 0
    for t in tasks:
        max_name_length = max(max_name_length, len(t.name))

    # We'll force the 'Name' column to have a minimum width
    # enough to handle the longest name (plus a little padding).
    name_col_width = max(15, max_name_length)

    # 2) Group tasks by type
    tasks_by_type = {}
    for t in tasks:
        t_type = t.type if t.type else "N/A"
        tasks_by_type.setdefault(t_type, []).append(t)

    # 3) We'll build a global index that runs across all tables
    global_index = 1
    tasks_map = {}

    # 4) For each type group, build and print a table
    for t_type, tasks_in_group in tasks_by_type.items():
        table_title = f"\n[bold bright_white] Tasks: {t_type} [/bold bright_white]"
        table = Table(title=table_title, show_header=True, show_lines=True, header_style="bold magenta")

        # We omit the Type column (since each table *is* that type).
        table.add_column("ID", style="cyan", justify="right", width=2)
        table.add_column("Name", style="bright_cyan", min_width=name_col_width, no_wrap=True)
        table.add_column("Rem. Days", style="bright_white", width=9, justify="right")
        table.add_column("Due Date", style="bright_yellow", width=8, justify="right")
        table.add_column("Hours", style="bright_blue", width=6, justify="right")
        table.add_column("% Time", style="bright_white", width=6, justify="right")
        table.add_column("Panic", style="bold bright_red", width=6, justify="right")

        for task in tasks_in_group:
            # Prepare data
            due_date_str = time.strftime("%d.%m.%y", time.localtime(task.due_date)) if task.due_date else "N/A"
            est_hours = f"{int(task.estimated_hours)}" if (task.estimated_hours is not None) else "N/A"
            days_remaining = f"{task.remaining_days:.2f}" if (task.remaining_days is not None) else "N/A"
            percent_time = f"{task.percent_time_required:.2f}%" if (task.percent_time_required is not None) else "N/A"

            # -- COLORIZE THE PANIC FACTOR --
            panic_level = task.panic_factor if task.panic_factor else 0
            r, g, b = panic_to_rgb(panic_level)
            panic_str = f"[rgb({r},{g},{b})]{panic_level:.2f}[/rgb({r},{g},{b})]"

            table.add_row(
                str(global_index),
                task.name,
                days_remaining,
                due_date_str,
                est_hours,
                percent_time,
                panic_str
            )


            # Map the global index to the actual Task object
            tasks_map[global_index] = task
            global_index += 1

        console.print(table)

    return tasks_map


def sort_tasks(tasks, primary_key, secondary_key="type"):
    """
    Sort tasks by primary_key and then by secondary_key.
    """
    def sort_key(task):
        def normalize_value(value):
            if isinstance(value, str):
                return value.lower()
            elif value is None:
                # Put None-values at the far end by returning -∞ for primary sorting
                return -float('inf')
            return value

        primary = normalize_value(getattr(task, primary_key))
        secondary = normalize_value(getattr(task, secondary_key))
        return (primary, secondary)

    tasks.sort(key=sort_key, reverse=True)


def sort_tasks_custom(tasks):
    """
    Allow the user to sort tasks by a selected field.
    """
    sort_fields = {
        "1": "name",
        "2": "type",
        "3": "due_date",
        "4": "estimated_hours",
        "5": "remaining_days",
        "6": "percent_time_required",
        "7": "panic_factor"
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
    sort_tasks(tasks, primary_key, secondary_key="type")  # Always secondarily sort by Type

    console.print(f"[green]Tasks sorted by {primary_key.replace('_', ' ').title()} and then by Type.[/green]")


def adjust_terminal_size():
    """
    Adjusts the terminal size to ensure it fits the application needs.
    """
    desired_columns = 100  # Minimum width for comfortable display
    desired_rows = 42      # Minimum height for comfortable display

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

    # Edit task attributes
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

    new_due_date = Prompt.ask(
        f"New due date (e.g., today, tomorrow, Monday, dd/mm/yyyy, or press Enter to keep: "
        f"{time.strftime('%Y-%m-%d', time.localtime(task.due_date)) if task.due_date else 'N/A'})",
        default=""
    ).strip()
    if new_due_date:
        task.set_due_date(new_due_date)

    # Recalculate fields after editing
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
    """
    Returns the sum of all percent_time_required fields across tasks.
    """
    return sum((task.percent_time_required or 0) for task in tasks)


def update_dates(tasks):
    """
    Update the remaining_days field for each task based on the current time.
    """
    for task in tasks:
        if task.due_date:
            task.complete_fields()
    return tasks


def main_menu():
    global hours_per_day

    os.system('clear')
    adjust_terminal_size()

    tasks = load_tasks()
    tasks = update_dates(tasks)

    # Initial sorting: first by panic_factor, then by type
    sort_tasks(tasks, primary_key="panic_factor")

    while True:
        console.print("\n[bold blue] One must imagine sisyphus happy [/bold blue]")

        # Show tasks (grouped by type, but with a global numbering)
        tasks_map = display_tasks(tasks)


        # Display sum of % Time Required
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
                " [H] Set hours of work per day",  # <-- New menu option
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
                # Re-sort after adding a new task
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
                # Recalculate fields for each task based on the new hours_per_day
                for t in tasks:
                    t.complete_fields()
                save_tasks(tasks)
                console.print(f"[green]Hours per day set to {hours_per_day}. Tasks updated accordingly![/green]")
            except ValueError:
                console.print("[red]Invalid input. Please enter a numeric value.[/red]")

        elif choice == "q":
            console.print("[bold green]Goodbye![/bold green]")
            break

        else:
            console.print("[red]Invalid choice. Please select a valid option.[/red]")


if __name__ == "__main__":
    main_menu()