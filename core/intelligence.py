from __future__ import annotations
import numpy as np
import pandas as pd
from .metrics import weighted_rate, summary


def merchant_latest(df: pd.DataFrame, month: str) -> pd.DataFrame:
    return df[df["month"] == month].copy()


def build_timeline(df: pd.DataFrame) -> pd.DataFrame:
    keys = ["month", "merchant_id", "merchant_name", "bd", "area", "category", "level"]
    # one row per merchant per month; if duplicates aggregate simple fields
    agg = df.groupby(keys, dropna=False).agg(
        gmv=("gmv","sum"), orders=("orders","sum"), exposure=("exposure","sum"), visit=("visit","sum"), cart=("cart","sum"),
        rate_ev=("rate_ev","mean"), rate_vc=("rate_vc","mean"), rate_co=("rate_co","mean"), rate_eo=("rate_eo","mean"),
        promo_flag=("promo_flag","max"), material_flag=("material_flag","max"), visit_record_flag=("visit_record_flag","max")
    ).reset_index()
    agg = agg.sort_values(["merchant_id","month"])
    agg["gmv_prev"] = agg.groupby("merchant_id")["gmv"].shift(1)
    agg["gmv_mom"] = np.where(agg["gmv_prev"]>0, (agg["gmv"]-agg["gmv_prev"])/agg["gmv_prev"], np.nan)
    agg["orders_prev"] = agg.groupby("merchant_id")["orders"].shift(1)
    agg["orders_mom"] = np.where(agg["orders_prev"]>0, (agg["orders"]-agg["orders_prev"])/agg["orders_prev"], np.nan)
    return agg


def alert_center(df: pd.DataFrame, month: str) -> pd.DataFrame:
    tl = build_timeline(df)
    cur = tl[tl["month"] == month].copy()
    if cur.empty: return cur
    # consecutive decline count
    def decline_streak(g):
        g = g.sort_values("month")
        streak=0; vals=[]
        for _,row in g.iterrows():
            if pd.notna(row["gmv_mom"]) and row["gmv_mom"] < -0.05: streak += 1
            else: streak = 0
            vals.append(streak)
        g["decline_streak"] = vals
        return g
    tl2 = tl.groupby("merchant_id", group_keys=False).apply(decline_streak)
    cur = tl2[tl2["month"] == month].copy()
    cur["priority_score"] = (
        cur["gmv"].rank(pct=True).fillna(0)*35 +
        cur["gmv_mom"].fillna(0).clip(upper=0).abs()*100*0.35 +
        cur["decline_streak"].fillna(0)*15 +
        (1-cur["rate_eo"].rank(pct=True).fillna(0))*15
    ).clip(0,100)
    cur["alert_type"] = np.select(
        [cur["decline_streak"]>=2, cur["gmv_mom"]<-0.15, cur["gmv_mom"]>0.2],
        ["Need Immediate Action", "Warning", "Rising Star"],
        default="Monitor"
    )
    return cur.sort_values("priority_score", ascending=False)


def merchant_health(df: pd.DataFrame) -> pd.Series:
    # rank based 0-100 score within selected dataset
    parts = []
    for col, weight in [("gmv",30),("rate_eo",20),("rate_ev",15),("rate_vc",15),("rate_co",10)]:
        parts.append(df[col].rank(pct=True).fillna(0)*weight)
    parts.append(df["promo_flag"].astype(float)*5)
    parts.append(df["material_flag"].astype(float)*3)
    parts.append(df["visit_record_flag"].astype(float)*2)
    return sum(parts).clip(0,100)


def learning_score(target: pd.Series, candidates: pd.DataFrame) -> pd.Series:
    score = pd.Series(0.0, index=candidates.index)
    score += (candidates["category"].astype(str) == str(target["category"])) * 35
    score += (candidates["level"].astype(str) == str(target["level"])) * 15
    score += (candidates["area"].astype(str) == str(target["area"])) * 10
    # scale similarity: exposure/orders size closeness
    for col, w in [("exposure",15),("orders",10),("gmv",15)]:
        t = float(target.get(col,0) or 0)
        denom = max(t, 1)
        diff = (candidates[col].astype(float)-t).abs()/denom
        score += (1-diff.clip(0,1))*w
    # reward stronger stores
    score += candidates["gmv"].rank(pct=True).fillna(0)*10
    score += candidates["rate_eo"].rank(pct=True).fillna(0)*10
    return score.clip(0,100)


def top_learning_merchants(df: pd.DataFrame, merchant_query: str, topn: int = 5):
    pool = df.copy()
    matches = pool[pool["merchant_name"].astype(str).str.contains(merchant_query, case=False, na=False)]
    if matches.empty:
        return None, pd.DataFrame(), pd.DataFrame()
    target = matches.sort_values("gmv", ascending=False).iloc[0]
    cand = pool[pool["merchant_id"] != target["merchant_id"]].copy()
    # prefer same category, but keep fallback if few
    if (cand["category"].astype(str)==str(target["category"])).sum() >= topn:
        cand = cand[cand["category"].astype(str)==str(target["category"])]
    cand["Learning Score"] = learning_score(target, cand)
    cand["Health Score"] = merchant_health(cand)
    top = cand.sort_values(["Learning Score","gmv"], ascending=False).head(topn)
    gap_metrics = ["gmv","orders","rate_ev","rate_vc","rate_co","rate_eo"]
    gap=[]
    for c in gap_metrics:
        gap.append({"Metric":c, "Your Store":target[c], "Top5 Avg":top[c].mean(), "Gap":target[c]-top[c].mean()})
    return target, top, pd.DataFrame(gap)


def best_practice(df: pd.DataFrame, group_col="category", top_pct=.2) -> pd.DataFrame:
    rows=[]
    for k,g in df.groupby(group_col, dropna=False):
        if len(g)<5: continue
        cutoff = g["gmv"].quantile(1-top_pct)
        top = g[g["gmv"]>=cutoff]
        rows.append({
            group_col:k, "Top Stores":len(top), "Avg GMV":top["gmv"].mean(),
            "Promo Coverage":top["promo_flag"].mean(), "Material Coverage":top["material_flag"].mean(),
            "Visit Record Coverage":top["visit_record_flag"].mean(), "Exposure → Order":top["rate_eo"].mean()
        })
    return pd.DataFrame(rows).sort_values("Avg GMV", ascending=False) if rows else pd.DataFrame()
