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

st.title("ACH Participants Dashboard")
st.caption("Source: BancNet / PCHC")

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

        # ---- Robust "as of" extraction ----
        first_row = raw.iloc[0].dropna().astype(str).tolist()
        joined = " ".join(first_row)

        subtitle = ""
        m = re.search(r"as of\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", joined, re.IGNORECASE)
        if m:
            subtitle = f"as of {m.group(1)}"

        # ---- Actual data starts at row 2 ----
        headers = raw.iloc[1].astype(str).str.strip().tolist()
        df = raw.iloc[2:].copy()
        df.columns = headers
        df = df.dropna(how="all")

        data[sheet] = (subtitle, df)

    return data


if not DATA_FILE.exists():
    st.error("ACHdata.xlsx not found in repository root.")
    st.stop()

sheets_data = load_participant_sheets(
    DATA_FILE,
    DATA_FILE.stat().st_mtime
)

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
# Sidebar filters (per tab)
# =========================
with st.sidebar:
    st.markdown(f"### {active_sheet} Filters")

    # Category filter (Sender/Receiver OR Issuer/Acquirer)
    if "Category" in df.columns:
        cats = sorted(df["Category"].dropna().unique())
        sel_cats = st.multiselect("Category", cats, default=cats)
    else:
        sel_cats = None

    # Institution Type filter
    if "Institution Type" in df.columns:
        inst_types = sorted(df["Institution Type"].dropna().unique())
        sel_inst_types = st.multiselect("Institution Type", inst_types, default=inst_types)
    else:
        sel_inst_types = None

    search = st.text_input("Search institution")

# =========================
# Apply filters
# =========================
dff = df.copy()

if sel_cats is not None:
    dff = dff[dff["Category"].isin(sel_cats)]

if sel_inst_types is not None:
    dff = dff[dff["Institution Type"].isin(sel_inst_types)]

if search:
    dff = dff[dff["Institution"].str.contains(search, case=False, na=False)]

# =========================
# Header
# =========================
st.subheader(active_sheet)
if subtitle:
    st.caption(subtitle)

# =========================
# Summary table
# =========================
INST_TYPE_SHORT = {
    "Universal and Commercial Banks (U/KBs)": "U/KBs",
    "Thrift Banks (TBs)": "TBs",
    "Rural Banks (RBs)": "RBs",
    "Digital Banks": "DBs",
    "Electronic Money Issuers (EMI) - Others": "EMI-NBFI",
}

if {"Category", "Institution Type"}.issubset(dff.columns):
    summary = (
        dff.groupby(["Category", "Institution Type"])
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

    pivot = pivot.rename(columns=INST_TYPE_SHORT)
    pivot = pivot[[c for c in INST_TYPE_SHORT.values() if c in pivot.columns]]

    pivot["TOTAL"] = pivot.sum(axis=1)

    total_row = pivot.sum(axis=0).to_frame().T
    total_row.index = ["TOTAL"]
    pivot = pd.concat([pivot, total_row])

    pivot = pivot.replace(0, "–")

    st.markdown("### Summary by Participation Role and Institution Type")
    st.dataframe(pivot, use_container_width=True)

st.divider()

# =========================
# PDF-style layout
# =========================
INST_TYPE_ORDER = list(INST_TYPE_SHORT.keys())

# Role labels
if active_sheet.lower().startswith("egov"):
    ROLE_MAP = {
        "Issuer": "ISSUING BANKS",
        "Acquirer": "ACQUIRING BANKS",
    }
else:
    ROLE_MAP = {
        "Sender/Receiver": "SENDER/RECEIVER",
        "Sender Only": "SENDER ONLY",
        "Receiver Only": "RECEIVER ONLY",
    }

for inst_type in INST_TYPE_ORDER:
    block = dff[dff["Institution Type"] == inst_type]

    if block.empty:
        continue

    st.markdown(f"## {inst_type}")

    for role_value, role_label in ROLE_MAP.items():
        role_block = block[block["Category"] == role_value]

        if role_block.empty:
            continue

        st.markdown(f"**{role_label}**")

        table = (
            role_block[["Institution"]]
            .sort_values("Institution")
            .reset_index(drop=True)
        )
        table.index = table.index + 1

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=False,
            height=min(400, 35 * len(table) + 35)
        )

    st.divider()

#st.caption(
    #"This view mirrors the official PDF layout while retaining live, "
    #"filterable data from row-level Excel sources."
#)
