from pathlib import Path
from typing import Dict, Tuple
import re

import pandas as pd
import streamlit as st

# =========================
# App config
# =========================
st.set_page_config(
    page_title="ACH Participants Dashboard",
    layout="wide"
)

col1, col2 = st.columns([1, 2])

with col1:
    st.image("bsp_logo.png", width=90)

with col2:
    st.markdown("## ACH Participants Dashboard")
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

        # =========================
        # Row 1: metadata ("as of" only)
        # =========================
        first_row = raw.iloc[0].dropna().astype(str).tolist()
        joined = " ".join(first_row)

        subtitle = ""
        m = re.search(
            r"as of\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            joined,
            re.IGNORECASE
        )
        if m:
            subtitle = f"as of {m.group(1)}"

        # =========================
        # Row 2: headers
        # =========================
        headers = raw.iloc[1].astype(str).str.strip().tolist()

        # =========================
        # Row 3+: data
        # =========================
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
# Sidebar (ONLY active tab)
# =========================
with st.sidebar:
    st.markdown(f"### {active_sheet} Filters")

    # Category = participation role
    if "Category" in df.columns:
        categories = sorted(df["Category"].dropna().unique())
        sel_categories = st.multiselect(
            "Category",
            categories,
            default=categories
        )
    else:
        sel_categories = None

    # Institution Type
    if "Institution Type" in df.columns:
        inst_types = sorted(df["Institution Type"].dropna().unique())
        sel_inst_types = st.multiselect(
            "Institution Type",
            inst_types,
            default=inst_types
        )
    else:
        sel_inst_types = None

    # Search
    search = st.text_input("Search institution")

# =========================
# Apply filters
# =========================
dff = df.copy()

if sel_categories is not None:
    dff = dff[dff["Category"].isin(sel_categories)]

if sel_inst_types is not None:
    dff = dff[dff["Institution Type"].isin(sel_inst_types)]

if search and "Institution" in dff.columns:
    dff = dff[dff["Institution"].str.contains(search, case=False, na=False)]

# =========================
# Main header
# =========================
st.subheader(active_sheet)
if subtitle:
    st.caption(subtitle)

# =========================
# Summary matrix (Role × Institution Type)
# =========================
INST_TYPE_MAP = {
    "U/KBs": "Universal and Commercial Banks (U/KBs)",
    "TBs": "Thrift Banks (TBs)",
    "RBs": "Rural Banks (RBs)",
    "DBs": "Digital Banks",
    "EMI-NBFI": "Electronic Money Issuers (EMI) - Others",
}

if {"Category", "Institution Type"}.issubset(dff.columns):

    summary = (
        dff
        .groupby(["Category", "Institution Type"])
        .size()
        .reset_index(name="Count")
    )

    pivot = summary.pivot_table(
        index="Category",
        columns="Institution Type",
        values="Count",
        aggfunc="sum",
        fill_value=0
    )

    # Rename columns to short labels
    pivot = pivot.rename(
        columns={v: k for k, v in INST_TYPE_MAP.items()}
    )

    # Ensure column order
    pivot = pivot[[c for c in INST_TYPE_MAP.keys() if c in pivot.columns]]

    # Add TOTAL column
    pivot["TOTAL"] = pivot.sum(axis=1)

    # Add TOTAL row
    total_row = pivot.sum(axis=0).to_frame().T
    total_row.index = ["TOTAL"]
    pivot = pd.concat([pivot, total_row])

    # Replace zeros with dash
    pivot_display = pivot.replace(0, "–")

    st.markdown("### Summary by Participation Role and Institution Type")
    st.dataframe(
        pivot_display,
        use_container_width=True
    )

else:
    st.info("Summary table not available for this sheet.")

st.divider()

# =========================
# Detail table
# =========================
st.dataframe(
    dff.sort_values("Institution") if "Institution" in dff.columns else dff,
    use_container_width=True,
    hide_index=True,
    height=520
)

#st.caption(
    #"Summary and details are derived from row-level data in ACHdata.xlsx. "
    #"Only worksheets ending with '*Participants' are included."
#)
