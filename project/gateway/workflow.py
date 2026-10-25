import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "data" / "finance" / "expenses.csv"
OUTPUT = BASE / "runtime" / "finance" / "expenses_cleaned.csv"


def clean_expenses(identity):
    # Authorize BEFORE any file access.
    if (
        identity.get("team") != "Finance"
        or identity.get("role") != "finance_reader"
    ):
        raise PermissionError("finance_workflow_access_denied")

    cleaned = []
    seen = {}
    rejected = []
    duplicates = 0
    input_rows = 0
    total = Decimal("0.00")

    with SOURCE.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != ["expense_id", "vendor", "amount"]:
            raise ValueError("unexpected_csv_columns")

        for line, row in enumerate(reader, start=2):
            input_rows += 1
            expense_id = (row.get("expense_id") or "").strip()
            vendor = (row.get("vendor") or "").strip()
            raw_amount = (row.get("amount") or "").strip()

            try:
                amount = Decimal(raw_amount)
                if (
                    not amount.is_finite()
                    or amount <= 0
                    or amount > Decimal("1000000000")
                ):
                    raise ValueError()
                rounded = amount.quantize(Decimal("0.01"))
                if amount != rounded:
                    raise ValueError()
                amount = rounded
            except (InvalidOperation, ValueError):
                rejected.append({"line": line, "reason": "invalid_amount"})
                continue

            if not expense_id or not vendor or None in row:
                rejected.append({"line": line, "reason": "invalid_fields"})
                continue

            # Block CSV/Spreadsheet formula injection
            if any(v.lstrip().startswith(("=", "+", "-", "@")) or any(ord(c) < 32 for c in v)
                   for v in (expense_id, vendor)):
                rejected.append({"line": line, "reason": "unsafe_spreadsheet_text"})
                continue

            record = (vendor, amount)
            if expense_id in seen:
                if seen[expense_id] == record:
                    duplicates += 1
                else:
                    rejected.append({
                        "line": line,
                        "reason": "conflicting_expense_id"
                    })
                continue

            seen[expense_id] = record
            cleaned.append({
                "expense_id": expense_id,
                "vendor": vendor,
                "amount": format(amount, ".2f")
            })
            total += amount

    OUTPUT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=["expense_id", "vendor", "amount"]
        )
        writer.writeheader()
        writer.writerows(cleaned)

    return {
        "input_rows": input_rows,
        "cleaned_rows": len(cleaned),
        "duplicate_rows": duplicates,
        "rejected_rows": len(rejected),
        "rejections": rejected,
        "total_amount": format(total, ".2f"),
        "currency": "THB",
        "output_file": str(OUTPUT.relative_to(BASE))
    }
