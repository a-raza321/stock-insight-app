import itertools
import re
import warnings
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------
# Page config
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Financial Reconciliation Tool",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "pdf"}
FIXED_FIELDS = ["Date", "Amount", "Reference", "Description"]

# --------------------------------------------------------------------------
# Custom CSS - gives the app a clean, "designed" look
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #f7f9fc 0%, #eef1f8 100%);
    }
    .app-header {
        text-align: center;
        padding: 1.6rem 1rem 1.2rem 1rem;
        margin-bottom: 1.2rem;
        border-radius: 18px;
        background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 60%, #a855f7 100%);
        color: white;
        box-shadow: 0 10px 30px rgba(99, 60, 220, 0.25);
    }
    .app-header h1 {
        margin: 0;
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .app-header p {
        margin: 0.35rem 0 0 0;
        font-size: 1.0rem;
        opacity: 0.92;
    }
    /* Force readable dark text everywhere, regardless of the visitor's
       system light/dark preference, so nothing renders white-on-white. */
    .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stCaptionContainer"],
    div[data-testid="stCaptionContainer"] p,
    div[data-testid="stWidgetLabel"] p,
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] p,
    div[data-testid="stFileUploaderDropzoneInstructions"] span,
    div[data-testid="stFileUploaderDropzoneInstructions"] small,
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricValue"] {
        color: #1f2937 !important;
    }
    div[data-testid="stCaptionContainer"] p, .stCaption {
        color: #6b7280 !important;
    }
        color: #000000;
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    div[data-testid="stFileUploader"] {
        margin-top: 0rem;
    }
    .file-ok {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #065f46;
        padding: 0.6rem 0.9rem;
        border-radius: 10px;
        font-size: 0.9rem;
    }
    .file-err {
        background: #fef2f2;
        border: 1px solid #fecaca;
        color: #991b1b;
        padding: 0.55rem 0.8rem;
        border-radius: 10px;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }
    .file-ext-badge {
        display: inline-block;
        background: #eef2ff;
        color: #4338ca;
        font-weight: 700;
        font-size: 0.72rem;
        letter-spacing: 0.5px;
        padding: 0.15rem 0.5rem;
        border-radius: 6px;
        margin-left: 0.5rem;
        text-transform: uppercase;
    }
    .section-title {
        font-size: 1.3rem;
        font-weight: 800;
        color: #33265a;
        margin: 1.6rem 0 0.6rem 0;
    }
    div[data-testid="stFileUploaderDropzone"] {
        border-radius: 12px !important;
        border: 2px dashed #b9a8f7 !important;
        background: #faf9ff !important;
        padding: 0.4rem 0.7rem !important;
        min-height: 0 !important;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] {
        padding: 0.2rem 0 !important;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] svg {
        height: 1.1rem !important;
        width: 1.1rem !important;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] span {
        font-size: 0.78rem !important;
        line-height: 1.1rem !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] small {
        font-size: 0.68rem !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stFileUploaderDropzone"] button {
        padding: 0.25rem 0.7rem !important;
        font-size: 0.78rem !important;
        min-height: 0 !important;
    }
    div[data-testid="stFileUploader"] section {
        min-height: 0 !important;
    }
    /* Primary (Process) narrow button */
    div[data-testid="stButton"] button[kind="primary"] {
        border-radius: 12px;
        font-weight: 700;
        font-size: 1.0rem;
        background: #004d26 !important;
        color: white;
        border: none;
        box-shadow: 0 8px 20px rgba(0, 51, 30, 0.35);
        transition: transform 0.15s ease;
        padding: 0.6rem 0;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background: #00512F;
        transform: translateY(-2px);
    }
    div[data-testid="stButton"] button[kind="primary"]:disabled {
        background: #e0e0e0 !important;
        color: #1f2937 !important;
        color: #8a8aa3;
    }
    /* Reset button styling */
    div[data-testid="stButton"] button[kind="secondary"] {
        border-radius: 10px;
        font-weight: 700;
        border: 1.5px solid #ef4444;
        color: #ef4444;
        background: white;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background: #fef2f2;
    }
    /* Small delete (trash) buttons */
    button[title="delete_file"] {
        border-radius: 8px !important;
    }
    .mapping-row {
        background: white;
        border-radius: 12px;
        padding: 0.6rem 0.9rem;
        margin-bottom: 0.55rem;
        border: 1px solid #eceefb;
        box-shadow: 0 3px 10px rgba(20,20,43,0.04);
    }
    .mapping-header {
        font-weight: 800;
        color: #4f46e5;
        font-size: 0.95rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #ece6ff;
        margin-bottom: 0.6rem;
    }
    .badge-full {
        display:inline-block; background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0;
        padding:0.15rem 0.6rem; border-radius:999px; font-weight:700; font-size:0.78rem;
    }
    .badge-partial {
        display:inline-block; background:#fffbeb; color:#92400e; border:1px solid #fde68a;
        padding:0.15rem 0.6rem; border-radius:999px; font-weight:700; font-size:0.78rem;
    }
    .badge-split {
        display:inline-block; background:#eff6ff; color:#1e40af; border:1px solid #bfdbfe;
        padding:0.15rem 0.6rem; border-radius:999px; font-weight:700; font-size:0.78rem;
    }
    .badge-unmatched {
        display:inline-block; background:#fef2f2; color:#991b1b; border:1px solid #fecaca;
        padding:0.15rem 0.6rem; border-radius:999px; font-weight:700; font-size:0.78rem;
    }
    .recon-summary-card {
        background:white; border:1px solid #eceefb; border-radius:14px; padding:0.9rem 1.1rem;
        box-shadow: 0 4px 14px rgba(20,20,43,0.05); text-align:center;
    }
    .recon-summary-card .num { font-size:1.6rem; font-weight:800; color:#33265a; }
    .recon-summary-card .lbl { font-size:0.8rem; color:#6b7280; font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Session state initialisation
# --------------------------------------------------------------------------
DEFAULT_STATE = {
    "processed": False,
    "df1": None,
    "df2": None,
    "file1_bytes": None,
    "file1_name": None,
    "file2_bytes": None,
    "file2_name": None,
    "uploader1_key": 0,
    "uploader2_key": 0,
    "mapping_result": None,
    "reconciled": False,
    "recon_results": None,
}
for k, v in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = v


def clear_mapping_widget_state():
    """Remove any previously-stored column-mapping selectbox values so
    fresh auto-detected defaults are used whenever a new pair of files
    is processed (or the app is reset)."""
    for f in FIXED_FIELDS:
        st.session_state.pop(f"map1_{f}", None)
        st.session_state.pop(f"map2_{f}", None)


def reset_app():
    """Wipe every piece of app state back to defaults and force fresh
    (empty) uploader widgets by bumping their keys."""
    st.session_state.processed = False
    st.session_state.df1 = None
    st.session_state.df2 = None
    st.session_state.file1_bytes = None
    st.session_state.file1_name = None
    st.session_state.file2_bytes = None
    st.session_state.file2_name = None
    st.session_state.mapping_result = None
    st.session_state.reconciled = False
    st.session_state.recon_results = None
    st.session_state.uploader1_key += 1
    st.session_state.uploader2_key += 1
    clear_mapping_widget_state()


def delete_file(slot: int):
    """Remove a single uploaded file so the user can pick a new one."""
    if slot == 1:
        st.session_state.file1_bytes = None
        st.session_state.file1_name = None
        st.session_state.uploader1_key += 1
    else:
        st.session_state.file2_bytes = None
        st.session_state.file2_name = None
        st.session_state.uploader2_key += 1
    # Any existing processed result is now stale
    st.session_state.processed = False
    st.session_state.df1 = None
    st.session_state.df2 = None
    st.session_state.mapping_result = None
    st.session_state.reconciled = False
    st.session_state.recon_results = None
    clear_mapping_widget_state()


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <h1>🗂️ Financial Reconciliation Tool</h1>
        <p>Match transactions between two files, automatically</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _looks_numeric(value: str) -> bool:
    v = value.strip().replace(",", "")
    if not v:
        return False
    v2 = v.replace(".", "", 1).replace("-", "", 1)
    return v2.isdigit()


def detect_header_row(raw: pd.DataFrame, max_scan: int = 25) -> int:
    """
    Scan the first `max_scan` rows of a headerless dataframe and guess which
    one is the real header row. Works even if the header isn't row 0 (e.g.
    files that start with a title, blank rows, or metadata above the table).
    """
    best_idx = 0
    best_score = -1.0
    n_check = min(max_scan, len(raw))

    for i in range(n_check):
        row = raw.iloc[i]
        non_null = row.notna().sum()
        if non_null == 0:
            continue

        ratio_filled = non_null / len(row)

        str_count = 0
        for val in row:
            if pd.isna(val):
                continue
            s = str(val)
            if not _looks_numeric(s):
                str_count += 1
        ratio_text = str_count / non_null

        values = row.dropna().astype(str).str.strip()
        ratio_unique = (len(values.unique()) / len(values)) if len(values) else 0

        transition_bonus = 0.0
        if i + 1 < len(raw):
            next_row = raw.iloc[i + 1]
            next_non_null = next_row.notna().sum()
            if next_non_null:
                next_numeric = sum(
                    1 for v in next_row if pd.notna(v) and _looks_numeric(str(v))
                )
                if next_numeric / next_non_null > ratio_text:
                    transition_bonus = 0.15

        score = (ratio_filled * 0.35) + (ratio_text * 0.35) + (ratio_unique * 0.15) + transition_bonus

        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def clean_header_labels(values):
    seen = {}
    labels = []
    for j, v in enumerate(values):
        label = str(v).strip() if pd.notna(v) else ""
        if not label or label.lower() == "nan":
            label = f"Column_{j + 1}"
        if label in seen:
            seen[label] += 1
            label = f"{label}_{seen[label]}"
        else:
            seen[label] = 0
        labels.append(label)
    return labels


def extract_pdf_rows(file_bytes):
    try:
        import pdfplumber
    except ImportError:
        st.error(
            "The `pdfplumber` package is required to read PDF files. "
            "Install it with: pip install pdfplumber"
        )
        return None

    import io
    rows = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                rows.extend(table)
    return rows if rows else None


def load_dataframe(file_bytes, filename):
    """
    Load a file (given as raw bytes) into a clean DataFrame, automatically
    detecting the header row wherever it appears in the file.
    Returns (dataframe, error_message).
    """
    import io

    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        return None, f"Unsupported file type: .{ext}"

    try:
        if ext == "csv":
            raw = pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=str, skip_blank_lines=False)
        elif ext in ("xlsx", "xls"):
            raw = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
        elif ext == "pdf":
            table_rows = extract_pdf_rows(file_bytes)
            if not table_rows:
                return None, "No table could be detected inside this PDF."
            width = max(len(r) for r in table_rows)
            padded = [r + [None] * (width - len(r)) for r in table_rows]
            raw = pd.DataFrame(padded)
        else:
            return None, f"Unsupported file type: .{ext}"
    except Exception as e:
        return None, f"Could not read file: {e}"

    if raw is None or raw.empty:
        return None, "The file appears to be empty."

    raw = raw.dropna(how="all").reset_index(drop=True)
    if raw.empty:
        return None, "The file has no usable data."

    header_idx = detect_header_row(raw)
    header_values = raw.iloc[header_idx].tolist()
    columns = clean_header_labels(header_values)

    data = raw.iloc[header_idx + 1:].reset_index(drop=True)
    data.columns = columns
    data = data.dropna(how="all").reset_index(drop=True)

    return data, None


BLANK_OPTION = "— Select —"

# Column-name signal patterns, ranked best-to-worst, used to auto-detect
# which real column in the uploaded file corresponds to each fixed field.
# No user selection involved — this is our own rule-based detection logic,
# used here only to pre-fill sensible defaults in the mapping dropdowns
# (the user can always override them).
FIELD_SIGNALS = {
    "Date": ["transaction date", "value date", "posting date", "date"],
    "Amount": ["amount", "net amount", "total", "value", "debit", "credit", "paid"],
    "Reference": ["invoice", "reference", "ref no", "ref", "cheque", "txn id", "transaction id", "receipt"],
    "Description": ["description", "narration", "particulars", "details", "memo", "remarks"],
}


def auto_detect_column(columns, field):
    """
    Pick the best real column for a fixed field using our own rules:
    exact/near header-name matches first (in priority order), keyword
    containment second. Returns the column name, or None if nothing
    confidently matches.
    """
    lowered = {c: c.lower().strip() for c in columns}

    # Pass 1: exact match against a known signal phrase
    for signal in FIELD_SIGNALS[field]:
        for col, low in lowered.items():
            if low == signal:
                return col

    # Pass 2: signal phrase contained within the column header
    for signal in FIELD_SIGNALS[field]:
        for col, low in lowered.items():
            if signal in low:
                return col

    return None


def auto_detect_mapping(columns):
    """Runs auto_detect_column for every fixed field against one file's
    column list. Returns {field: column_name_or_None}. Used to pre-fill
    the default value of each mapping dropdown."""
    used = set()
    mapping = {}
    # Detect in priority order (Amount and Date first, since they carry the
    # most matching weight) so a column isn't double-claimed by two fields.
    for field in ["Amount", "Date", "Reference", "Description"]:
        col = auto_detect_column([c for c in columns if c not in used], field)
        mapping[field] = col
        if col:
            used.add(col)
    return mapping


# ==========================================================================
# RECONCILIATION ENGINE
# Deterministic, rule-based, weighted-scoring matcher (no AI).
# ==========================================================================
def parse_amount(val):
    """Parse a raw cell into a float amount. Handles currency symbols,
    thousands separators, and parentheses-as-negative accounting notation."""
    if pd.isna(val):
        return float("nan")
    s = str(val).strip()
    if s == "" or s.lower() == "nan":
        return float("nan")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.upper().endswith("CR") or s.upper().endswith("DR"):
        s = s[:-2].strip()
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", ".", "-."):
        return float("nan")
    try:
        v = float(s)
    except ValueError:
        return float("nan")
    return -abs(v) if neg else v


EXCEL_EPOCH = pd.Timestamp("1899-12-30")  # correctly accounts for Excel's 1900 leap-year bug


def _excel_serial_to_date(serial):
    try:
        serial = float(serial)
    except (TypeError, ValueError):
        return pd.NaT
    # Plausible Excel serial range: roughly year 1950 to 2100
    if serial < 18000 or serial > 73000:
        return pd.NaT
    try:
        return EXCEL_EPOCH + pd.to_timedelta(serial, unit="D")
    except (OverflowError, ValueError):
        return pd.NaT


def parse_single_date(val):
    """
    Parse one raw cell into a standardized pandas Timestamp, trying —
    in order:
      1. Excel serial date numbers (e.g. 45597, whether stored as a real
         number or as plain-digit text)
      2. ISO and common numeric formats (YYYY-MM-DD, DD/MM/YYYY, MM-DD-YYYY...)
      3. Day-first variants (for non-US exports)
      4. Flexible/fuzzy parsing (e.g. "5 Jan 2024", "Jan 5, 2024")
    Returns pd.NaT if nothing works.

    NOTE: kept for reference / ad-hoc single-value use. The reconciliation
    engine itself uses the vectorized `parse_date_series` below (much
    faster on full columns), so this function is no longer called from
    `build_standard_frame`.
    """
    if pd.isna(val):
        return pd.NaT

    # Real numeric types (openpyxl sometimes yields these) -> Excel serial
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return _excel_serial_to_date(val)

    s = str(val).strip()
    if s == "" or s.lower() == "nan":
        return pd.NaT

    # Plain-digit strings that look like an Excel serial (e.g. "45597")
    if re.fullmatch(r"\d{4,6}", s):
        candidate = _excel_serial_to_date(s)
        if pd.notna(candidate):
            return candidate

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)

        # Standard parse (month-first, e.g. US-style MM/DD/YYYY)
        parsed = pd.to_datetime(s, errors="coerce", dayfirst=False)
        if pd.notna(parsed):
            return parsed

        # Day-first parse (e.g. UK/AU/EU-style DD/MM/YYYY)
        parsed = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            return parsed

    # Last resort: flexible/fuzzy parsing for odd formats
    try:
        from dateutil import parser as _dtparser
        try:
            return pd.Timestamp(_dtparser.parse(s, dayfirst=False, fuzzy=True))
        except (ValueError, OverflowError):
            return pd.Timestamp(_dtparser.parse(s, dayfirst=True, fuzzy=True))
    except Exception:
        return pd.NaT


