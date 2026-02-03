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
# Sidebar (light filters)
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
# Header
# =========================
st.subheader(active_sheet)
if subtitle:
    st.caption(subtitle)

# =========================
# SUMMARY MATRIX (unchanged)
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

    pivot = pivot.rename(columns={v: k for k, v in INST_TYPE_MAP.items()})
    pivot = pivot[[c for c in INST_TYPE_MAP.keys() if c in pivot.columns]]

    pivot["TOTAL"] = pivot.sum(axis=1)

    total_row = pivot.sum(axis=0).to_frame().T
    total_row.index = ["TOTAL"]
    pivot = pd.concat([pivot, total_row])

    pivot_display = pivot.replace(0, "–")

    st.markdown("### Summary by Participation Role and Institution Type")
    st.dataframe(pivot_display, use_container_width=True)

st.divider()

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

# Role labels differ ONLY for EGov
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
    #"This view mirrors the official PDF layout, with EGov Pay "
    #"using Issuing / Acquiring bank labels."
#)
