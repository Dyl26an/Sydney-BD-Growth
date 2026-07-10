from __future__ import annotations
from typing import Optional
import pandas as pd

CANDIDATES = {
    "merchant_name": ["商户名称", "店铺名称", "门店名称", "merchant name", "restaurant name", "shop name", "name"],
    "merchant_id": ["商户id", "商户ID", "店铺id", "门店id", "merchant id", "shop id"],
    "bd_name": ["bd姓名", "BD姓名", "bd name", "BD Name", "负责人姓名", "负责人", "owner", "AM姓名"],
    "bd_id": ["bd工号", "BD工号", "bd id", "BD ID", "员工工号", "owner id"],
    "area": ["商圈", "区域", "area", "suburb", "zone", "城市商圈"],
    "category": ["品类", "一级品类", "二级品类", "category", "cuisine", "菜系"],
    "level": ["商户等级", "店铺等级", "商家等级", "merchant level", "level", "等级"],
    "gmv": ["GMV", "gmv", "交易额", "营业额", "实付gmv", "支付金额"],
    "orders": ["订单数_排除mm的均单", "订单数", "有效订单数", "orders", "order count", "paid orders"],
    "exposure": ["平均曝光人数", "曝光人数", "曝光", "exposure users", "exposure", "impressions"],
    "visit": ["平均进店人数", "进店人数", "进店", "visit users", "visits", "store visits"],
    "cart": ["平均加购人数", "加购人数", "加购", "cart users", "add to cart", "cart"],
    "rate_ev": ["曝光进店转化率", "曝光-进店转化率", "exposure visit", "exposure→visit"],
    "rate_vc": ["进店加购转化率", "进店-加购转化率", "visit cart", "visit→cart"],
    "rate_co": ["加购下单转化率", "加购-下单转化率", "cart order", "cart→order"],
    "rate_eo": ["曝光下单转化率", "曝光-下单转化率", "exposure order", "exposure→order"],
    "promo": ["活动", "促销", "折扣", "优惠券", "promo", "promotion", "campaign"],
    "material": ["物料", "海报", "material", "poster"],
    "visit_record": ["拜访", "拜访记录", "visit record", "visited"],
}


def find_col(df: pd.DataFrame, key: str) -> Optional[str]:
    cols = list(df.columns)
    low = {str(c).lower().strip(): c for c in cols}
    for cand in CANDIDATES.get(key, []):
        if cand.lower() in low:
            return low[cand.lower()]
    for cand in CANDIDATES.get(key, []):
        cc = cand.lower()
        for c in cols:
            if cc in str(c).lower():
                # avoid false order delivery type
                if key == "orders" and any(x in str(c).lower() for x in ["类型", "type", "配送"]):
                    continue
                return c
    return None


def columns_map(df: pd.DataFrame) -> dict:
    return {k: find_col(df, k) for k in CANDIDATES.keys()}