def parse_date_series(series):
    """
    Vectorized version of parse_single_date — parses an entire column at
    once instead of row-by-row. Same fallback order (Excel serial -> ISO/
    month-first -> day-first -> fuzzy dateutil), but only the rows that
    fail one stage get passed to the next, so it's fast even on large
    PDFs/CSVs instead of doing up to 3 slow parses per row, and it won't
    spam the console with per-row UserWarnings.
    """
    s = series.astype(str).str.strip()
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    empty_mask = series.isna() | (s == "") | (s.str.lower() == "nan")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)

        # Stage 1: plain-digit strings that look like an Excel serial number
        serial_mask = (~empty_mask) & s.str.fullmatch(r"\d{4,6}")
        if serial_mask.any():
            result.loc[serial_mask] = s[serial_mask].apply(_excel_serial_to_date)

        # Stage 2: month-first pass (vectorized)
        remaining = result.isna() & ~empty_mask
        if remaining.any():
            result.loc[remaining] = pd.to_datetime(s[remaining], errors="coerce", dayfirst=False)

        # Stage 3: day-first pass (vectorized)
        remaining = result.isna() & ~empty_mask
        if remaining.any():
            result.loc[remaining] = pd.to_datetime(s[remaining], errors="coerce", dayfirst=True)

        # Stage 4: fuzzy fallback — only for the few stragglers left
        remaining = result.isna() & ~empty_mask
        if remaining.any():
            from dateutil import parser as _dtparser

            def _fuzzy(v):
                try:
                    return pd.Timestamp(_dtparser.parse(v, dayfirst=False, fuzzy=True))
                except (ValueError, OverflowError):
                    try:
                        return pd.Timestamp(_dtparser.parse(v, dayfirst=True, fuzzy=True))
                    except Exception:
                        return pd.NaT
                except Exception:
                    return pd.NaT

            result.loc[remaining] = s[remaining].apply(_fuzzy)

    return result


