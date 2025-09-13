"""
Script to import CSV transactions into Actual Budget server.
Supports the Italian bank CSV format with semicolon delimiters.
"""

import argparse
import csv
import decimal
import datetime
import sys
import os
from typing import Optional, Dict, Any
from pathlib import Path

from actual import Actual
from actual.queries import get_account, create_account, create_transaction

# Try to load dotenv if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def parse_date(date_str: str) -> datetime.date:
    """Parse date in DD/MM/YYYY format."""
    try:
        return datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected DD/MM/YYYY")


def parse_amount(amount_str: str) -> decimal.Decimal:
    """Parse amount string with European formatting (dots as thousands separator, comma as decimal separator)."""
    try:
        # Clean the amount string
        amount_str = amount_str.strip()
        if not amount_str:
            raise ValueError("Empty amount string")

        # Handle European number format: 3.388,00 -> 3388.00
        # If there's both dot and comma, dot is thousands separator
        if "." in amount_str and "," in amount_str:
            # Remove dots (thousands separators) and replace comma with dot
            amount_str = amount_str.replace(".", "").replace(",", ".")
        elif "," in amount_str and "." not in amount_str:
            # Only comma present, it's the decimal separator
            amount_str = amount_str.replace(",", ".")
        # If only dots present, they could be decimal separators (keep as is)

        return decimal.Decimal(amount_str)
    except (decimal.InvalidOperation, ValueError) as e:
        print(f"Error parsing amount '{amount_str}': {e}")
        raise


def extract_payee_from_description(description: str) -> str:
    """Extract a meaningful payee name from the transaction description."""
    description = description.strip()
    lines = description.split("\n")

    # Try different extraction methods in order
    payee = (
        _extract_pos_payee(lines)
        or _extract_transfer_payee(lines)
        or _extract_direct_debit_payee(lines)
        or _extract_fallback_payee(lines, description)
    )

    return payee.title() if payee else "Unknown"


def _extract_pos_payee(lines: list[str]) -> str:
    """Extract payee from POS payment descriptions."""
    for line in lines:
        line = line.strip()
        if not ("PAGAMENTO POS" in line or "PAGAMENTO" in line):
            continue

        # Handle PayPal transactions
        payee = _extract_paypal_payee(line)
        if payee:
            return payee

        # Handle SumUp transactions
        payee = _extract_sumup_payee(line)
        if payee:
            return payee

        # Handle Google services
        payee = _extract_google_payee(line)
        if payee:
            return payee

        # Handle standard POS payments with CARTA pattern
        payee = _extract_carta_payee(line)
        if payee:
            return payee

    return ""


def _extract_paypal_payee(line: str) -> str:
    """Extract PayPal merchant name."""
    if "PAYPAL" not in line.upper():
        return ""

    parts = line.split()
    for i, part in enumerate(parts):
        if "PAYPAL" in part.upper() and i + 1 < len(parts):
            parts[i + 1] = parts[i + 1].strip("*")
            payee = " ".join(parts[i + 1 : -1])
            if payee:
                return payee
    return ""


def _extract_sumup_payee(line: str) -> str:
    """Extract SumUp merchant name."""
    if "SUMUP" not in line.upper():
        return ""

    parts = line.split()
    for i, part in enumerate(parts):
        if "SUMUP" in part.upper() and i + 1 < len(parts):
            parts[i + 1] = parts[i + 1].strip("*")
            payee = " ".join(parts[i + 1 : -1])
            if payee:
                return payee
    return ""


def _extract_google_payee(line: str) -> str:
    """Extract Google service name."""
    if "GOOGLE*" not in line.upper():
        return ""

    parts = line.split()
    for part in parts:
        if "GOOGLE*" in part.upper():
            payee = part.split("*", 1)[-1]
            if payee:
                return payee
    return ""


def _extract_carta_payee(line: str) -> str:
    """Extract merchant name from CARTA pattern."""
    if not ("CARTA" in line and "DI EUR" in line):
        return ""

    parts = line.split()
    eur_index = -1
    for i, part in enumerate(parts):
        if part == "EUR":
            eur_index = i
            break

    if eur_index > 0 and eur_index + 2 < len(parts):
        merchant_start = eur_index + 2
        merchant_parts = parts[merchant_start:-1]  # Exclude last part (city)
        if merchant_parts:
            return " ".join(merchant_parts)
    return ""


