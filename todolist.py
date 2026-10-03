import json
import os
from datetime import datetime, timedelta

class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"


def c(text, color):
    """Wrap text in a color code."""
    return f"{color}{text}{Color.RESET}"

class TaskManager:
    """
    The Model Layer (Slide 12 - Decoupling the Architecture).
    Handles all data logic. Zero UI code here.
    """

    DATA_FILE = "tasks.json"
    PRIORITY_ORDER = {"High": 1, "Medium": 2, "Low": 3}

    def __init__(self):
        self.users = {}          
        self.current_user = None
        self.history = []        
        self.next_id = 1
        self.load()

    # ---------- USER MANAGEMENT ----------
    def switch_user(self, username):
        """Multi-user support — like Bigtable row keys (Slide 18)."""
        self.current_user = username
        if username not in self.users:
            self.users[username] = []
            print(c(f"👤 New user created: '{username}'", Color.CYAN))
        else:
            print(c(f"👤 Switched to user: '{username}'", Color.CYAN))

    def _current_tasks(self):
        return self.users.setdefault(self.current_user, [])

    # ---------- CRUD OPERATIONS ----------
    def add_task(self, description, priority="Medium", due_days=3):
        """CREATE — append a new task (O(1) amortized, Slide 8)."""
        if not description.strip():
            print(c("⚠️  Task cannot be empty.", Color.YELLOW))
            return

        task = {
            "id": self.next_id,
            "task": description.strip(),
            "priority": priority.capitalize(),
            "done": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "due": (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d"),
        }
        self._current_tasks().append(task)
        self.history.append(("add", task["id"]))
        self.next_id += 1
        print(c(f"✅ Task added: '{description}' [{priority}]", Color.GREEN))

    def view_tasks(self, filter_mode="all"):
        """READ — display tasks with enumerate() (Slide 11)."""
        tasks = self._current_tasks()
        if not tasks:
            print(c("\n📭 Your to-do list is empty.", Color.YELLOW))
            return

        # Apply filter
        if filter_mode == "pending":
            tasks = [t for t in tasks if not t["done"]]
        elif filter_mode == "completed":
            tasks = [t for t in tasks if t["done"]]
        elif filter_mode == "overdue":
            today = datetime.now().strftime("%Y-%m-%d")
            tasks = [t for t in tasks if not t["done"] and t["due"] < today]

        if not tasks:
            print(c(f"\n📭 No tasks match filter: '{filter_mode}'.", Color.YELLOW))
            return

        # Sort by priority
        tasks = sorted(tasks, key=lambda t: self.PRIORITY_ORDER.get(t["priority"], 2))

        print("\n" + c("=" * 60, Color.BLUE))
        print(c(f"         📋 TO-DO LIST — {self.current_user.upper()}", Color.BOLD))
        print(c("=" * 60, Color.BLUE))

        today = datetime.now().strftime("%Y-%m-%d")
        for index, task in enumerate(tasks, start=1):
            status = c("✔", Color.GREEN) if task["done"] else c("○", Color.YELLOW)
            overdue = (not task["done"]) and task["due"] < today
            due_str = c(task["due"], Color.RED) if overdue else task["due"]
            prio_color = {
                "High": Color.RED,
                "Medium": Color.YELLOW,
                "Low": Color.GREEN,
            }.get(task["priority"], Color.GRAY)

            print(
                f"  {status} [{index}] "
                f"{c('ID:' + str(task['id']), Color.GRAY)} "
                f"{task['task']} "
                f"[{c(task['priority'], prio_color)}] "
                f"(due: {due_str})"
            )
        print(c("=" * 60, Color.BLUE))
        print(f"  Total shown: {len(tasks)}")

    def update_task(self, task_id, new_description):
        """UPDATE — edit an existing task."""
        task = self._find_by_id(task_id)
        if not task:
            print(c(f"❌ Task ID {task_id} not found.", Color.RED))
            return
        old = task["task"]
        task["task"] = new_description
        self.history.append(("update", task_id, old))
        print(c(f"✏️  Updated ID {task_id}: '{old}' → '{new_description}'", Color.GREEN))

    def delete_task(self, task_id):
        """DELETE — remove a task by ID."""
        task = self._find_by_id(task_id)
        if not task:
            print(c(f"❌ Task ID {task_id} not found.", Color.RED))
            return
        self._current_tasks().remove(task)
        self.history.append(("delete", task))
        print(c(f"🗑️  Deleted: '{task['task']}'", Color.GREEN))

    def toggle_complete(self, task_id):
        """Mark a task complete/incomplete."""
        task = self._find_by_id(task_id)
        if not task:
            print(c(f"❌ Task ID {task_id} not found.", Color.RED))
            return
        task["done"] = not task["done"]
        state = "completed ✔" if task["done"] else "reopened ○"
        print(c(f"🔄 Task ID {task_id} {state}", Color.GREEN))

    def clear_all(self):
        """Wipe all tasks for the current user."""
        confirm = input(c("⚠️  Delete ALL tasks for this user? (yes/no): ", Color.YELLOW))
        if confirm.strip().lower() == "yes":
            self.history.append(("clear", list(self._current_tasks())))
            self._current_tasks().clear()
            print(c("🧹 All tasks cleared.", Color.GREEN))

    # ---------- SEARCH & FILTER ----------
    def search_tasks(self, keyword):
        """Filter tasks by keyword (list comprehension)."""
        results = [t for t in self._current_tasks() if keyword.lower() in t["task"].lower()]
        if not results:
            print(c(f"🔍 No tasks matching '{keyword}'.", Color.YELLOW))
            return
        print(c(f"\n🔍 Found {len(results)} match(es) for '{keyword}':", Color.CYAN))
        for i, t in enumerate(results, start=1):
            print(f"  {i}. [{t['id']}] {t['task']} ({t['priority']})")

    # ---------- STATS ----------
    def show_stats(self):
        """Dashboard view — completion progress."""
        tasks = self._current_tasks()
        total = len(tasks)
        if total == 0:
            print(c("\n📊 No tasks to analyze.", Color.YELLOW))
            return
        done = sum(1 for t in tasks if t["done"])
        pending = total - done
        percent = (done / total) * 100
        bar_len = 30
        filled = int(bar_len * done / total)
        bar = "█" * filled + "░" * (bar_len - filled)

        print("\n" + c("=" * 60, Color.MAGENTA))
        print(c(f"         📊 STATS — {self.current_user.upper()}", Color.BOLD))
        print(c("=" * 60, Color.MAGENTA))
        print(f"  Total     : {total}")
        print(f"  Completed : {c(done, Color.GREEN)}")
        print(f"  Pending   : {c(pending, Color.YELLOW)}")
        print(f"  Progress  : [{c(bar, Color.GREEN)}] {percent:.1f}%")
        print(c("=" * 60, Color.MAGENTA))

    # ---------- UNDO (Stack / LIFO) ----------
    def undo(self):
        """Undo the last destructive action."""
        if not self.history:
            print(c("↩️  Nothing to undo.", Color.YELLOW))
            return
        action = self.history.pop()

        if action[0] == "add":
            task = self._find_by_id(action[1])
            if task:
                self._current_tasks().remove(task)
                print(c(f"↩️  Undid add (ID {action[1]}).", Color.CYAN))

        elif action[0] == "update":
            _, tid, old = action
            task = self._find_by_id(tid)
            if task:
                task["task"] = old
                print(c(f"↩️  Undid update (ID {tid}).", Color.CYAN))

        elif action[0] == "delete":
            self._current_tasks().append(action[1])
            print(c(f"↩️  Restored: '{action[1]['task']}'", Color.CYAN))

        elif action[0] == "clear":
            self.users[self.current_user] = action[1]
            print(c("↩️  Restored all cleared tasks.", Color.CYAN))

    # ---------- PERSISTENCE (JSON) — Slide 14 ----------
    def save(self):
        """Serialize RAM → Disk."""
        try:
            with open(self.DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "users": self.users,
                    "current_user": self.current_user,
                    "next_id": self.next_id,
                }, f, indent=2)
            print(c(f"💾 Saved to {self.DATA_FILE}", Color.GREEN))
        except OSError as e:
            print(c(f"❌ Save failed: {e}", Color.RED))

    def load(self):
        """Deserialize Disk → RAM."""
        if not os.path.exists(self.DATA_FILE):
            return
        try:
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.users = data.get("users", {})
            self.current_user = data.get("current_user")
            self.next_id = data.get("next_id", 1)
            print(c(f"📂 Loaded from {self.DATA_FILE}", Color.CYAN))
        except (OSError, json.JSONDecodeError) as e:
            print(c(f"⚠️  Could not load data: {e}", Color.YELLOW))

    # ---------- HELPERS ----------
    def _find_by_id(self, task_id):
        for t in self._current_tasks():
            if t["id"] == task_id:
                return t
        return None



