import json
import csv
import logging
import unittest
from pathlib import Path
from datetime import datetime, date

DATA_FILE   = Path("expenses_data.json")
LOG_FILE    = Path("tracker.log")
CSV_FILE    = Path("expenses_export.csv")
MAX_ALLOWED = 1_000_000.00
MONTHLY_BUDGET = 2000.00

class C:
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def load_all_users():
    """Load the entire multi-user data store from JSON."""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Could not read data file: {e}")
    return {}


def save_all_users(store):
    """Persist the entire multi-user data store to JSON."""
    try:
        DATA_FILE.write_text(json.dumps(store, indent=2, default=str))
    except OSError as e:
        logging.error(f"Could not write data file: {e}")


class ExpenseTracker:
    """
    Backend engine for a single user's expenses.

    Follows the Accumulator Pattern (Page 11):
        State(new) = State(old) + Input
    """

    def __init__(self, username, data=None):
        self.username = username
        data = data or {}

        
        self.total        = data.get("total", 0.0)
        self.transactions = data.get("transactions", [])  
        self.categories   = data.get("categories", {})    
        self.daily_totals = data.get("daily_totals", {})   

    
    def add_expense(self, amount, category):
        timestamp = datetime.now().isoformat(timespec="seconds")
        today     = date.today().isoformat()

        # 1. Append to history
        self.transactions.append({
            "amount":    amount,
            "category":  category,
            "timestamp": timestamp,
        })

        # 2. Accumulate total
        self.total += amount

        # 3. Accumulate per-category
        self.categories[category] = self.categories.get(category, 0.0) + amount

        # 4. Accumulate per-day
        self.daily_totals[today] = self.daily_totals.get(today, 0.0) + amount

        logging.info(
            f"[{self.username}] +${amount:.2f} in '{category}' | total=${self.total:.2f}"
        )

    def undo_last(self):
        if not self.transactions:
            return None

        last      = self.transactions.pop()
        amount    = last["amount"]
        category  = last["category"]
        day       = last["timestamp"][:10]

        # Reverse every accumulator
        self.total -= amount
        self.categories[category] = self.categories.get(category, 0.0) - amount
        if self.categories[category] <= 0:
            self.categories.pop(category, None)

        self.daily_totals[day] = self.daily_totals.get(day, 0.0) - amount
        if self.daily_totals[day] <= 0:
            self.daily_totals.pop(day, None)

        logging.warning(f"[{self.username}] UNDO ${amount:.2f} from '{category}'")
        return last

    
    def to_dict(self):
        return {
            "total":        self.total,
            "transactions": self.transactions,
            "categories":   self.categories,
            "daily_totals": self.daily_totals,
        }

    
    def print_summary(self):
        print(f"\n{C.BOLD}{'=' * 52}{C.RESET}")
        print(f"{C.BOLD}         FINAL EXPENSE REPORT — {self.username.upper()}{C.RESET}")
        print(f"{C.BOLD}{'=' * 52}{C.RESET}")
        print(f"  Transactions Processed : {len(self.transactions)}")
        print(f"  FINAL TOTAL            : {C.GREEN}${self.total:.2f}{C.RESET}")

        if self.categories:
            print(f"\n  {C.CYAN}Breakdown by Category:{C.RESET}")
            for cat, amt in sorted(self.categories.items(),
                                   key=lambda x: x[1], reverse=True):
                pct = (amt / self.total * 100) if self.total else 0
                bar = "█" * int(pct / 5)   # 20-char bar max
                print(f"    {cat:<12} ${amt:>9.2f}  {pct:>5.1f}%  {bar}")

        if self.daily_totals:
            print(f"\n  {C.CYAN}Daily Totals:{C.RESET}")
            for day, amt in sorted(self.daily_totals.items()):
                print(f"    {day}  ->  ${amt:.2f}")

        self._check_budget()
        print(f"{C.BOLD}{'=' * 52}{C.RESET}\n")

    def _check_budget(self):
        if self.total > MONTHLY_BUDGET:
            print(f"\n  {C.RED}🚨 BUDGET EXCEEDED by "
                  f"${self.total - MONTHLY_BUDGET:.2f}{C.RESET}")
        elif self.total > MONTHLY_BUDGET * 0.8:
            pct = self.total / MONTHLY_BUDGET * 100
            print(f"\n  {C.YELLOW}⚠️  {pct:.1f}% of monthly "
                  f"budget used.{C.RESET}")

    def print_history(self, limit=10):
        if not self.transactions:
            print(f"{C.DIM}  No transactions yet.{C.RESET}")
            return
        print(f"\n{C.BOLD}  Last {min(limit, len(self.transactions))} "
              f"Transactions:{C.RESET}")
        for tx in self.transactions[-limit:]:
            print(f"    {tx['timestamp']}  "
                  f"{tx['category']:<12} ${tx['amount']:>9.2f}")
        print()

    
    def export_csv(self, filename=CSV_FILE):
        if not self.transactions:
            print(f"{C.YELLOW}  Nothing to export.{C.RESET}")
            return
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f,
                                    fieldnames=["timestamp", "category", "amount"])
            writer.writeheader()
            writer.writerows(self.transactions)
        print(f"{C.GREEN}  📄 Exported {len(self.transactions)} rows "
              f"to {filename}{C.RESET}")
        logging.info(f"[{self.username}] Exported {len(self.transactions)} rows")