def _extract_transfer_payee(lines: list[str]) -> str:
    """Extract payee from bank transfer descriptions."""
    if not any("BONIFICO SEPA" in line for line in lines):
        return ""

    for line in lines:
        line = line.strip()
        if ("DA:" in line or "A:" in line) and not line.startswith("BONIFICO"):
            if "DA:" in line:
                entity = line.split("DA:")[-1].strip()
            elif "A:" in line:
                entity = line.split("A:")[-1].strip()
            else:
                continue

            # Clean up the entity name
            entity = entity.split("PER:")[0].strip()

            # Handle specific patterns
            if "Directa" in entity:
                return "Directa"

            # Return first meaningful part
            entity_parts = entity.split()
            if entity_parts:
                return entity_parts[0]
    return ""


def _extract_direct_debit_payee(lines: list[str]) -> str:
    """Extract payee from direct debit descriptions."""
    if not any("ADDEBITO SEPA DD" in line for line in lines):
        return ""

    for line in lines:
        line = line.strip()
        if "/" in line and not line.startswith("ADDEBITO"):
            parts = line.split("/")
            if len(parts) >= 2:
                company = parts[-1].strip()

                # Handle specific patterns
                if "Satispay" in company:
                    return "Satispay"

                if company:
                    return company
    return ""


def _extract_fallback_payee(lines: list[str], description: str) -> str:
    """Extract payee using fallback methods."""
    # Try first meaningful line
    for line in lines:
        line = line.strip()
        if line and not line.startswith(
            ("PAGAMENTO", "BONIFICO", "ADDEBITO", "COMMISSIONI", "CANONE")
        ):
            return line[:50]

    # Final fallback based on transaction type
    if "PAGAMENTO POS" in description or "PAGAMENTO" in description:
        return "POS Payment"
    elif "BONIFICO" in description:
        return "Bank Transfer"
    elif "ADDEBITO" in description:
        return "Direct Debit"
    elif "COMMISSIONI" in description or "CANONE" in description:
        return "Bank Fees"
    else:
        return description.split()[0] if description.split() else "Unknown"


def import_csv_to_actual(
    csv_file: Path,
    base_url: str,
    password: str,
    budget_name: str,
    account_name: str,
    dry_run: bool = False,
    skip_existing: bool = True,
) -> None:
    """Import transactions from CSV file to Actual server."""

    print(f"Reading CSV file: {csv_file}")

    # Read and parse CSV
    transactions = []
    with open(csv_file, "r", encoding="utf-8") as f:
        # Skip BOM if present
        content = f.read()
        if content.startswith("\ufeff"):
            content = content[1:]

        reader = csv.reader(content.splitlines(), delimiter=";")
        header = next(reader)

        print(f"CSV Headers: {header}")

        for row_num, row in enumerate(reader, start=2):
            if not row or len(row) < 5:
                continue

            try:
                # Parse CSV fields
                reg_date = parse_date(row[0].strip())
                op_time = row[1].strip()
                value_date = parse_date(row[2].strip())
                description = row[3].strip()
                amount = parse_amount(row[4].strip())

                # Extract payee from description
                payee_name = extract_payee_from_description(description)

                transaction = {
                    "date": value_date,  # Use value date as transaction date
                    "payee": payee_name,
                    "notes": description,
                    "amount": amount,
                    "row_num": row_num,
                }

                transactions.append(transaction)

            except (ValueError, IndexError) as e:
                print(f"Warning: Skipping row {row_num} due to error: {e}")
                continue

    print(f"Parsed {len(transactions)} transactions from CSV")

    if dry_run:
        print("\nDRY RUN - Transactions that would be imported:")
        for tx in transactions:
            print(f"  {tx['date']} | {tx['payee'][:30]:30} | {tx['amount']:>10}")
        return

    # Connect to Actual server
    print(f"Connecting to Actual server at {base_url}")

    with Actual(base_url=base_url, password=password, file=budget_name) as actual:
        # Get or create account
        account = get_account(actual.session, account_name)
        if not account:
            print(f"Creating new account: {account_name}")
            account = create_account(actual.session, account_name)
        else:
            print(f"Using existing account: {account_name}")

        # Import transactions
        imported_count = 0
        skipped_count = 0

        transactions_db = account.transactions

        for tx in transactions:
            existing = None
            try:
                # Check for existing transaction if skip_existing is enabled
                if skip_existing:
                    # Check for same date and amount
                    for tx_db in transactions_db:
                        # tx_db.get_date() returns a datetime.date object
                        # tx_db.get_amount() returns a decimal.Decimal object
                        if (
                            tx_db.get_date() == tx["date"]
                            and tx_db.get_amount() == tx["amount"]
                        ):
                            existing = True
                            break

                    if existing:
                        skipped_count += 1
                        print(
                            f"Skipping existing transaction: {tx['date']} | {tx['payee'][:30]:30} | {tx['amount']:>10}"
                        )
                        continue

                # Create transaction
                create_transaction(
                    actual.session,
                    tx["date"],
                    account,
                    tx["payee"],
                    notes=tx["notes"],
                    amount=tx["amount"],
                )

                imported_count += 1
                print(
                    f"Imported: {tx['date']} | {tx['payee'][:30]:30} | {tx['amount']:>10}"
                )

            except Exception as e:
                print(f"Error importing transaction from row {tx['row_num']}: {e}")
                continue

        # Commit changes
        if imported_count > 0:
            print(f"\nCommitting {imported_count} transactions...")
            actual.commit()
            print("Import completed successfully!")
        else:
            print("No transactions to import.")

        print(f"\nSummary:")
        print(f"  Imported: {imported_count}")
        print(f"  Skipped:  {skipped_count}")
        print(f"  Total:    {len(transactions)}")


