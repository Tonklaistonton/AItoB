"""Export only the fixed, already-cleaned lab CSV after backend Finance auth."""
import csv
import hashlib
import io
from decimal import Decimal, InvalidOperation

from auth import authenticate
from workflow import OUTPUT

MAX_BYTES = 2_000_000

def export_for_key(authorization):
    identity = authenticate(authorization)
    if identity is None:
        return 401, {'error': 'invalid_key_or_permissions'}
    if identity.get('team') != 'Finance' or identity.get('role') != 'finance_reader':
        return 403, {'error': 'finance_export_access_denied'}
    try:
        with OUTPUT.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return 413, {'error': 'finance_export_too_large'}
        content = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        if reader.fieldnames != ['expense_id', 'vendor', 'amount']:
            raise ValueError('columns')
        count, seen, total = 0, set(), Decimal('0.00')
        for row in reader:
            expense_id, vendor = row.get('expense_id'), row.get('vendor')
            if None in row or not expense_id or not vendor or expense_id in seen:
                raise ValueError('invalid_record')
            # Export fails closed on spreadsheet-formula payloads, without changing data.
            for value in (expense_id, vendor):
                if value.lstrip().startswith(('=', '+', '-', '@')) or any(ord(c) < 32 for c in value):
                    raise ValueError('unsafe_spreadsheet_text')
            amount = Decimal(row['amount'])
            if not amount.is_finite() or amount <= 0 or amount > Decimal('1000000000') or amount != amount.quantize(Decimal('0.01')):
                raise ValueError('invalid_amount')
            seen.add(expense_id); total += amount; count += 1
        return 200, {'filename': 'expenses_cleaned.csv', 'content': content,
                     'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                     'rows': count, 'total_amount': format(total, '.2f'), 'currency': 'THB'}
    except FileNotFoundError:
        return 404, {'error': 'cleaned_csv_not_ready'}
    except (OSError, UnicodeError, ValueError, TypeError, csv.Error, InvalidOperation):
        return 422, {'error': 'cleaned_csv_export_validation_failed'}
