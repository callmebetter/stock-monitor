"""Locked underlying universe + tab mapping (PRD §2 / §4).

Strict scope: 7 on-market ETFs + 8 OTC share codes. Nothing may be added
or removed without a PRD revision.
"""
import logging

logger = logging.getLogger(__name__)

# 场内实物黄金 ETF（7 只），按 PRD §2.1 锁定。
# scale_b / turnover_b 为文档记载的约数，仅用于排序与展示，不参与实时计算。
ETF_UNIVERSE = [
    {"code": "518880", "name": "华安黄金ETF", "exchange": "沪", "secid": "1.518880", "fee": 0.0060, "scale_b": 600, "turnover_b": 12.5, "note": "规模最大、流动性最强、支持两融"},
    {"code": "159937", "name": "博时黄金ETF", "exchange": "深", "secid": "0.159937", "fee": 0.0060, "scale_b": 260, "turnover_b": 9.0, "note": "深市龙头、交易活跃、适合波段"},
    {"code": "159934", "name": "易方达黄金ETF", "exchange": "深", "secid": "0.159934", "fee": 0.0060, "scale_b": 160, "turnover_b": 6.0, "note": "跟踪精度高、规模稳健"},
    {"code": "518850", "name": "华夏黄金ETF", "exchange": "沪", "secid": "1.518850", "fee": 0.0020, "scale_b": 160, "turnover_b": 6.0, "note": "费率最低、成本最优"},
    {"code": "518660", "name": "工银黄金ETF", "exchange": "沪", "secid": "1.518660", "fee": 0.0020, "scale_b": 50, "turnover_b": 3.0, "note": "费率最低、银行系、跟踪误差小"},
    {"code": "518800", "name": "国泰黄金ETF", "exchange": "沪", "secid": "1.518800", "fee": 0.0060, "scale_b": 180, "turnover_b": 4.0, "note": "规模中等、波动平稳"},
    {"code": "159830", "name": "上海金ETF", "exchange": "深", "secid": "0.159830", "fee": 0.0030, "scale_b": 20, "turnover_b": 1.5, "note": "费率适中、跟踪上海金基准"},
]

# 场外联接基金（4 组 / 8 个份额代码），按 PRD §2.2 锁定。
# NOTE: PRD §4.2 将易方达 C 类误写为 002963，以 §2.2 的 000308 为准。
OTC_UNIVERSE = [
    {"code": "000217", "name": "华安黄金ETF联接A", "parent": "518880", "fee": 0.0060, "cls": "A"},
    {"code": "000218", "name": "华安黄金ETF联接C", "parent": "518880", "fee": 0.0060, "cls": "C"},
    {"code": "002610", "name": "博时黄金ETF联接A", "parent": "159937", "fee": 0.0060, "cls": "A"},
    {"code": "002611", "name": "博时黄金ETF联接C", "parent": "159937", "fee": 0.0060, "cls": "C"},
    {"code": "000307", "name": "易方达黄金ETF联接A", "parent": "159934", "fee": 0.0060, "cls": "A"},
    {"code": "000308", "name": "易方达黄金ETF联接C", "parent": "159934", "fee": 0.0060, "cls": "C"},
    {"code": "008701", "name": "华夏黄金ETF联接A", "parent": "518850", "fee": 0.0020, "cls": "A"},
    {"code": "008702", "name": "华夏黄金ETF联接C", "parent": "518850", "fee": 0.0020, "cls": "C"},
]

ETF_BY_CODE = {e["code"]: e for e in ETF_UNIVERSE}
OTC_BY_CODE = {f["code"]: f for f in OTC_UNIVERSE}

# Tab 分类与排序（PRD §4.2）
TABS = {
    # 低费率优先 → C 类置顶：华夏C → 华安C → 博时C → 易方达C，A 类折叠展示
    "otc": {"codes": ["008702", "000218", "002611", "000308", "008701", "000217", "002610", "000307"]},
    # 费率升序 → 规模降序
    "lowfee": {"codes": ["518850", "518660", "159830"]},
    # 日均成交额降序
    "band": {"codes": ["159937", "518880", "159934", "518800"]},
    # 规模降序（518880 置顶）
    "main": {"codes": ["518880", "159937", "518800", "159934", "518850", "518660", "159830"]},
}

# 国内现货 4 指标（PRD §6.1）与国际 4 指标（PRD §6.2）的展示顺序
DOMESTIC_SYMBOLS = ["Au99.99", "Au(T+D)", "SHAU", "Au9999"]
INTL_SYMBOLS = ["XAU", "GC", "DXY", "USDCNY"]

# 1 金衡盎司 = 31.1035 克（PRD §6.3 换算公式用）
GRAMS_PER_OUNCE = 31.1035


def _validate_catalog() -> None:
    assert len(ETF_UNIVERSE) == 7, "ETF universe must contain exactly 7 symbols"
    assert len(OTC_UNIVERSE) == 8, "OTC universe must contain exactly 8 share codes"
    assert len(ETF_BY_CODE) == 7 and len(OTC_BY_CODE) == 8, "duplicate codes in catalog"
    for tab, spec in TABS.items():
        unknown = [c for c in spec["codes"] if c not in ETF_BY_CODE and c not in OTC_BY_CODE]
        if unknown:
            raise ValueError(f"tab {tab} references unknown codes: {unknown}")


_validate_catalog()