def format_date_display(val):
    """Standardized display format for parsed dates: YYYY-MM-DD."""
    if pd.isna(val):
        return ""
    return val.strftime("%Y-%m-%d")


def build_standard_frame(df, mapping):
    """Turn the user's chosen mapping into a small standardized frame with
    only the fields that were actually mapped (blank / '— Select —' fields
    are dropped from the matching criteria entirely)."""
    std = pd.DataFrame(index=df.index)
    flags = {}
    for field in FIXED_FIELDS:
        col = mapping.get(field)
        if col and col != BLANK_OPTION:
            if field == "Amount":
                std["Amount"] = df[col].apply(parse_amount)
            elif field == "Date":
                std["Date"] = parse_date_series(df[col])
            else:
                std[field] = df[col].astype(str).str.strip()
            flags[field] = True
        else:
            flags[field] = False
    std = std.reset_index(drop=True)
    return std, flags


def score_pair(a, b, flags):
    """
    Weighted scoring engine (max 100), matching every field the user mapped:
        Exact amount match          +40   (compared by absolute value — sign is ignored,
                                            so -5009.24 and 5009.24 are treated as equal)
        Amount within tolerance     +25   (rounding / GST-style differences)
        Same-day date               +20
        Date within 2-3 days        +10
        Exact reference match       +20
        Description similarity      up to +20 (proportional to similarity)
    Fields the user didn't map contribute nothing (rather than being
    treated as a mismatch), since balances/other criteria weren't provided.

    IMPORTANT: when both Amount and Date are available, a pair is only ever
    considered a valid match if BOTH agree (within tolerance) — a same
    amount on a wildly different date is rejected outright rather than
    being accepted on amount alone.
    """
    parts = []
    amount_pts = 0
    date_pts = 0
    ref_pts = 0
    desc_pts = 0

    amount_available = flags.get("Amount") and pd.notna(a.get("Amount")) and pd.notna(b.get("Amount"))
    date_available = flags.get("Date") and pd.notna(a.get("Date")) and pd.notna(b.get("Date"))

    if amount_available:
        # Sign-agnostic comparison: a debit in one file and a credit in the
        # other (e.g. -5009.24 vs 5009.24) are treated as the same amount.
        abs_a, abs_b = abs(a["Amount"]), abs(b["Amount"])
        diff = abs(abs_a - abs_b)
        tol = max(0.05, abs_a * 0.02)
        if diff <= 0.005:
            amount_pts = 40
            parts.append("Amount exact match, sign ignored (+40)")
        elif diff <= tol:
            amount_pts = 25
            parts.append(f"Amount within tolerance (sign ignored), diff {diff:.2f} — possible GST/rounding (+25)")
        else:
            parts.append(f"Amount mismatch, diff {diff:.2f} (+0)")

    if date_available:
        d = abs((a["Date"] - b["Date"]).days)
        if d == 0:
            date_pts = 20
            parts.append("Same-day date (+20)")
        elif d <= 3:
            date_pts = 10
            parts.append(f"Date {d} day(s) apart (+10)")
        else:
            parts.append(f"Date {d} day(s) apart (+0)")

    if flags.get("Reference"):
        ra = str(a.get("Reference", "")).strip().lower()
        rb = str(b.get("Reference", "")).strip().lower()
        if ra and rb and ra not in ("nan", "") and ra == rb:
            ref_pts = 20
            parts.append("Reference exact match (+20)")
        else:
            parts.append("Reference no match (+0)")

    if flags.get("Description"):
        da = str(a.get("Description", "")).strip().lower()
        db = str(b.get("Description", "")).strip().lower()
        if da and db and da not in ("nan", "") and db not in ("nan", ""):
            ratio = SequenceMatcher(None, da, db).ratio()
            desc_pts = round(ratio * 20)
            parts.append(f"Description {ratio * 100:.0f}% similar (+{desc_pts})")

    # Gate: if both Amount and Date were mapped on both sides, require BOTH
    # to actually agree — an amount match with no date agreement is rejected
    # rather than accepted purely on amount.
    if amount_available and date_available:
        if amount_pts == 0 or date_pts == 0:
            return 0, parts + ["Rejected: amount and date must both agree (+0)"]

    score = amount_pts + date_pts + ref_pts + desc_pts
    return score, parts


