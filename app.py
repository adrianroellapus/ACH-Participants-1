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
# Load Excel (row-level, filtered sheets, cache-safe)
# =========================
@st.cache_data
def load_participant_sheets(
    xlsx_path: Path,
    mtime: float
) -> Dict[str, Tuple[str, pd.DataFrame]]:
    """
    Returns:
      {
        sheet_name: (subtitle_text, dataframe)
      }
    Only sheets ending with 'Participants' are included.
    """
    xls = pd.ExcelFile(xlsx_path, engine="openpyxl")
    data = {}

    for sheet in xls.sheet_names:
        # ✅ Only include sheets ending with "Participants"
        if not sheet.strip().endswith("Participants"):
            continue

        # Read entire sheet without headers
        raw = pd.read_excel(
            xlsx_path,
            sheet_name=sheet,
            header=None
        )

        # ---- Row 1: metadata (tab title / as-of date)
        subtitle_parts = raw.iloc[0].dropna().astype(str).tolist()
        subtitle = " • ".join(subtitle_parts)

        # ---- Row 2: column headers
        headers = raw.iloc[1].astype(str).str.strip().tolist()

        # ---- Row 3 onwards: row-level data
        df = raw.iloc[2:].copy()
        df.columns = headers
        df = df.dropna(how="all")

        # Defensive cleanup
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
    st.error("No '*Participants' sheets found in ACHdata.xlsx.")
    st.stop()

# =========================
# Tabs (one per Participants sheet)
# =========================
tab_names = list(sheets_data.keys())
tabs = st.tabs(tab_names)

for tab, sheet_name in zip(tabs, tab_names):
    with tab:
        subtitle, df = sheets_data[sheet_name]

        st.subheader(f"{sheet_name}")
        if subtitle:
            st.caption(subtitle)

        if df.empty:
            st.warning("No row-level data found in this sheet.")
            continue

        # =========================
        # EGov Pay role handling
        # =========================
        is_egov = sheet_name.lower().startswith("egov")

        role_col = "Role"
        role_label = "Issuer / Acquirer" if is_egov else "Participation Role"

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

            # Role filter
            if role_col in df.columns:
                roles = sorted(df[role_col].dropna().unique().tolist())
                sel_roles = st.multiselect(
                    role_label,
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
            dff = dff[dff[role_col].isin(sel_roles)]

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
            "Row-level data loaded from ACHdata.xlsx. "
            "Only worksheets ending with 'Participants' are included."
        )
