from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import streamlit as st

# =========================
# App config
# =========================
st.set_page_config(
    page_title="ACH Participants Dashboard",
    layout="wide"
)

st.title("ACH Participants Dashboard")
st.caption("Source: BancNet / PCHC")

DATA_FILE = Path("ACHdata.xlsx")

# =========================
# Load Excel (row-level, cache-safe)
# =========================
@st.cache_data
def load_participant_sheets(
    xlsx_path: Path,
    mtime: float
) -> Dict[str, Tuple[str, pd.DataFrame]]:
    xls = pd.ExcelFile(xlsx_path, engine="openpyxl")
    data = {}

    for sheet in xls.sheet_names:
        if not sheet.strip().endswith("Participants"):
            continue

        raw = pd.read_excel(xlsx_path, sheet_name=sheet, header=None)

        # Row 1: metadata
        subtitle_parts = raw.iloc[0].dropna().astype(str).tolist()
        subtitle = " • ".join(subtitle_parts)

        # Row 2: headers
        headers = raw.iloc[1].astype(str).str.strip().tolist()

        # Row 3+: data
        df = raw.iloc[2:].copy()
        df.columns = headers
        df = df.dropna(how="all")

        df.columns = [c.strip() for c in df.columns]

        data[sheet] = (subtitle, df)

    return data


if not DATA_FILE.exists():
    st.error("ACHdata.xlsx not found in repository root.")
    st.stop()

sheets_data = load_participant_sheets(
    DATA_FILE,
    DATA_FILE.stat().st_mtime
)

if not sheets_data:
    st.error("No '*Participants' sheets found.")
    st.stop()

# =========================
# Navigation (tab replacement)
# =========================
sheet_names = list(sheets_data.keys())

active_sheet = st.radio(
    "",
    sheet_names,
    horizontal=True,
    label_visibility="collapsed"
)

subtitle, df = sheets_data[active_sheet]

# =========================
# Sidebar (ONLY active sheet)
# =========================
is_egov = active_sheet.lower().startswith("egov")
role_label = "Issuer / Acquirer" if is_egov else "Participation Role"

with st.sidebar:
    st.markdown(f"### {active_sheet} Filters")

    # ---- Category filter (U/KBs, TBs, etc.)
    if "Category" in df.columns:
        categories = sorted(df["Category"].dropna().unique())
        sel_categories = st.multiselect(
            "Category",
            categories,
            default=categories
        )
    else:
        sel_categories = None

    # ---- Institution Type filter (descriptive)
    if "Institution Type" in df.columns:
        inst_types = sorted(df["Institution Type"].dropna().unique())
        sel_inst_types = st.multiselect(
            "Institution Type",
            inst_types,
            default=inst_types
        )
    else:
        sel_inst_types = None

    # ---- Role filter
    if "Role" in df.columns:
        roles = sorted(df["Role"].dropna().unique())
        sel_roles = st.multiselect(
            role_label,
            roles,
            default=roles
        )
    else:
        sel_roles = None

    # ---- Search
    search = st.text_input("Search institution")

# =========================
# Apply filters
# =========================
dff = df.copy()

if sel_categories is not None:
    dff = dff[dff["Category"].isin(sel_categories)]

if sel_inst_types is not None:
    dff = dff[dff["Institution Type"].isin(sel_inst_types)]

if sel_roles is not None:
    dff = dff[dff["Role"].isin(sel_roles)]

if search and "Institution" in dff.columns:
    dff = dff[dff["Institution"].str.contains(search, case=False, na=False)]

# =========================
# Main content
# =========================
st.subheader(active_sheet)
if subtitle:
    st.caption(subtitle)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total", len(dff))

for col, cat in zip(
    [k2, k3, k4, k5, k6],
    ["U/KBs", "TBs", "RBs", "DBs", "EMI-NBFI"]
):
    if "Category" in dff.columns:
        col.metric(cat, int((dff["Category"] == cat).sum()))
    else:
        col.metric(cat, "—")

st.divider()

st.dataframe(
    dff.sort_values("Institution") if "Institution" in dff.columns else dff,
    use_container_width=True,
    hide_index=True,
    height=520
)

st.caption(
    "Row-level data loaded from ACHdata.xlsx. "
    "Only '*Participants' worksheets are included."
)