def generate_candidates(df1, df2, flags):
    """Build candidate (i, j) pairs using blocking on amount / reference so
    we don't need a full O(n*m) description-similarity scan on large files."""
    n1, n2 = len(df1), len(df2)
    candidates = []

    amount_bucket = {}
    if flags.get("Amount"):
        for j in range(n2):
            amt = df2.iloc[j].get("Amount")
            if pd.notna(amt):
                amount_bucket.setdefault(round(abs(amt), 2), []).append(j)

    ref_index = {}
    if flags.get("Reference"):
        for j in range(n2):
            r = str(df2.iloc[j].get("Reference", "")).strip().lower()
            if r and r != "nan":
                ref_index.setdefault(r, []).append(j)

    no_blocking_key = not flags.get("Amount") and not flags.get("Reference")

    for i in range(n1):
        a = df1.iloc[i]
        js = set()
        if flags.get("Amount") and pd.notna(a.get("Amount")):
            base = round(abs(a["Amount"]), 2)
            tol = max(0.05, base * 0.02)
            steps = int(tol / 0.01) + 1
            for d in range(-steps, steps + 1):
                key = round(base + d * 0.01, 2)
                if key in amount_bucket:
                    js.update(amount_bucket[key])
        if flags.get("Reference"):
            r = str(a.get("Reference", "")).strip().lower()
            if r and r in ref_index:
                js.update(ref_index[r])
        if no_blocking_key:
            js.update(range(min(n2, 2000)))  # bounded fallback scan

        for j in js:
            b = df2.iloc[j]
            score, parts = score_pair(a, b, flags)
            if score > 0:
                candidates.append((score, i, j, parts))

    return candidates