HELP_TEXT = f"""
{C.BOLD}AVAILABLE COMMANDS{C.RESET}
  {C.CYAN}<number>{C.RESET}    Add an expense (e.g. 100)
  {C.CYAN}undo{C.RESET}        Remove the last transaction
  {C.CYAN}history{C.RESET}     Show the last 10 transactions
  {C.CYAN}summary{C.RESET}     Show total + breakdown
  {C.CYAN}export{C.RESET}      Save all transactions to CSV
  {C.CYAN}help{C.RESET}        Show this help
  {C.CYAN}quit{C.RESET}        Save & exit gracefully
"""


def prompt_category():
    """Ask for a category but never block the flow."""
    cat = input(f"  {C.DIM}Category [General]: {C.RESET}").strip()
    return cat.title() if cat else "General"


def handle_command(tracker, cmd):
    """Dispatch table for non-numeric commands."""
    if cmd == "help":
        print(HELP_TEXT)
    elif cmd == "history":
        tracker.print_history()
    elif cmd == "summary":
        tracker.print_summary()
    elif cmd == "export":
        tracker.export_csv()
    elif cmd == "undo":
        undone = tracker.undo_last()
        if undone:
            print(f"{C.YELLOW}  ↩️  Undid ${undone['amount']:.2f} "
                  f"from '{undone['category']}'{C.RESET}")
        else:
            print(f"{C.DIM}  Nothing to undo.{C.RESET}")
    else:
        print(f"{C.RED}  Unknown command. Type 'help'.{C.RESET}")


def run_tracker():
    """Main interactive session — the IPO loop."""
    print(f"\n{C.BOLD}{'=' * 52}{C.RESET}")
    print(f"{C.BOLD}   DECODELABS EXPENSE TRACKER v2{C.RESET}")
    print(f"{C.BOLD}{'=' * 52}{C.RESET}")

    
    store    = load_all_users()
    username = input("  Login name: ").strip().lower() or "guest"

    if username not in store:
        store[username] = {}
        print(f"{C.GREEN}  🆕 New user '{username}' created.{C.RESET}")
    else:
        print(f"{C.GREEN}  👋 Welcome back, {username}!{C.RESET}")

    tracker = ExpenseTracker(username, store[username])

    print(f"\n  Type {C.CYAN}help{C.RESET} for commands, "
          f"{C.CYAN}quit{C.RESET} to exit.")
    print(f"  Type a {C.CYAN}number{C.RESET} to log an expense.\n")

    
    while True:
        raw = input(f"{C.BOLD}[{username}] ${tracker.total:.2f} > {C.RESET}").strip()

        if not raw:
            continue

        low = raw.lower()

    
        if low in ("quit", "exit", "q"):
            print(f"\n{C.CYAN}  [SYSTEM] Saving and shutting down...{C.RESET}")
            store[username] = tracker.to_dict()
            save_all_users(store)
            logging.info(f"[{username}] Session ended. "
                         f"Total=${tracker.total:.2f}")
            tracker.print_summary()
            break

        
        if low in ("help", "history", "summary", "export", "undo"):
            handle_command(tracker, low)
            continue

        
        try:
            amount = float(raw)
        except ValueError:
            print(f"{C.RED}  ❌ Invalid Data. Enter a number or a command.{C.RESET}")
            logging.warning(f"[{username}] Invalid input: {raw!r}")
            continue

        if amount <= 0:
            print(f"{C.YELLOW}  ⚠️  Amount must be greater than 0.{C.RESET}")
            continue

        if amount > MAX_ALLOWED:
            print(f"{C.RED}  ⚠️  Amount exceeds limit of "
                  f"${MAX_ALLOWED:,.2f}{C.RESET}")
            continue

    
        category = prompt_category()
        tracker.add_expense(amount, category)
        print(f"{C.GREEN}  ✅ Added ${amount:.2f} to '{category}' | "
              f"Running Total: ${tracker.total:.2f}{C.RESET}")

        
        store[username] = tracker.to_dict()
        save_all_users(store)



class TestExpenseTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = ExpenseTracker("tester")

    def test_accumulator_basic(self):
        self.tracker.add_expense(100, "Food")
        self.tracker.add_expense(50, "Travel")
        self.assertEqual(self.tracker.total, 150.0)  

    def test_string_concat_disaster(self):
        
        self.assertNotEqual("100" + "50", 150)
        self.assertEqual(int("100") + int("50"), 150)

    def test_undo_reverses_everything(self):
        self.tracker.add_expense(100, "Food")
        self.tracker.add_expense(50, "Travel")
        self.tracker.undo_last()
        self.assertEqual(self.tracker.total, 100.0)
        self.assertNotIn("Travel", self.tracker.categories)

    def test_categories_accumulate(self):
        self.tracker.add_expense(30, "Food")
        self.tracker.add_expense(20, "Food")
        self.assertEqual(self.tracker.categories["Food"], 50.0)

    def test_daily_totals(self):
        self.tracker.add_expense(10, "Food")
        today = date.today().isoformat()
        self.assertEqual(self.tracker.daily_totals[today], 10.0)

    def test_serialization_roundtrip(self):
        self.tracker.add_expense(75, "Bills")
        data = self.tracker.to_dict()
        restored = ExpenseTracker("tester", data)
        self.assertEqual(restored.total, 75.0)
        self.assertEqual(len(restored.transactions), 1)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1].lower() == "test":
        sys.argv = [sys.argv[0]]
        unittest.main(verbosity=2)
    else:
        try:
            run_tracker()
        except KeyboardInterrupt:
            print(f"\n\n{C.YELLOW}  [SYSTEM] Interrupted. "
                  f"Progress saved.{C.RESET}")
            logging.warning("Session interrupted by user (Ctrl+C)")