def main():
    parser = argparse.ArgumentParser(
        description="Import CSV transactions into Actual Budget server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s transactions.csv --url http://localhost:5006 --password mypass --budget "My Budget" --account "Bank Account"
  %(prog)s transactions.csv --url http://localhost:5006 --password mypass --budget "My Budget" --account "Bank Account" --dry-run
  %(prog)s transactions.csv --url http://localhost:5006 --password mypass --budget "My Budget" --account "Bank Account" --no-skip-existing

Environment variables (can be used instead of command line arguments):
  ACTUAL_URL - Actual server URL
  ACTUAL_PASSWORD - Actual server password  
  ACTUAL_BUDGET - Budget file name
  ACTUAL_ACCOUNT - Account name
        """,
    )

    parser.add_argument(
        "csv_file", type=Path, help="Path to CSV file containing transactions"
    )
    parser.add_argument("--url", help="Actual server URL (e.g., http://localhost:5006)")
    parser.add_argument("--password", help="Actual server password")
    parser.add_argument("--budget", help="Budget file name")
    parser.add_argument("--account", help="Account name to import transactions into")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview transactions without importing"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Do not skip potentially duplicate transactions",
    )

    args = parser.parse_args()

    # Get values from environment variables if not provided via command line
    url = args.url or os.getenv("ACTUAL_URL")
    password = args.password or os.getenv("ACTUAL_PASSWORD")
    budget = args.budget or os.getenv("ACTUAL_BUDGET")
    account = args.account or os.getenv("ACTUAL_ACCOUNT")

    # Validate required parameters
    if not url:
        print(
            "Error: URL is required (use --url or set ACTUAL_URL environment variable)"
        )
        sys.exit(1)
    if not password:
        print(
            "Error: Password is required (use --password or set ACTUAL_PASSWORD environment variable)"
        )
        sys.exit(1)
    if not budget:
        print(
            "Error: Budget name is required (use --budget or set ACTUAL_BUDGET environment variable)"
        )
        sys.exit(1)
    if not account:
        print(
            "Error: Account name is required (use --account or set ACTUAL_ACCOUNT environment variable)"
        )
        sys.exit(1)

    if not args.csv_file.exists():
        print(f"Error: CSV file not found: {args.csv_file}")
        sys.exit(1)

    try:
        import_csv_to_actual(
            csv_file=args.csv_file,
            base_url=url,
            password=password,
            budget_name=budget,
            account_name=account,
            dry_run=args.dry_run,
            skip_existing=not args.no_skip_existing,
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
