from __future__ import annotations
import numpy as np
import pandas as pd
from .loader import clean_numeric
from .schema import columns_map


def pct_to_ratio(s: pd.Series) -> pd.Series:
    x = clean_numeric(s)
    # If values look like 15 rather than 0.15, convert to ratio
    if x.max() > 1.5:
        x = x / 100.0
    return x.clip(lower=0)


def has_value(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(dtype=bool)
    text = s.fillna("").astype(str).str.strip().str.lower()
    return ~(text.isin(["", "0", "no", "false", "nan", "none", "否", "无", "未配置"]))


def standardize(df: pd.DataFrame, month: str) -> pd.DataFrame:
    m = columns_map(df)
    out = pd.DataFrame(index=df.index)
    out["month"] = month
    out["merchant_name"] = df[m["merchant_name"]].astype(str) if m["merchant_name"] else "Unknown"
    out["merchant_id"] = df[m["merchant_id"]].astype(str) if m["merchant_id"] else out["merchant_name"]
    bd_name = df[m["bd_name"]].astype(str) if m["bd_name"] else None
    bd_id = df[m["bd_id"]].astype(str) if m["bd_id"] else None
    out["bd"] = bd_name.where(bd_name.notna() & (bd_name.str.strip()!=""), bd_id) if bd_name is not None else (bd_id if bd_id is not None else "Unknown")
    out["area"] = df[m["area"]].astype(str) if m["area"] else "Unknown"
    out["category"] = df[m["category"]].astype(str) if m["category"] else "Unknown"
    out["level"] = df[m["level"]].astype(str) if m["level"] else "Auto"
    for key in ["gmv", "orders", "exposure", "visit", "cart"]:
        out[key] = clean_numeric(df[m[key]]) if m[key] else 0
    # rates: prefer official rate fields, weighted later by denominator
    for key in ["rate_ev", "rate_vc", "rate_co", "rate_eo"]:
        out[key] = pct_to_ratio(df[m[key]]) if m[key] else np.nan
    # fallbacks only when official rate missing and same-period counts are usable
    out["rate_ev"] = out["rate_ev"].fillna(np.where(out["exposure"]>0, out["visit"]/out["exposure"], 0))
    out["rate_vc"] = out["rate_vc"].fillna(np.where(out["visit"]>0, out["cart"]/out["visit"], 0))
    # order is often monthly cumulative while cart is average users; do not fallback aggressively
    out["rate_co"] = out["rate_co"].fillna(0)
    out["rate_eo"] = out["rate_eo"].fillna(0)
    out["promo_flag"] = has_value(df[m["promo"]]) if m["promo"] else False
    out["material_flag"] = has_value(df[m["material"]]) if m["material"] else False
    out["visit_record_flag"] = has_value(df[m["visit_record"]]) if m["visit_record"] else False
    # auto level if missing
    if m["level"] is None or out["level"].eq("Auto").all():
        q = out["gmv"].quantile([.25,.5,.75]).to_dict()
        out["level"] = pd.cut(out["gmv"], bins=[-1, q.get(.25,0), q.get(.5,0), q.get(.75,0), float('inf')], labels=["D", "C", "B", "A"]).astype(str)
    return out


def weighted_rate(df: pd.DataFrame, rate_col: str, weight_col: str) -> float:
    w = df[weight_col].fillna(0).astype(float)
    r = df[rate_col].fillna(0).astype(float)
    return float((r*w).sum()/w.sum()) if w.sum() > 0 else 0.0


def summary(df: pd.DataFrame) -> dict:
    stores = df["merchant_id"].nunique()
    return {
        "Merchants": stores,
        "GMV": float(df["gmv"].sum()),
        "Orders": float(df["orders"].sum()),
        "GMV / Store": float(df["gmv"].sum()/stores) if stores else 0,
        "Exposure → Visit": weighted_rate(df, "rate_ev", "exposure"),
        "Visit → Cart": weighted_rate(df, "rate_vc", "visit"),
        "Cart → Order": weighted_rate(df, "rate_co", "cart"),
        "Exposure → Order": weighted_rate(df, "rate_eo", "exposure"),
        "Promo Rate": float(df["promo_flag"].mean()) if len(df) else 0,
        "Material Rate": float(df["material_flag"].mean()) if len(df) else 0,
        "Visit Record Rate": float(df["visit_record_flag"].mean()) if len(df) else 0,
    }


def group_summary(df: pd.DataFrame, by: str) -> pd.DataFrame:
    rows=[]
    for k,g in df.groupby(by, dropna=False):
        s=summary(g); s[by]=k; rows.append(s)
    res=pd.DataFrame(rows)
    if not res.empty:
        res=res.sort_values("GMV", ascending=False).reset_index(drop=True)
        res.insert(0,"Rank", range(1,len(res)+1))
    return res


def latest_month(df: pd.DataFrame) -> str:
    vals = sorted(df["month"].dropna().astype(str).unique())
    return vals[-1] if vals else ""
