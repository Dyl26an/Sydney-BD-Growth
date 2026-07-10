from __future__ import annotations
import io, re
from pathlib import Path
from typing import Optional
import pandas as pd
import msoffcrypto


def read_excel_file(uploaded_file, password: str | None = None) -> pd.DataFrame:
    data = uploaded_file.read()
    bio = io.BytesIO(data)
    if password:
        try:
            office = msoffcrypto.OfficeFile(bio)
            out = io.BytesIO()
            office.load_key(password=password)
            office.decrypt(out)
            out.seek(0)
            return pd.read_excel(out, sheet_name=0, engine="openpyxl")
        except Exception:
            bio.seek(0)
    bio.seek(0)
    return pd.read_excel(bio, sheet_name=0, engine="openpyxl")


def infer_month(df: pd.DataFrame, filename: str) -> str:
    # 1) look for month/date columns
    for col in df.columns:
        c = str(col).lower()
        if any(k in c for k in ["month", "月份", "统计月份", "年月", "date", "日期"]):
            s = df[col].dropna().astype(str)
            if not s.empty:
                val = s.iloc[0]
                m = re.search(r"(20\d{2})[-_/年.]?\s*(0?[1-9]|1[0-2])", val)
                if m:
                    return f"{m.group(1)}-{int(m.group(2)):02d}"
    # 2) filename
    m = re.search(r"(20\d{2})[-_/ .]?(0?[1-9]|1[0-2])", filename)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return Path(filename).stem[:30]


def clean_numeric(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    s = series.copy()
    if s.dtype == object:
        s = s.astype(str).str.replace('%','', regex=False).str.replace(',','', regex=False).str.replace('$','', regex=False).str.strip()
    return pd.to_numeric(s, errors='coerce').fillna(0)
