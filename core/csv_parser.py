from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from pathlib import Path
from typing import IO, Any, cast


class CSVParser:
    """
    Pure-Python CSV parser that handles Standard, AMEX, TD Bank, and generic formats.
    Uses stdlib csv module; pandas is used only as a last-resort date fallback.
    """

    DATE_FORMATS = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y/%m/%d",
        "%d %b %Y",
    ]

    def parse(self, file_obj: IO[bytes], filename: str) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Parse a CSV file object and return (rows, errors).

        rows  — list of dicts with keys: date, description, amount, account, source_file
        errors — list of human-readable error strings (row-level or fatal)
        """
        try:
            raw_rows = self._read_csv(file_obj)
        except Exception as exc:
            return [], [f"Could not read file: {exc}"]

        if not raw_rows:
            return [], ["File is empty or contains no data rows."]

        headers = list(raw_rows[0].keys())
        fmt = self._detect_format(headers)

        try:
            normalized = self._normalize_columns(raw_rows, fmt, filename)
        except ValueError as exc:
            return [], [str(exc)]

        rows, errors = [], []
        for i, row in enumerate(normalized, start=2):  # row 1 is the header
            row_errors = []

            date_val = self._parse_date(row.get("date", ""))
            if date_val is None:
                row_errors.append(f"Row {i}: invalid or missing date «{row.get('date', '')}»")

            description = (row.get("description") or "").strip()
            if not description:
                row_errors.append(f"Row {i}: missing description")

            try:
                amount = self._parse_amount(row.get("amount", ""))
            except (ValueError, TypeError):
                row_errors.append(f"Row {i}: invalid amount «{row.get('amount', '')}»")
                amount = None

            if row_errors:
                errors.extend(row_errors)
                continue

            rows.append(
                {
                    "date": date_val,
                    "description": description,
                    "amount": amount,
                    "account": (row.get("account") or "").strip(),
                    "source_file": filename,
                }
            )

        return rows, errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_csv(self, file_obj: IO[bytes]) -> list[dict[str, str]]:
        raw: bytes = file_obj.read()
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text: str = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("latin-1", errors="replace")

        reader = csv.DictReader(io.StringIO(text))
        return list(reader)

    def _detect_format(self, headers: list[str]) -> str:
        lower = {h.lower().strip() for h in headers if h is not None}

        if "card member" in lower or "extended details" in lower:
            return "amex"
        if "account number" in lower and "posted date" in lower:
            return "td_bank"
        if "date" in lower and "description" in lower and "amount" in lower:
            return "standard"
        return "generic"

    def _normalize_columns(self, rows: list[dict[str, str]], format_type: str, filename: str) -> list[dict[str, Any]]:
        dispatch = {
            "standard": self._standard_normalize,
            "amex": lambda r: self._amex_normalize(r, filename),
            "td_bank": self._td_bank_normalize,
            "generic": self._generic_normalize,
        }
        return dispatch[format_type](rows)

    @staticmethod
    def _row_lower(row: dict[str, str]) -> dict[str, str]:
        """Return a dict with all keys lower-stripped, skipping None keys."""
        return {k.lower().strip(): v for k, v in row.items() if k is not None}

    def _standard_normalize(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            lr = self._row_lower(row)
            result.append(
                {
                    "date": lr.get("date", ""),
                    "description": lr.get("description", ""),
                    "amount": lr.get("amount", ""),
                    "account": lr.get("account", ""),
                }
            )
        return result

    def _amex_normalize(self, rows: list[dict[str, str]], filename: str) -> list[dict[str, Any]]:
        # AMEX CSVs have no account column — derive from filename stem
        account = Path(filename).stem
        result = []
        for row in rows:
            lr = self._row_lower(row)
            result.append(
                {
                    "date": lr.get("date", ""),
                    "description": lr.get("description", ""),
                    "amount": lr.get("amount", ""),
                    "account": account,
                }
            )
        return result

    def _td_bank_normalize(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            lr = self._row_lower(row)
            result.append(
                {
                    "date": lr.get("posted date", lr.get("date", "")),
                    "description": lr.get("payee", lr.get("description", "")),
                    "amount": lr.get("amount", ""),
                    "account": lr.get("account number", ""),
                }
            )
        return result

    def _generic_normalize(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        if not rows:
            return []

        headers = [h for h in rows[0] if h is not None]
        lh = [h.lower().strip() for h in headers]

        date_col = self._find_col(
            lh, headers, ["date", "transaction date", "posted date", "trans date", "trans. date", "value date"]
        )
        desc_col = self._find_col(
            lh,
            headers,
            ["description", "payee", "merchant", "memo", "details", "narrative", "particulars", "transaction details"],
        )
        account_col = self._find_col(lh, headers, ["account", "account number", "account name", "account no"])
        amount_col = self._find_col(lh, headers, ["amount", "transaction amount", "value", "net amount"])
        debit_col = self._find_col(lh, headers, ["debit", "debit amount", "withdrawals", "withdrawal", "dr"])
        credit_col = self._find_col(lh, headers, ["credit", "credit amount", "deposits", "deposit", "cr"])

        if date_col is None and desc_col is None and amount_col is None and debit_col is None:
            raise ValueError(
                "Could not identify required columns (date, description, amount). Please use a supported CSV format."
            )

        result = []
        for row in rows:
            if debit_col and credit_col and not amount_col:
                amount = self._combine_debit_credit(row, debit_col, credit_col)
            else:
                amount = row.get(amount_col, "") if amount_col else ""

            result.append(
                {
                    "date": row.get(date_col, "") if date_col else "",
                    "description": row.get(desc_col, "") if desc_col else "",
                    "amount": amount,
                    "account": row.get(account_col, "") if account_col else "",
                }
            )
        return result

    def _find_col(self, lower_headers: list[str], original_headers: list[str], candidates: list[str]) -> str | None:
        """Exact match first, then substring fallback."""
        for candidate in candidates:
            for i, h in enumerate(lower_headers):
                if h == candidate:
                    return original_headers[i]
        for candidate in candidates:
            for i, h in enumerate(lower_headers):
                if candidate in h:
                    return original_headers[i]
        return None

    def _parse_date(self, s: str) -> date | None:
        if not s or not str(s).strip():
            return None
        s = str(s).strip()
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        # Last-resort: pandas.to_datetime
        try:
            import pandas as pd  # type: ignore[import-untyped]  # noqa: PLC0415

            return cast(date, pd.to_datetime(s, dayfirst=False).date())
        except Exception:  # noqa: S110
            pass
        return None

    def _parse_amount(self, s: str | None) -> float:
        if s is None:
            raise ValueError("missing amount")
        s = str(s).strip()
        if not s:
            raise ValueError("empty amount")
        negative = s.startswith("(") and s.endswith(")")
        s = re.sub(r"[$€£,\s]", "", s)
        s = s.strip("()").strip()
        if not s:
            raise ValueError("empty amount after stripping")
        val = float(s)
        if negative:
            val = -val
        return abs(val)

    def _combine_debit_credit(self, row: dict[str, str], debit_col: str, credit_col: str) -> str:
        """Return net amount string (credit − debit) for rows with split columns."""

        def _safe_parse(v: object) -> float:
            try:
                return self._parse_amount(str(v or "").strip()) if str(v or "").strip() else 0.0
            except (ValueError, TypeError):
                return 0.0

        debit = _safe_parse(row.get(debit_col, ""))
        credit = _safe_parse(row.get(credit_col, ""))
        return str(credit - debit)
