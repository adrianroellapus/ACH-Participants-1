from pathlib import Path
from typing import Dict

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
st.caption("Source: BancNet / PCHC • Data as of December 2025")

DATA_FILE = Path("ACHdata.xlsx")

# =========================
# Load Excel (cache-safe)
# =========================
@st.cache_data
def load_all_sheets(xlsx_path: Path, mtime: float) -> Dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(xlsx_path, engine="openpyxl")
    data = {}

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)

        # Basic cleanup
        df = df.dropna(how="all").dropna(axis=1, how="all")
        df.columns = [c.strip() for c in df.columns]

        data[sheet] = df

    return data


if not DATA_FILE.exists():
    st.error("ACHdata.xlsx not found in repository root.")
    st.stop()

sheets_data = load_all_sheets(DATA_FILE, DATA_FILE.stat().st_mtime)

if not sheets_data:
    st.error("No sheets found in ACHdata.xlsx.")
    st.stop()

# =========================
# Tabs (one per sheet)
# =========================
tab_names = list(sheets_data.keys())
tabs = st.tabs(tab_names)

for tab, sheet_name in zip(tabs, tab_names):
    with tab:
        df = sheets_data[sheet_name].copy()

        st.subheader(f"{sheet_name} ACH Participants")

        if df.empty:
            st.warning("No data found in this sheet.")
            continue

        # =========================
        # Determine role labels
        # =========================
        is_egov = sheet_name.strip().lower() == "egov pay"

        role_label = "Role"
        role_display_name = "Issuer / Acquirer" if is_egov else "Participation Role"

        # =========================
        # Filters (ONLY for active tab)
        # =========================
        with st.sidebar:
            st.markdown(f"### {sheet_name} Filters")

            # Institution Type
            if "Category" in df.columns:
                cats = sorted(df["Category"].dropna().unique().tolist())
                sel_cats = st.multiselect(
                    "Institution Type",
                    options=cats,
                    default=cats,
                    key=f"{sheet_name}_cat"
                )
            else:
                sel_cats = None

            # Role filter (Sender/Receiver OR Issuer/Acquirer)
            if role_label in df.columns:
                roles = sorted(df[role_label].dropna().unique().tolist())
                sel_roles = st.multiselect(
                    role_display_name,
                    options=roles,
                    default=roles,
                    key=f"{sheet_name}_role"
                )
            else:
                sel_roles = None

            # Search
            search = st.text_input(
                "Search institution",
                key=f"{sheet_name}_search"
            )

        # =========================
        # Apply filters
        # =========================
        dff = df.copy()

        if sel_cats is not None:
            dff = dff[dff["Category"].isin(sel_cats)]

        if sel_roles is not None:
            dff = dff[dff[role_label].isin(sel_roles)]

        if search and "Institution" in dff.columns:
            dff = dff[dff["Institution"].str.contains(search, case=False, na=False)]

        # =========================
        # KPIs
        # =========================
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

        # =========================
        # Table
        # =========================
        st.dataframe(
            dff.sort_values("Institution") if "Institution" in dff.columns else dff,
            use_container_width=True,
            hide_index=True,
            height=520
        )

        st.caption(
            "Data loaded directly from ACHdata.xlsx. "
            "Each tab corresponds to a worksheet."
        )
