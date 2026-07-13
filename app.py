from __future__ import annotations
import io
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
from core.loader import read_excel_file, infer_month
from core.metrics import standardize, summary, group_summary, weighted_rate
from core.intelligence import alert_center, merchant_health, top_learning_merchants, best_practice, build_timeline

st.set_page_config(page_title="Sydney Growth Intelligence", layout="wide", page_icon="📈")
st.title("📈 Sydney Growth Intelligence Platform")
st.caption("Multi-month BD growth intelligence: Learn, Fix, Grow. · Build v1.2")

with st.sidebar:
    st.header("1) Upload reports")
    files = st.file_uploader("Upload one or multiple monthly Excel files", type=["xlsx", "xls"], accept_multiple_files=True)
    password = st.text_input("Excel password (if encrypted)", type="password")
    st.divider()
    st.header("2) Filters")

@st.cache_data(show_spinner=False)
def load_all(file_blobs, password):
    frames=[]
    raw_info=[]
    for name, data in file_blobs:
        class F:
            def __init__(self, name, data): self.name=name; self._data=data
            def read(self): return self._data
        f=F(name,data)
        raw=read_excel_file(f, password)
        month=infer_month(raw, name)
        std=standardize(raw, month)
        frames.append(std)
        raw_info.append({"file":name,"month":month,"rows":len(std),"columns":len(raw.columns)})
    return pd.concat(frames, ignore_index=True), pd.DataFrame(raw_info)

if not files:
    st.info("Upload monthly Excel files to start. You can upload multiple months together; the app will infer the reporting month from the file or columns.")
    st.stop()

try:
    file_blobs=[(f.name, f.getvalue()) for f in files]
    df, file_info = load_all(file_blobs, password)
except Exception as e:
    st.error(f"Failed to read files: {e}")
    st.stop()

months = sorted(df["month"].astype(str).unique())
with st.sidebar:
    selected_month = st.selectbox("Reporting month", months, index=len(months)-1)
    all_bds = sorted(df["bd"].dropna().astype(str).unique())
    selected_bd = st.selectbox("BD / Owner", ["All"] + all_bds, index=0)
    levels = sorted(df["level"].dropna().astype(str).unique())
    selected_levels = st.multiselect("Merchant level", levels, default=levels)
    areas = sorted(df["area"].dropna().astype(str).unique())
    selected_areas = st.multiselect("Area", areas, default=[])
    cats = sorted(df["category"].dropna().astype(str).unique())
    selected_cats = st.multiselect("Category", cats, default=[])

cur = df[df["month"].astype(str)==selected_month].copy()
if selected_bd != "All": cur = cur[cur["bd"].astype(str)==selected_bd]
if selected_levels: cur = cur[cur["level"].astype(str).isin(selected_levels)]
if selected_areas: cur = cur[cur["area"].astype(str).isin(selected_areas)]
if selected_cats: cur = cur[cur["category"].astype(str).isin(selected_cats)]
cur["Health Score"] = merchant_health(cur) if not cur.empty else []

# Formatting helpers
def money(x): return f"${x:,.0f}"
def pct(x): return f"{x*100:.2f}%"

def show_metric_row(s: dict):
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("GMV", money(s["GMV"]))
    c2.metric("Orders", f"{s['Orders']:,.0f}")
    c3.metric("Merchants", f"{s['Merchants']:,.0f}")
    c4.metric("GMV / Store", money(s["GMV / Store"]))
    c5.metric("Exposure → Order", pct(s["Exposure → Order"]))

st.subheader(f"📅 Reporting Month: {selected_month}")
with st.expander("Loaded files"):
    st.dataframe(file_info, use_container_width=True)

if cur.empty:
    st.warning("No merchants match the selected filters.")
    st.stop()

# Tabs
tabs = st.tabs(["🏠 Executive", "🚨 Alerts", "🏆 Learn From Best", "🔍 Merchant AI Coach", "📊 BD / Area / Category", "📈 Trends", "📘 Metric Dictionary"])

with tabs[0]:
    st.subheader("Executive Summary")
    s = summary(cur)
    show_metric_row(s)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Exposure → Visit", pct(s["Exposure → Visit"]))
    c2.metric("Visit → Cart", pct(s["Visit → Cart"]))
    c3.metric("Cart → Order", pct(s["Cart → Order"]))
    c4.metric("Promo Rate", pct(s["Promo Rate"]))
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        top = cur.sort_values("gmv", ascending=False).head(15)
        fig = px.bar(top.sort_values("gmv"), x="gmv", y="merchant_name", orientation="h", title="Top merchants by GMV", labels={"gmv":"GMV","merchant_name":"Merchant"})
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        level_board = group_summary(cur, "level")
        if not level_board.empty:
            fig = px.bar(level_board, x="level", y="GMV", title="GMV by merchant level", labels={"level":"Merchant level"})
            st.plotly_chart(fig, use_container_width=True)
    st.markdown("### Merchant data")
    display_cols=["merchant_name","bd","area","category","level","gmv","orders","rate_ev","rate_vc","rate_co","rate_eo","Health Score"]
    st.dataframe(cur[display_cols].sort_values("gmv", ascending=False), use_container_width=True)