class ConsoleUI:
    """The View Layer — only prints and collects input."""

    def __init__(self, manager):
        self.mgr = manager

    def banner(self):
        print(c("\n" + "═" * 60, Color.MAGENTA))
        print(c("   🧠  DECODELABS TO-DO MANAGER — ULTIMATE EDITION", Color.BOLD))
        print(c("   Batch 2026 | Powered by DecodeLabs", Color.GRAY))
        print(c("═" * 60, Color.MAGENTA))

    def menu(self):
        print(c("\n" + "─" * 60, Color.BLUE))
        print(c(f"  👤 User: {self.mgr.current_user or 'None'}", Color.CYAN))
        print(c("─" * 60, Color.BLUE))
        print("  1.  Add task            8.  Search tasks")
        print("  2.  View all tasks      9.  Filter (pending/completed/overdue)")
        print("  3.  Update task        10.  Undo last action")
        print("  4.  Delete task        11.  Show stats")
        print("  5.  Toggle complete    12.  Switch user")
        print("  6.  Clear all tasks    13.  Save")
        print("  7.  Exit               14.  Load")
        print(c("─" * 60, Color.BLUE))

    def ask_int(self, prompt):
        """Safe integer input with validation."""
        while True:
            try:
                return int(input(c(prompt, Color.CYAN)).strip())
            except ValueError:
                print(c("❌ Please enter a valid number.", Color.RED))

    def ask_str(self, prompt):
        return input(c(prompt, Color.CYAN)).strip()

    def run(self):
        self.banner()

        # Ensure a user is selected
        if not self.mgr.current_user:
            name = self.ask_str("Enter your username: ")
            self.mgr.switch_user(name or "guest")

        while True:
            self.menu()
            choice = self.ask_str("Enter your choice (1-14): ")

            try:
                if choice == "1":
                    desc = self.ask_str("Task description: ")
                    prio = self.ask_str("Priority [High/Medium/Low] (default Medium): ") or "Medium"
                    days = self.ask_str("Due in how many days? (default 3): ") or "3"
                    self.mgr.add_task(desc, prio, int(days))

                elif choice == "2":
                    self.mgr.view_tasks()

                elif choice == "3":
                    tid = self.ask_int("Task ID to update: ")
                    new = self.ask_str("New description: ")
                    self.mgr.update_task(tid, new)

                elif choice == "4":
                    tid = self.ask_int("Task ID to delete: ")
                    self.mgr.delete_task(tid)

                elif choice == "5":
                    tid = self.ask_int("Task ID to toggle: ")
                    self.mgr.toggle_complete(tid)

                elif choice == "6":
                    self.mgr.clear_all()

                elif choice == "7":
                    self.mgr.save()
                    print(c("\n👋 Goodbye! Your tasks are saved (RAM → Disk).", Color.GREEN))
                    break

                elif choice == "8":
                    kw = self.ask_str("Search keyword: ")
                    self.mgr.search_tasks(kw)

                elif choice == "9":
                    mode = self.ask_str("Filter [pending/completed/overdue/all]: ") or "all"
                    self.mgr.view_tasks(mode)

                elif choice == "10":
                    self.mgr.undo()

                elif choice == "11":
                    self.mgr.show_stats()

                elif choice == "12":
                    name = self.ask_str("Switch to user: ")
                    self.mgr.switch_user(name)

                elif choice == "13":
                    self.mgr.save()

                elif choice == "14":
                    self.mgr.load()

                else:
                    print(c("❌ Invalid choice. Enter 1–14.", Color.RED))

            except (ValueError, TypeError) as e:
                print(c(f"⚠️  Input error: {e}", Color.YELLOW))
            except Exception as e:
                print(c(f"💥 Unexpected error: {e}", Color.RED))

def main():
    manager = TaskManager()
    ui = ConsoleUI(manager)
    try:
        ui.run()
    except KeyboardInterrupt:
        print(c("\n\n⚠️  Interrupted. Auto-saving...", Color.YELLOW))
        manager.save()
        print(c("👋 Session ended safely.", Color.GREEN))


if __name__ == "__main__":
    main()