import re
from pathlib import Path
from typing import List, Dict

import pdfplumber
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

DATA_DIR = Path(".")

# Map payment streams to PDFs
PAYMENT_STREAMS = {
    "InstaPay": "InstaPay ACH Participants (as of December 2025).pdf",
    "PESONet": "PESONet ACH Participants (as of December 2025).pdf",
    # Add more later:
    # "Bills Pay": "BillsPay.pdf",
    # "eGov Pay": "EGovPay.pdf",
}

# =========================
# PDF Parsing Helpers
# =========================
CATEGORY_MAP = {
    "Universal and Commercial Banks": "U/KBs",
    "Thrift Banks": "TBs",
    "Rural Banks": "RBs",
    "Digital Banks": "DBs",
    "EMI-Non-Bank Financial Institutions": "EMI-NBFI",
}

ROLE_HEADERS = {
    "SENDER/RECEIVER": "Sender/Receiver",
    "RECEIVER ONLY": "Receiver Only",
    "SENDER ONLY": "Sender Only",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@st.cache_data
def load_ach_pdf(pdf_path: Path) -> pd.DataFrame:
    rows = []
    current_category = None
    current_role = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = [normalize(l) for l in text.split("\n") if l.strip()]

            for line in lines:
                # Detect category headers
                for cat in CATEGORY_MAP:
                    if cat in line:
                        current_category = CATEGORY_MAP[cat]

                # Detect role headers
                for rh, role in ROLE_HEADERS.items():
                    if line.upper().startswith(rh):
                        current_role = role

                # Detect numbered institution lines
                m = re.match(r"^\d+\.\s+(.*)", line)
                if m and current_category and current_role:
                    name = m.group(1).strip()
                    rows.append({
                        "Institution": name,
                        "Category": current_category,
                        "Role": current_role
                    })

    return pd.DataFrame(rows)


# =========================
# Load all streams
# =========================
@st.cache_data
def load_all_streams() -> Dict[str, pd.DataFrame]:
    data = {}
    for stream, file_name in PAYMENT_STREAMS.items():
        pdf_path = DATA_DIR / file_name
        if not pdf_path.exists():
            continue
        data[stream] = load_ach_pdf(pdf_path)
    return data


streams_data = load_all_streams()

if not streams_data:
    st.error("No PDF data files found.")
    st.stop()

# =========================
# Tabs per payment stream
# =========================
tabs = st.tabs(list(streams_data.keys()))

for tab, (stream_name, df) in zip(tabs, streams_data.items()):
    with tab:
        st.subheader(f"{stream_name} ACH Participants")

        if df.empty:
            st.warning("No participants extracted from this PDF.")
            continue

        # =========================
        # Sidebar filters (per tab)
        # =========================
        with st.sidebar:
            st.markdown(f"### {stream_name} Filters")

            cats = sorted(df["Category"].unique())
            sel_cats = st.multiselect(
                "Institution Type",
                options=cats,
                default=cats,
                key=f"{stream_name}_cat"
            )

            roles = sorted(df["Role"].unique())
            sel_roles = st.multiselect(
                "Participation Role",
                options=roles,
                default=roles,
                key=f"{stream_name}_role"
            )

            search = st.text_input(
                "Search institution",
                key=f"{stream_name}_search"
            )

        dff = df.copy()
        dff = dff[dff["Category"].isin(sel_cats)]
        dff = dff[dff["Role"].isin(sel_roles)]

        if search:
            dff = dff[dff["Institution"].str.contains(search, case=False)]

        # =========================
        # KPIs
        # =========================
        k1, k2, k3, k4, k5, k6 = st.columns(6)

        k1.metric("Total", len(dff))
        for col, cat in zip([k2, k3, k4, k5, k6], ["U/KBs", "TBs", "RBs", "DBs", "EMI-NBFI"]):
            col.metric(cat, int((dff["Category"] == cat).sum()))

        st.divider()

        # =========================
        # Table
        # =========================
        st.dataframe(
            dff.sort_values("Institution"),
            use_container_width=True,
            hide_index=True,
            height=520
        )

        st.caption(
            "Parsed directly from official ACH Participants PDFs "
            "using pdfplumber. Names and classifications follow the source document."
        )