def greedy_assign(candidates, min_score=30):
    """Assign the highest-scoring pairs first, one-to-one, never reusing a
    row on either side (a real optimizer would use Hungarian algorithm; this
    greedy pass is a close, fast approximation for typical statement sizes)."""
    ordered = sorted(candidates, key=lambda x: -x[0])
    used_i, used_j = set(), set()
    full_matches, partial_matches = [], []

    for score, i, j, parts in ordered:
        if i in used_i or j in used_j:
            continue
        if score < min_score:
            continue
        used_i.add(i)
        used_j.add(j)
        record = {"i": i, "j": j, "score": score, "parts": parts}
        if score >= 80:
            full_matches.append(record)
        else:
            partial_matches.append(record)

    return full_matches, partial_matches, used_i, used_j


def find_split_and_combined(df1, df2, used_i, used_j, flags, max_combo=3, date_window=10, pool_limit=25):
    """
    Split payment: one file-1 transaction == sum of several file-2 transactions.
    Combined payment: several file-1 transactions == one file-2 transaction.
    Skipped gracefully if Amount wasn't mapped, or if the leftover pool is
    too large to brute-force safely.
    """
    splits, combined = [], []
    if not flags.get("Amount"):
        return splits, combined, used_i, used_j

    leftover1 = [i for i in range(len(df1)) if i not in used_i]
    leftover2 = [j for j in range(len(df2)) if j not in used_j]

    if len(leftover1) > 400 or len(leftover2) > 400:
        return splits, combined, used_i, used_j  # too large to brute-force safely

    def amount_ok(target, total):
        # Sign-agnostic: compare magnitudes only.
        return abs(abs(total) - abs(target)) <= max(0.05, abs(target) * 0.02)

    def within_window(a, b):
        if flags.get("Date") and pd.notna(a.get("Date")) and pd.notna(b.get("Date")):
            return abs((a["Date"] - b["Date"]).days) <= date_window
        return True

    used_j_local = set()
    for i in leftover1:
        a = df1.iloc[i]
        if pd.isna(a.get("Amount")):
            continue
        pool = [j for j in leftover2 if j not in used_j_local and pd.notna(df2.iloc[j].get("Amount")) and within_window(a, df2.iloc[j])]
        pool = pool[:pool_limit]
        found = None
        for r in range(2, max_combo + 1):
            for combo in itertools.combinations(pool, r):
                total = sum(df2.iloc[j]["Amount"] for j in combo)
                if amount_ok(a["Amount"], total):
                    found = combo
                    break
            if found:
                break
        if found:
            splits.append({"i": i, "js": list(found), "target": a["Amount"], "sum": sum(df2.iloc[j]["Amount"] for j in found)})
            used_j_local.update(found)

    split_i_used = {s["i"] for s in splits}
    leftover1_remaining = [i for i in leftover1 if i not in split_i_used]
    leftover2_remaining = [j for j in leftover2 if j not in used_j_local]

    used_i_local = set()
    for j in leftover2_remaining:
        b = df2.iloc[j]
        if pd.isna(b.get("Amount")):
            continue
        pool = [i for i in leftover1_remaining if i not in used_i_local and pd.notna(df1.iloc[i].get("Amount")) and within_window(df1.iloc[i], b)]
        pool = pool[:pool_limit]
        found = None
        for r in range(2, max_combo + 1):
            for combo in itertools.combinations(pool, r):
                total = sum(df1.iloc[i]["Amount"] for i in combo)
                if amount_ok(b["Amount"], total):
                    found = combo
                    break
            if found:
                break
        if found:
            combined.append({"j": j, "is": list(found), "target": b["Amount"], "sum": sum(df1.iloc[i]["Amount"] for i in found)})
            used_i_local.update(found)

    final_used_i = set(used_i) | split_i_used | used_i_local
    final_used_j = set(used_j) | used_j_local | {c["j"] for c in combined}
    return splits, combined, final_used_i, final_used_j


