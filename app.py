import re
from pathlib import Path
from typing import Dict

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

# PDFs are stored in repo root
DATA_DIR = Path(".")

# Map payment streams to PDFs
PAYMENT_STREAMS = {
    "InstaPay": "instapay.pdf",
    "PESONet": "pesonet.pdf",
    # Add more later:
    # "Bills Pay": "billspay.pdf",
    # "eGov Pay": "egovpay.pdf",
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
                for cat, short in CATEGORY_MAP.items():
                    if cat in line:
                        current_category = short

                # Detect role headers
                for header, role in ROLE_HEADERS.items():
                    if line.upper().startswith(header):
                        current_role = ro_
