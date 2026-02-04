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
# Stronger table borders
# =========================
st.markdown("""
<style>
[data-testid="stDataFrame"] table {
    border-collapse: collapse !important;
}
[data-testid="stDataFrame"] th,
[data-testid="stDataFrame"] td {
    border: 1px solid rgba(128,128,128,0.6) !important;
}
[data-testid="stDataFrame"] thead th {
    border-bottom: 2px solid rgba(128,128,128,0.9) !important;
}
</style>
""", unsafe_allow_html=True)

DATA_FILE = Path("ACHdata.xlsx")

# =========================
# Load Excel
# =========================
@st.cache_data
def load_participant_sheets(xlsx_path: Path, mtime: float) -> Dict[str, Tuple[str, pd.DataFrame]]:

    xls = pd.ExcelFile(xlsx_path, engine="openpyxl")
    data = {}

    for sheet in xls.sheet_names:

        if "Participants" not in sheet:
            continue

        raw = pd.read_excel(xlsx_path, sheet_name=sheet, header=None)

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
# PASSWORD FOR Bills Pay Participants (Full)
# =========================
APP_PASSWORD = os.getenv("APP_PASSWORD", "GovAdrian")

if active_sheet == "Bills Pay Participants (Full)":

    if "bills_full_authenticated" not in st.session_state:
        st.session_state.bills_full_authenticated = False

    if not st.session_state.bills_full_authenticated:
        st.warning("🔐 This tab is password protected")

        password = st.text_input(
            "Enter password to access Bills Pay Participants (Full)",
            type="password"
        )

        if password == APP_PASSWORD:
            st.session_state.bills_full_authenticated = True
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
# Institution Type Mapping
# =========================
INST_TYPE_SHORT = {
    "Universal and Commercial Banks (U/KBs)": "UKBs",
    "Thrift Banks (TBs)": "TBs",
    "Rural Banks (RBs)": "RBs",
    "Digital Banks": "DBs",
    "Electronic Money Issuers (EMI) - Others": "EMI-NBFI",
}

# =========================
# SUMMARY — FULL TAB (INDEPENDENT QR/NON-QR LOGIC)
# =========================
if active_sheet == "Bills Pay Participants (Full)" and not search:

    required_cols = {
        "Institution Type",
        "QR Sender",
        "QR Receiver",
        "Non-QR Sender",
        "Non-QR Receiver"
    }

    if required_cols.issubset(dff.columns):

        temp = dff.copy()

        # Normalize booleans properly
        for col in ["QR Sender", "QR Receiver", "Non-QR Sender", "Non-QR Receiver"]:
            temp[col] = temp[col].astype(str).str.upper().eq("TRUE")

        records = []

        for _, row in temp.iterrows():

            inst_type = row["Institution Type"]

            qr_s = row["QR Sender"]
            qr_r = row["QR Receiver"]
            nqr_s = row["Non-QR Sender"]
            nqr_r = row["Non-QR Receiver"]

            # QR categories
            if qr_s and qr_r:
                records.append(("QR Sender/Receiver", inst_type))
            if qr_s and not qr_r:
                records.append(("QR Sender Only", inst_type))
            if not qr_s and qr_r:
                records.append(("QR Receiver Only", inst_type))

            # NON-QR categories (independent!)
            if nqr_s and nqr_r:
                records.append(("Non-QR Sender/Receiver", inst_type))
            if nqr_s and not nqr_r:
                records.append(("Non-QR Sender Only", inst_type))
            if not nqr_s and nqr_r:
                records.append(("Non-QR Receiver Only", inst_type))

        summary_df = pd.DataFrame(records, columns=["QR Category", "Institution Type"])

        pivot = summary_df.pivot_table(
            index="QR Category",
            columns="Institution Type",
            aggfunc="size",
            fill_value=0
        )

        pivot = pivot.rename(columns=INST_TYPE_SHORT)

        ordered_cols = [c for c in INST_TYPE_SHORT.values() if c in pivot.columns]
        pivot = pivot[ordered_cols]

        pivot["TOTAL"] = pivot.sum(axis=1)

        total_row = pivot.sum(axis=0).to_frame().T
        total_row.index = ["TOTAL"]
        pivot = pd.concat([pivot, total_row])

        pivot = pivot.replace(0, "–")

        st.markdown("### Summary by Institution Type and QR Category")
        st.dataframe(pivot, use_container_width=True)

        st.divider()

# =========================
# FULL TAB TABLE (5-column with ✅ ❌)
# =========================
if active_sheet == "Bills Pay Participants (Full)":

    for inst_type in INST_TYPE_SHORT.keys():

        block = dff[dff["Institution Type"] == inst_type]

        if block.empty:
            continue

        display_inst_type = (
            inst_type
            .replace("(U/KBs)", "(UKBs)")
            .replace("Rural Banks", "Rural and Cooperative Banks")
        )

        st.markdown(f"## {display_inst_type}")

        table = (
            block[[
                "Institution",
                "QR Sender",
                "QR Receiver",
                "Non-QR Sender",
                "Non-QR Receiver"
            ]]
            .sort_values("Institution")
            .reset_index(drop=True)
        )

        for col in ["QR Sender", "QR Receiver", "Non-QR Sender", "Non-QR Receiver"]:
            table[col] = table[col].astype(str).str.upper().map(
                {"TRUE": "✅", "FALSE": "❌"}
            )

        table.index = table.index + 1

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=False,
            height=min(600, 35 * len(table) + 35)
        )

        st.divider()

# =========================
# Footer
# =========================
st.caption("Source: BancNet / PCHC")