def find_duplicates(df, flags):
    """Flag rows within a single file that look like duplicate entries."""
    key_cols = []
    if flags.get("Amount"):
        key_cols.append("Amount")
    if flags.get("Reference"):
        key_cols.append("Reference")
    elif flags.get("Date"):
        key_cols.append("Date")
    if not key_cols or "Amount" not in key_cols:
        return pd.DataFrame()
    sub = df.dropna(subset=key_cols, how="any")
    if sub.empty:
        return pd.DataFrame()
    dup_mask = sub.duplicated(subset=key_cols, keep=False)
    return sub[dup_mask].copy()


def run_reconciliation(df1_orig, df2_orig, mapping1, mapping2):
    """Runs the full multi-pass reconciliation and returns a results dict."""
    std1, flags1 = build_standard_frame(df1_orig, mapping1)
    std2, flags2 = build_standard_frame(df2_orig, mapping2)
    # Combined flags: a field only "counts" for scoring if mapped on both sides
    flags = {f: (flags1.get(f, False) and flags2.get(f, False)) for f in FIXED_FIELDS}

    # Pass 1 & 2 & 3 combined into one weighted-scoring pass (see score_pair)
    candidates = generate_candidates(std1, std2, flags)
    full_matches, partial_matches, used_i, used_j = greedy_assign(candidates, min_score=30)

    # Pass 4: split & combined payments
    splits, combined, used_i, used_j = find_split_and_combined(std1, std2, used_i, used_j, flags)

    # Remaining exceptions
    unmatched1 = [i for i in range(len(std1)) if i not in used_i]
    unmatched2 = [j for j in range(len(std2)) if j not in used_j]

    duplicates1 = find_duplicates(std1, flags1)
    duplicates2 = find_duplicates(std2, flags2)

    return {
        "std1": std1, "std2": std2, "flags": flags, "flags1": flags1, "flags2": flags2,
        "full_matches": full_matches, "partial_matches": partial_matches,
        "splits": splits, "combined": combined,
        "unmatched1": unmatched1, "unmatched2": unmatched2,
        "duplicates1": duplicates1, "duplicates2": duplicates2,
    }


