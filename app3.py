from pathlib import Path
from typing import Dict, Tuple
import re
import os

import pandas as pd
import streamlit as st

# =========================
# App config
# =========================
st.set_page_config(
    page_title="ACH Participants Dashboard",
    layout="wide"
)

# =========================
# Stronger table borders (light + dark mode)
# =========================
st.markdown("""
<style>

/* Make dataframe borders clearly visible */
[data-testid="stDataFrame"] table {
    border-collapse: collapse !important;
}

[data-testid="stDataFrame"] th,
[data-testid="stDataFrame"] td {
    border: 1px solid rgba(128,128,128,0.6) !important;
}

/* Slightly stronger header border */
[data-testid="stDataFrame"] thead th {
    border-bottom: 2px solid rgba(128,128,128,0.9) !important;
}

</style>
""", unsafe_allow_html=True)

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

        # Extract "as of YYYY-MM-DD"
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
# PASSWORD FOR QR Ph P2M TAB ONLY
# =========================
APP_PASSWORD = os.getenv("APP_PASSWORD", "PPDD")

if active_sheet == "Bills Pay Participants (Full)":

    if "qr_authenticated" not in st.session_state:
        st.session_state.qr_authenticated = False

    if not st.session_state.qr_authenticated:
        st.warning("🔐 This tab is password protected")

        password = st.text_input(
            "Enter password to access QR Ph P2M",
            type="password"
        )

        if password == APP_PASSWORD:
            st.session_state.qr_authenticated = True
            st.rerun()
        elif password:
            st.error("Incorrect password")

        st.stop()

# =========================
# HEADER
# =========================
col1, col2 = st.columns([1, 13])

with col1:
    st.image("bsp_logo.png", width=100)

with col2:
    st.markdown("## ACH Participants Dashboard")
    if subtitle:
        st.caption(subtitle)

st.subheader(active_sheet)

# =========================
# Sidebar filters
# =========================
with st.sidebar:
    st.markdown(f"### {active_sheet} Filters")

    if "Category" in df.columns:
        cats = sorted(df["Category"].dropna().unique())
        sel_cats = st.multiselect("Category", cats, default=cats)
    else:
        sel_cats = None

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
# Summary table
# =========================
INST_TYPE_SHORT = {
    "Universal and Commercial Banks (U/KBs)": "UKBs",
    "Thrift Banks (TBs)": "TBs",
    "Rural Banks (RBs)": "RBs",
    "Digital Banks": "DBs",
    "Electronic Money Issuers (EMI) - Others": "EMI-NBFI",
}

if not search and {"Category", "Institution Type"}.issubset(dff.columns):

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

    st.markdown("### Summary by Institution Type and Category")
    st.dataframe(pivot, use_container_width=True)

elif search:
    st.info("Summary hidden while searching. Clear search to restore summary.")

st.divider()

# =========================
# PDF-style layout
# =========================
INST_TYPE_ORDER = list(INST_TYPE_SHORT.keys())

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

    display_inst_type = (
        inst_type
            .replace("Universal and Commercial Banks (U/KBs)", "Universal and Commercial Banks (UKBs)")
            .replace("Rural Banks", "Rural and Cooperative Banks")
            .replace("Digital Banks", "Digital Banks (DBs)")
    )

    st.markdown(f"## {display_inst_type}")

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

# =========================
# Footer
# =========================
st.caption("Source: BancNet / PCHC")