with tabs[1]:
    st.subheader("Alert Center: stores needing attention or worth learning")
    alerts = alert_center(df, selected_month)
    if selected_bd != "All": alerts = alerts[alerts["bd"].astype(str)==selected_bd]
    if selected_levels: alerts = alerts[alerts["level"].astype(str).isin(selected_levels)]
    st.markdown("**Need Immediate Action** = consecutive or sharp GMV decline. **Rising Star** = strong month-on-month growth.")
    cols=["alert_type","priority_score","merchant_name","bd","area","category","level","gmv","gmv_mom","orders","rate_eo","decline_streak"]
    st.dataframe(alerts[cols].head(100), use_container_width=True)
    col1,col2 = st.columns(2)
    with col1:
        top_risk = alerts[alerts["alert_type"].isin(["Need Immediate Action","Warning"])].head(15)
        if not top_risk.empty:
            fig=px.bar(top_risk.sort_values("priority_score"), x="priority_score", y="merchant_name", orientation="h", title="Top priority stores to fix")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        rising = alerts[alerts["alert_type"]=="Rising Star"].sort_values("gmv_mom", ascending=False).head(15)
        if not rising.empty:
            fig=px.bar(rising.sort_values("gmv_mom"), x="gmv_mom", y="merchant_name", orientation="h", title="Rising stars worth learning")
            st.plotly_chart(fig, use_container_width=True)

with tabs[2]:
    st.subheader("Learn From Best")
    st.write("Find high-performing stores and the common practices worth copying.")
    rank_basis = st.selectbox("Rank learning merchants by", ["Health Score", "gmv", "rate_eo", "orders"], index=0)
    top_learning = cur.sort_values(rank_basis, ascending=False).head(30)
    st.dataframe(top_learning[["merchant_name","bd","area","category","level","gmv","orders","rate_eo","promo_flag","material_flag","visit_record_flag","Health Score"]], use_container_width=True)
    col1,col2=st.columns(2)
    with col1:
        fig=px.scatter(cur, x="rate_eo", y="gmv", size="orders", color="level", hover_name="merchant_name", title="GMV vs Exposure → Order")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        bp_col=st.selectbox("Best practice by", ["category","area","level"])
        bp=best_practice(cur, bp_col)
        st.dataframe(bp, use_container_width=True)

with tabs[3]:
    st.subheader("Merchant AI Coach")
    q = st.text_input("Input your merchant name", placeholder="e.g. 东北咱家菜")
    if q:
        target, top5, gap = top_learning_merchants(cur, q, 5)
        if target is None:
            st.warning("No matching merchant found under current filters. Try clearing filters or using part of the merchant name.")
        else:
            st.markdown(f"### Target: {target['merchant_name']} · {target['category']} · {target['area']} · {target['level']}")
            c1,c2,c3,c4=st.columns(4)
            c1.metric("GMV", money(target["gmv"]))
            c2.metric("Orders", f"{target['orders']:,.0f}")
            c3.metric("Exposure → Order", pct(target["rate_eo"]))
            c4.metric("Health Score", f"{float(merchant_health(pd.DataFrame([target])) .iloc[0]):.0f}")
            st.markdown("#### Top 5 merchants to learn from")
            st.dataframe(top5[["merchant_name","bd","area","category","level","gmv","orders","rate_eo","Learning Score","Health Score"]], use_container_width=True)
            st.markdown("#### Gap analysis: your store vs Top5 average")
            pretty_gap=gap.copy()
            st.dataframe(pretty_gap, use_container_width=True)
            rate_rows=[]
            for label,col in [("Exposure → Visit","rate_ev"),("Visit → Cart","rate_vc"),("Cart → Order","rate_co"),("Exposure → Order","rate_eo")]:
                rate_rows.append({"Metric":label,"Your store":target[col],"Top5 avg":top5[col].mean()})
            rate_df=pd.DataFrame(rate_rows)
            fig=px.bar(rate_df, x="Metric", y=["Your store","Top5 avg"], barmode="group", title="Conversion comparison")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("#### Suggested action plan")
            actions=[]
            if target["rate_vc"] < top5["rate_vc"].mean(): actions.append("Improve menu structure and add stronger bundles: your Visit → Cart is below the learning group.")
            if target["rate_co"] < top5["rate_co"].mean(): actions.append("Add a stronger checkout incentive such as delivery voucher, threshold discount, or new customer offer.")
            if not bool(target["promo_flag"]): actions.append("Set up promotion coverage. Top learning stores are more likely to have active promotions.")
            if not bool(target["material_flag"]): actions.append("Add official material / poster support to improve store trust and click-through.")
            if not actions: actions.append("Your store is close to the learning group. Focus on maintaining activity and testing one small bundle/promo improvement.")
            for i,a in enumerate(actions,1): st.write(f"{i}. {a}")
            brief = f"Merchant Visit Brief\nMerchant: {target['merchant_name']}\nMonth: {selected_month}\nGMV: {money(target['gmv'])}\nOrders: {target['orders']:,.0f}\nRecommended learning stores: {', '.join(top5['merchant_name'].astype(str).head(5))}\nActions:\n" + "\n".join([f"- {a}" for a in actions])
            st.download_button("Download visit brief", brief, file_name=f"visit_brief_{target['merchant_name']}.txt")