def render_upload_slot(col, slot: int):
    """
    Renders one upload slot:
    - If no file stored yet -> show the file_uploader.
    - If a file IS stored -> hide the uploader, show a card with the
      filename, its extension badge, and a Delete button. The uploader
      only re-appears after Delete is pressed.
    """
    name_key = f"file{slot}_name"
    bytes_key = f"file{slot}_bytes"
    uploader_key = f"uploader{slot}_key"

    with col:
        st.markdown(f'<div class="upload-label">File {slot}</div>', unsafe_allow_html=True)

        if st.session_state[name_key] is None:
            uploaded = st.file_uploader(
                "Upload file",
                type=list(ALLOWED_EXTENSIONS),
                key=f"uploader{slot}_{st.session_state[uploader_key]}",
                help="Accepted formats: CSV, XLSX, XLS, PDF",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                ext = get_extension(uploaded.name)
                if ext in ALLOWED_EXTENSIONS:
                    st.session_state[name_key] = uploaded.name
                    st.session_state[bytes_key] = uploaded.getvalue()
                    st.rerun()
                else:
                    st.markdown(
                        f'<div class="file-err">❌ \'.{ext}\' is not supported. '
                        f'Please upload CSV, XLSX, XLS, or PDF.</div>',
                        unsafe_allow_html=True,
                    )
        else:
            ext = get_extension(st.session_state[name_key]).upper()
            info_col, del_col = st.columns([5, 1])
            with info_col:
                st.markdown(
                    f'<div class="file-ok">✅ <b>{st.session_state[name_key]}</b>'
                    f'<span class="file-ext-badge">{ext}</span></div>',
                    unsafe_allow_html=True,
                )
            with del_col:
                if st.button("🗑️", key=f"delete_btn_{slot}", help="Remove this file"):
                    delete_file(slot)
                    st.rerun()



# --------------------------------------------------------------------------
# Upload section
# --------------------------------------------------------------------------
col1, col2 = st.columns(2, gap="large")
render_upload_slot(col1, 1)
render_upload_slot(col2, 2)

file1_ready = st.session_state.file1_bytes is not None
file2_ready = st.session_state.file2_bytes is not None

st.write("")

# Process button sits narrow & centered directly under File 1's column;
# Reset sits narrow & centered directly under File 2's column (only once processed).
proc_col, reset_col = st.columns(2, gap="large")

with proc_col:
    p_l, p_c, p_r = st.columns([1.4, 1, 1.4])
    with p_c:
        process_clicked = st.button(
            "Process",
            disabled=not (file1_ready and file2_ready),
            type="primary",
            use_container_width=True,
        )
    if not (file1_ready and file2_ready):
        st.markdown(
            "<div style='text-align:center; font-size:0.82rem; color:#8a8aa3;'>"
            "Upload both files to enable Process.</div>",
            unsafe_allow_html=True,
        )

with reset_col:
    if st.session_state.processed:
        r_l, r_c, r_r = st.columns([1.4, 1, 1.4])
        with r_c:
            if st.button("↺ Reset", type="secondary", use_container_width=True):
                reset_app()
                st.rerun()

# --------------------------------------------------------------------------
# Process files -> load & clean them, then hand off to the mapping step
# (auto-detection / reconciliation itself no longer happens automatically —
# the user confirms or adjusts the mapping first, see the section below).
# --------------------------------------------------------------------------
if process_clicked and file1_ready and file2_ready:
    with st.spinner("Reading files and detecting headers..."):
        df1, err1 = load_dataframe(st.session_state.file1_bytes, st.session_state.file1_name)
        df2, err2 = load_dataframe(st.session_state.file2_bytes, st.session_state.file2_name)

    if err1:
        st.error(f"File 1 ({st.session_state.file1_name}): {err1}")
    if err2:
        st.error(f"File 2 ({st.session_state.file2_name}): {err2}")

    if df1 is not None and df2 is not None:
        st.session_state.df1 = df1
        st.session_state.df2 = df2
        st.session_state.processed = True
        st.session_state.reconciled = False
        st.session_state.recon_results = None
        clear_mapping_widget_state()
        st.rerun()
    else:
        st.session_state.processed = False

# --------------------------------------------------------------------------
# Column mapping step
# Shown once files are processed and before reconciliation has run.
# One row per fixed field (Date, Amount, Description, Reference), one
# dropdown column per uploaded file (headed with the actual file names),
# each dropdown pre-filled with our best keyword-based guess.
# --------------------------------------------------------------------------
MAP_FIELD_ORDER = ["Date", "Amount", "Description", "Reference"]

if (
    st.session_state.processed
    and st.session_state.df1 is not None
    and st.session_state.df2 is not None
    and not st.session_state.reconciled
):
    df1 = st.session_state.df1
    df2 = st.session_state.df2
    name1 = st.session_state.file1_name
    name2 = st.session_state.file2_name

    cols1 = list(df1.columns.astype(str))
    cols2 = list(df2.columns.astype(str))
    options1 = [BLANK_OPTION] + cols1
    options2 = [BLANK_OPTION] + cols2

    auto1 = auto_detect_mapping(cols1)
    auto2 = auto_detect_mapping(cols2)

    st.markdown('<div class="section-title">Map Columns</div>', unsafe_allow_html=True)
    st.caption(
        "Each dropdown is pre-filled with our best guess based on the file's own "
        "headers — change any of them if it picked the wrong column. "
        "**Date** and **Amount** are required for both files. "
        "**Reference** and **Description** are optional, but if you use one, "
        "it must be set on both files."
    )

    st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
    hdr_l, hdr_1, hdr_2 = st.columns([1.2, 2, 2])
    with hdr_l:
        st.markdown('<div class="mapping-header">Field</div>', unsafe_allow_html=True)
    with hdr_1:
        st.markdown(f'<div class="mapping-header">{name1}</div>', unsafe_allow_html=True)
    with hdr_2:
        st.markdown(f'<div class="mapping-header">{name2}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    selections1, selections2 = {}, {}

    for field in MAP_FIELD_ORDER:
        st.markdown('<div class="mapping-row">', unsafe_allow_html=True)
        lbl_col, sel1_col, sel2_col = st.columns([1.2, 2, 2])
        with lbl_col:
            st.markdown(f"**{field}**")

        default1 = auto1.get(field)
        idx1 = options1.index(default1) if default1 in options1 else 0
        with sel1_col:
            selections1[field] = st.selectbox(
                field, options1, index=idx1, key=f"map1_{field}", label_visibility="collapsed"
            )

        default2 = auto2.get(field)
        idx2 = options2.index(default2) if default2 in options2 else 0
        with sel2_col:
            selections2[field] = st.selectbox(
                field, options2, index=idx2, key=f"map2_{field}", label_visibility="collapsed"
            )
        st.markdown('</div>', unsafe_allow_html=True)

    date_ok = selections1["Date"] != BLANK_OPTION and selections2["Date"] != BLANK_OPTION
    amount_ok = selections1["Amount"] != BLANK_OPTION and selections2["Amount"] != BLANK_OPTION

    def _paired_ok(field):
        set1 = selections1[field] != BLANK_OPTION
        set2 = selections2[field] != BLANK_OPTION
        return set1 == set2  # both selected, or both left blank

    reference_ok = _paired_ok("Reference")
    description_ok = _paired_ok("Description")

    can_run = date_ok and amount_ok and reference_ok and description_ok

    mapping_warnings = []
    if not date_ok:
        mapping_warnings.append("select **Date** for both files")
    if not amount_ok:
        mapping_warnings.append("select **Amount** for both files")
    if not reference_ok:
        mapping_warnings.append("select **Reference** for both files, or leave it blank on both")
    if not description_ok:
        mapping_warnings.append("select **Description** for both files, or leave it blank on both")

    st.write("")
    run_l, run_c, run_r = st.columns([1.4, 1, 1.4])
    with run_c:
        run_clicked = st.button(
            "Run Reconciliation",
            disabled=not can_run,
            type="primary",
            use_container_width=True,
        )
    if not can_run:
        st.markdown(
            "<div style='text-align:center; font-size:0.82rem; color:#8a8aa3;'>"
            + ("Please " + "; ".join(mapping_warnings) + "." if mapping_warnings else "")
            + "</div>",
            unsafe_allow_html=True,
        )

    if run_clicked and can_run:
        mapping1 = {f: (selections1[f] if selections1[f] != BLANK_OPTION else None) for f in FIXED_FIELDS}
        mapping2 = {f: (selections2[f] if selections2[f] != BLANK_OPTION else None) for f in FIXED_FIELDS}
        with st.spinner("Running deterministic rule-based reconciliation..."):
            results = run_reconciliation(df1, df2, mapping1, mapping2)
            results["mapping1"] = mapping1
            results["mapping2"] = mapping2
        st.session_state.recon_results = results
        st.session_state.reconciled = True
        st.rerun()

# --------------------------------------------------------------------------
# Reconciliation results
# --------------------------------------------------------------------------
if st.session_state.reconciled and st.session_state.recon_results is not None:
    R = st.session_state.recon_results
    name1 = st.session_state.file1_name
    name2 = st.session_state.file2_name
    std1, std2 = R["std1"], R["std2"]
    flags1, flags2 = R["flags1"], R["flags2"]

    # Display-only copies with dates rendered in a single standardized format
    std1_disp = std1.copy()
    std2_disp = std2.copy()
    if "Date" in std1_disp.columns:
        std1_disp["Date"] = std1_disp["Date"].apply(format_date_display)
    if "Date" in std2_disp.columns:
        std2_disp["Date"] = std2_disp["Date"].apply(format_date_display)

    st.markdown('<div class="section-title">Reconciliation Results</div>', unsafe_allow_html=True)

    n_full = len(R["full_matches"])
    n_partial = len(R["partial_matches"])
    n_split = len(R["splits"])
    n_combined = len(R["combined"])
    n_unmatched = len(R["unmatched1"]) + len(R["unmatched2"])
    n_dupes = len(R["duplicates1"]) + len(R["duplicates2"])

    s1, s2, s3, s4, s5, s6 = st.columns(6)
    for col, num, lbl in [
        (s1, n_full, "Fully Matched"),
        (s2, n_partial, "Partially Matched"),
        (s3, n_split, "Split Payments"),
        (s4, n_combined, "Combined Payments"),
        (s5, n_unmatched, "Exceptions"),
        (s6, n_dupes, "Possible Duplicates"),
    ]:
        with col:
            st.markdown(
                f'<div class="recon-summary-card"><div class="num">{num}</div>'
                f'<div class="lbl">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

    st.write("")

    def display_cols(std, flags):
        return [f for f in FIXED_FIELDS if flags.get(f)]

    disp1_cols = display_cols(std1, flags1)
    disp2_cols = display_cols(std2, flags2)

    # ---- Fully matched ----
    st.markdown("#### <span class='badge-full'>Fully Matched</span>", unsafe_allow_html=True)
    if n_full:
        rows = []
        for m in R["full_matches"]:
            i, j = m["i"], m["j"]
            row = {f"{name1} Row": i + 1, f"{name2} Row": j + 1, "Score": m["score"]}
            for f in disp1_cols:
                row[f"{name1}: {f}"] = std1_disp.iloc[i][f]
            for f in disp2_cols:
                row[f"{name2}: {f}"] = std2_disp.iloc[j][f]
            row["Match Basis"] = "; ".join(m["parts"])
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No fully matched transactions found.")

    # ---- Partially matched ----
    st.markdown("#### <span class='badge-partial'>Partially Matched — Needs Review</span>", unsafe_allow_html=True)
    if n_partial:
        rows = []
        for m in R["partial_matches"]:
            i, j = m["i"], m["j"]
            row = {f"{name1} Row": i + 1, f"{name2} Row": j + 1, "Score": m["score"]}
            for f in disp1_cols:
                row[f"{name1}: {f}"] = std1_disp.iloc[i][f]
            for f in disp2_cols:
                row[f"{name2}: {f}"] = std2_disp.iloc[j][f]
            row["Match Basis"] = "; ".join(m["parts"])
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No partial matches found.")

    # ---- Split payments (one-to-many) ----
    st.markdown("#### <span class='badge-split'>Split Payments (1 → many)</span>", unsafe_allow_html=True)
    if n_split:
        rows = []
        for s in R["splits"]:
            row = {
                f"{name1} Row": s["i"] + 1,
                f"{name1} Amount": std1.iloc[s["i"]].get("Amount"),
                f"{name2} Rows": ", ".join(str(j + 1) for j in s["js"]),
                f"{name2} Sum": round(s["sum"], 2),
            }
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No split payments detected.")

    # ---- Combined payments (many-to-one) ----
    st.markdown("#### <span class='badge-split'>Combined Payments (many → 1)</span>", unsafe_allow_html=True)
    if n_combined:
        rows = []
        for c in R["combined"]:
            row = {
                f"{name2} Row": c["j"] + 1,
                f"{name2} Amount": std2.iloc[c["j"]].get("Amount"),
                f"{name1} Rows": ", ".join(str(i + 1) for i in c["is"]),
                f"{name1} Sum": round(c["sum"], 2),
            }
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No combined payments detected.")

    # ---- Unmatched / exceptions ----
    st.markdown("#### <span class='badge-unmatched'>Unmatched — Exceptions</span>", unsafe_allow_html=True)
    exc_c1, exc_c2 = st.columns(2)
    with exc_c1:
        st.caption(f"**{name1}** ({len(R['unmatched1'])} unmatched)")
        if R["unmatched1"]:
            st.dataframe(std1_disp.iloc[R["unmatched1"]][disp1_cols], use_container_width=True, hide_index=True)
        else:
            st.caption("None — every row matched.")
    with exc_c2:
        st.caption(f"**{name2}** ({len(R['unmatched2'])} unmatched)")
        if R["unmatched2"]:
            st.dataframe(std2_disp.iloc[R["unmatched2"]][disp2_cols], use_container_width=True, hide_index=True)
        else:
            st.caption("None — every row matched.")

    # ---- Duplicates ----
    st.markdown("#### 🔁 Possible Duplicate Entries")
    dup1_disp = R["duplicates1"].copy()
    dup2_disp = R["duplicates2"].copy()
    if "Date" in dup1_disp.columns:
        dup1_disp["Date"] = dup1_disp["Date"].apply(format_date_display)
    if "Date" in dup2_disp.columns:
        dup2_disp["Date"] = dup2_disp["Date"].apply(format_date_display)
    dup_c1, dup_c2 = st.columns(2)
    with dup_c1:
        st.caption(f"**{name1}**")
        if not dup1_disp.empty:
            st.dataframe(dup1_disp, use_container_width=True, hide_index=True)
        else:
            st.caption("No duplicates detected.")
    with dup_c2:
        st.caption(f"**{name2}**")
        if not dup2_disp.empty:
            st.dataframe(dup2_disp, use_container_width=True, hide_index=True)
        else:
            st.caption("No duplicates detected.")