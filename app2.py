from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import streamlit as st

# =========================
# App config
# =========================
st.set_page_config(
    page_title="ACH Participants Dashboard (PDF Style)",
    layout="wide"
)

st.title("ACH Participants Dashboard")
st.caption("PDF-style view • Source: BancNet / PCHC")

DATA_FILE = Path("ACHdata.xlsx")

# =========================
# Load Excel (row-level)
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

        subtitle_parts = raw.iloc[0].dropna().astype(str).tolist()
        subtitle = " • ".join(subtitle_parts)

        headers = raw.iloc[1].astype(str).str.strip().tolist()
        df = raw.iloc[2:].copy()
        df.columns = headers
        df = df.dropna(how="all")
        df.columns = [c.strip() for c in df.columns]

        data[sheet] = (subtitle, df)

    return data


if not DATA_FILE.exists():
    st.error("ACHdata.xlsx not found.")
    st.stop()

sheets_data = load_participant_sheets(
    DATA_FILE,
    DATA_FILE.stat().st_mtime
)

if not sheets_data:
    st.error("No '*Participants' sheets found.")
    st.stop()

# =========================
# Navigation
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
# Sidebar filters (simple)
# =========================
with st.sidebar:
    st.markdown(f"### {active_sheet} Filters")

    if "Category" in df.columns:
        categories = sorted(df["Category"].dropna().unique())
        sel_categories = st.multiselect(
            "Category",
            categories,
            default=categories
        )
    else:
        sel_categories = None

    search = st.text_input("Search institution")

# =========================
# Apply filters
# =========================
dff = df.copy()

if sel_categories is not None:
    dff = dff[dff["Category"].isin(sel_categories)]

if search:
    dff = dff[dff["Institution"].str.contains(search, case=False, na=False)]

# =========================
# Main header
# =========================
st.subheader(active_sheet)
if subtitle:
    st.caption(subtitle)

# =========================
# PDF-style grouped layout
# =========================
INST_TYPE_ORDER = [
    "Universal and Commercial Banks (U/KBs)",
    "Thrift Banks (TBs)",
    "Rural Banks (RBs)",
    "Digital Banks",
    "Electronic Money Issuers (EMI) - Others",
]

ROLE_ORDER = [
    "Sender/Receiver",
    "Sender Only",
    "Receiver Only",
]

for inst_type in INST_TYPE_ORDER:
    block = dff[dff["Institution Type"] == inst_type]

    if block.empty:
        continue

    st.markdown(f"## {inst_type}")

    for role in ROLE_ORDER:
        role_block = block[block["Category"] == role]

        if role_block.empty:
            continue

        st.markdown(f"**{role.upper()}**")

        table = (
            role_block[["Institution"]]
            .sort_values("Institution")
            .reset_index(drop=True)
        )
        table.index = table.index + 1  # numbering starts at 1

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=False,
            height=min(400, 35 * len(table) + 35)
        )

    st.divider()

st.caption(
    "This view mirrors the official PDF layout: "
    "grouped by Institution Type and Participation Role."
)
