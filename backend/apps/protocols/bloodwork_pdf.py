"""Parse a lab-report PDF into reviewable bloodwork rows.

Best-effort, layout-tolerant extraction for born-digital lab PDFs (the user's lab —
Dr. Stein & Collegae, NL — is plain text; no OCR). Deliberately split so the text→rows
core (`parse_report`, `match_marker`, `clean_unit`) is unit-testable on plain strings
without a PDF or the ORM. Nothing here is persisted: the caller returns the rows for the
user to review and confirm before saving. Not medical advice — purely transcription.

A result line looks like:  ``<name> [METHOD] [↑/↓] <value> <unit> [reference range]``
e.g.  ``testosteron ECLIA ↑ 79.90 nmol/l 8.64 - 29.00``. Ranges come as ``a - b``,
``< b``, ``> a``, or descriptive/multi-line (range left empty, value kept).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

# Method codes that sit between the marker name and the value (stripped from the name).
_METHODS = {"hplc", "ise", "phot", "turb", "eclia", "neph", "elisa", "cmia", "tosoh", "ce"}
_FLAG_UP = "↑"
_FLAG_DOWN = "↓"

# Units seen in EU/SI lab reports (normalised: lowercased, µ/μ unified). Used to confirm
# that a numeric token is really a result value (a unit must follow it).
_KNOWN_UNITS = {
    "/nl", "/pl", "/ul", "mmol/l", "µmol/l", "nmol/l", "pmol/l", "mmol/mol",
    "fl", "fmol", "pg", "g/l", "mg/l", "µg/l", "ng/ml", "pg/ml", "ng/dl", "µg/dl",
    "u/l", "mu/l", "iu/l", "%", "ratio", "l/l", "mg/dl",
}

_NUM = r"-?\d+(?:[.,]\d+)?"
_VALUE_RE = re.compile(rf"^{_NUM}$")
_UNIT_RE = re.compile(r"^/?[a-zµ%][a-zµ0-9/^]*$")
_RANGE_TWO = re.compile(rf"^({_NUM})\s*[-–]\s*({_NUM})$")
_RANGE_UP = re.compile(rf"^[<≤]\s*({_NUM})$")
_RANGE_LOW = re.compile(rf"^[>≥]\s*({_NUM})$")
_DATE_RE = re.compile(r"(?:afname|monster\s*afname)\s*:?\s*(\d{2})\.(\d{2})\.(\d{2,4})", re.I)


# --- PDF bytes → text (the only part that needs pdfplumber) -------------------


def extract_text(pdf_bytes: bytes) -> str:
    """Concatenated text of every page (pdfplumber is imported lazily)."""
    import io

    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


# --- text → structured rows (pure) -------------------------------------------


def _dot(tok: str) -> str:
    """Normalise a numeric token to a dot decimal string."""
    return tok.replace(",", ".")


def clean_unit(raw: str) -> str:
    """Tidy a unit token while preserving the lab's own notation (the document unit)."""
    return re.sub(r"\s+", "", raw).replace("μ", "µ")


def _is_value(tok: str) -> bool:
    return bool(_VALUE_RE.match(tok))


def _is_unit(tok: str) -> bool:
    n = clean_unit(tok).lower()
    if n in _KNOWN_UNITS:
        return True
    # Resilience for unseen units — only accept compound (slash) units, never bare
    # words (a loose pattern would swallow names/labels like "Uw").
    return "/" in n and bool(_UNIT_RE.match(n))


def _parse_range(s: str):
    """(low, high) dot-decimal strings from a reference-range fragment, else (None, None)."""
    s = s.strip()
    m = _RANGE_TWO.match(s)
    if m:
        return _dot(m.group(1)), _dot(m.group(2))
    m = _RANGE_UP.match(s)
    if m:
        return None, _dot(m.group(1))
    m = _RANGE_LOW.match(s)
    if m:
        return _dot(m.group(1)), None
    return None, None


def _parse_line(line: str):
    # Ensure ↑/↓ are standalone tokens even if glued to the value by the extractor.
    tokens = re.sub(r"([↑↓])", r" \1 ", line).split()
    if len(tokens) < 2:
        return None
    for i in range(1, len(tokens)):  # i>=1 → there is always a name before the value
        if not _is_value(tokens[i]):
            continue
        # A measurement value is never preceded by a comparator — that's a range/target
        # line (e.g. apoB "streefwaarden: < 1.0 g/l"), not a result.
        if tokens[i - 1] in ("<", ">", "≤", "≥"):
            continue
        if i + 1 >= len(tokens) or not _is_unit(tokens[i + 1]):
            continue
        flag = None
        name_parts = []
        for t in tokens[:i]:
            if t == _FLAG_UP:
                flag = "high"
            elif t == _FLAG_DOWN:
                flag = "low"
            elif t.lower().strip("()") in _METHODS:
                continue
            else:
                name_parts.append(t)
        name = " ".join(name_parts).strip()
        if not name or not re.search(r"[A-Za-z]", name):
            return None
        low, high = _parse_range(" ".join(tokens[i + 2:]))
        return {
            "raw_name": name,
            "value": _dot(tokens[i]),
            "unit": clean_unit(tokens[i + 1]),
            "ref_low": low,
            "ref_high": high,
            "lab_flag": flag,
            "raw_line": line.strip(),
        }
    return None


def _parse_date(text: str):
    m = _DATE_RE.search(text)
    if not m:
        return None
    d, mo, y = (int(g) for g in m.groups())
    y = 2000 + y if y < 100 else y
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_report(text: str) -> dict:
    """{measured_on, rows:[{raw_name, value, unit, ref_low, ref_high, lab_flag, raw_line}]}."""
    rows = []
    seen = set()
    for line in text.splitlines():
        row = _parse_line(line)
        if row is None:
            continue
        key = (row["raw_name"].lower(), row["value"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return {"measured_on": _parse_date(text), "rows": rows}


# --- marker matching (pure; takes any objects with .name/.aliases) ------------


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("μ", "µ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _marker_forms(marker):
    """Normalised name + alias forms for a marker. No paren-stripping here — a marker's
    own parenthetical (e.g. "HbA1c (IFCC)") is meaningful and kept distinct from "HbA1c"."""
    forms = {_normalize(n) for n in [marker.name, *(getattr(marker, "aliases", None) or [])]}
    forms.discard("")
    return forms


def match_marker(raw_name: str, markers):
    """Match a lab name to a marker → (marker | None, confidence 0..1).

    Pass A — exact (order-preserving) normalised match on the full name/aliases, so
    "HbA1c (IFCC)" maps to its own marker, not "HbA1c". Pass B — exact match after
    stripping a parenthetical from the *lab* name (e.g. "estradiol (17-…)" → "estradiol").
    Pass C — multi-token subset (alias tokens ⊆ name tokens) for truncated multi-line
    names; skipped for ratio-like names with "/" so "cholesterol/HDL" isn't mis-mapped.
    """
    target = _normalize(raw_name)
    if not target:
        return None, 0.0
    for m in markers:
        if target in _marker_forms(m):
            return m, 1.0
    target_np = _normalize(re.sub(r"\(.*?\)", "", raw_name))
    if target_np and target_np != target:
        for m in markers:
            if target_np in _marker_forms(m):
                return m, 0.95
    if "/" in raw_name:
        return None, 0.0
    tset = set(target.split())
    best = None
    for m in markers:
        for f in _marker_forms(m):
            toks = set(f.split())
            if len(toks) >= 2 and toks <= tset:
                score = len(toks) / max(1, len(tset))
                if best is None or score > best[1]:
                    best = (m, score)
    return best if best else (None, 0.0)