with tabs[4]:
    st.subheader("BD / Area / Category Intelligence")
    view = st.radio("Group by", ["bd","area","category","level"], horizontal=True)
    board = group_summary(cur, view)
    st.dataframe(board, use_container_width=True)
    if not board.empty:
        fig=px.bar(board.head(20).sort_values("GMV"), x="GMV", y=view, orientation="h", title=f"Top {view} by GMV")
        st.plotly_chart(fig, use_container_width=True)

with tabs[5]:
    st.subheader("Monthly Trends")
    tl = build_timeline(df)
    if selected_bd != "All": tl = tl[tl["bd"].astype(str)==selected_bd]
    trend = tl.groupby("month").agg(GMV=("gmv","sum"), Orders=("orders","sum"), Merchants=("merchant_id","nunique"), Avg_EO=("rate_eo","mean")).reset_index()
    col1,col2=st.columns(2)
    with col1:
        fig=px.line(trend, x="month", y="GMV", markers=True, title="GMV trend")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig=px.line(trend, x="month", y="Orders", markers=True, title="Orders trend")
        st.plotly_chart(fig, use_container_width=True)
    merchant_for_timeline = st.text_input("Merchant timeline search", placeholder="Enter merchant name")
    if merchant_for_timeline:
        mt = tl[tl["merchant_name"].astype(str).str.contains(merchant_for_timeline, case=False, na=False)]
        if not mt.empty:
            chosen = st.selectbox("Choose merchant", mt["merchant_name"].unique())
            one = mt[mt["merchant_name"]==chosen]
            fig=px.line(one, x="month", y="gmv", markers=True, title=f"GMV timeline · {chosen}")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(one[["month","merchant_name","bd","area","category","gmv","gmv_mom","orders","rate_eo"]], use_container_width=True)

with tabs[6]:
    st.subheader("Metric Dictionary")
    md = pd.DataFrame([
        ["GMV", "Sum of merchant GMV in the selected month/filter.", "Sum", "Higher is better, final business result."],
        ["Orders", "Sum of order count. Uses the best detected order count field, not delivery type.", "Sum", "Volume result."],
        ["Exposure → Visit", "Weighted conversion from exposure to store visit.", "Σ(rate × exposure) / Σexposure", "Measures whether listing/title/image attracts users."],
        ["Visit → Cart", "Weighted conversion from visit to add-to-cart.", "Σ(rate × visit) / Σvisit", "Measures menu attractiveness and offer design."],
        ["Cart → Order", "Weighted conversion from cart to order.", "Σ(rate × cart) / Σcart", "Measures checkout incentives, price, delivery fee and friction."],
        ["Exposure → Order", "Weighted total funnel conversion from exposure to order.", "Σ(rate × exposure) / Σexposure", "Best single conversion metric for store efficiency."],
        ["Promo Rate", "Share of selected merchants with any detected promotion/campaign field value.", "Promoted stores / stores", "BD controllable lever."],
        ["Material Rate", "Share of merchants with detected material/poster support.", "Stores with material / stores", "Improves trust and click-through."],
        ["Health Score", "Composite 0–100 score based on GMV, conversion, promotion, material and visit record.", "Rank-weighted score", "Quickly separates strong stores from stores needing work."],
        ["Priority Score", "Risk score for immediate action based on GMV scale, decline, streak and weak conversion.", "Composite score", "Ranks stores that need timely handling."],
        ["Learning Score", "Similarity plus performance score for finding stores worth learning from.", "Composite score", "Finds comparable stores to copy, not just biggest stores."],
    ], columns=["Metric","Definition","Formula / Method","Why it matters"])
    st.dataframe(md, use_container_width=True)

# Download full current data
csv = cur.to_csv(index=False).encode("utf-8-sig")
st.sidebar.download_button("Download filtered merchant data", csv, file_name=f"filtered_merchants_{selected_month}.csv", mime="text/csv")
