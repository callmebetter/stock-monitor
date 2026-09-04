"""Catalog integrity tests: universe locked to PRD §2, tabs per PRD §4.2."""
from services.gold.catalog import (
    DOMESTIC_SYMBOLS,
    ETF_BY_CODE,
    ETF_UNIVERSE,
    GRAMS_PER_OUNCE,
    INTL_SYMBOLS,
    OTC_BY_CODE,
    OTC_UNIVERSE,
    TABS,
)


def test_etf_universe_locked_to_seven():
    assert len(ETF_UNIVERSE) == 7
    expected = {"518880", "159937", "159934", "518850", "518660", "518800", "159830"}
    assert set(ETF_BY_CODE) == expected


def test_otc_universe_locked_to_eight():
    assert len(OTC_UNIVERSE) == 8
    expected = {
        "000217", "000218", "002610", "002611",
        "000307", "000308", "008701", "008702",
    }
    assert set(OTC_BY_CODE) == expected


def test_otc_parent_codes_are_etf_codes():
    for fund in OTC_UNIVERSE:
        assert fund["parent"] in ETF_BY_CODE


def test_tab_membership_per_prd():
    assert set(TABS["otc"]["codes"]) == set(OTC_BY_CODE)
    assert TABS["lowfee"]["codes"] == ["518850", "518660", "159830"]
    assert TABS["band"]["codes"] == ["159937", "518880", "159934", "518800"]
    assert TABS["main"]["codes"] == ["518880", "159937", "518800", "159934", "518850", "518660", "159830"]


def test_otc_tab_order_c_class_first_low_fee_top():
    # PRD §4.2: 华夏C → 华安C → 博时C → 易方达C 置顶，A 类折叠
    assert TABS["otc"]["codes"][:4] == ["008702", "000218", "002611", "000308"]


def test_lowfee_tab_sorted_by_fee_then_scale():
    fees = [ETF_BY_CODE[c]["fee"] for c in TABS["lowfee"]["codes"]]
    assert fees == sorted(fees)


def test_band_tab_order_locked_per_prd():
    # PRD §4.2 显式锁定顺序；与其成交额约数（518880 10~15 > 159937 8~10）存在
    # 自相矛盾，以显式顺序为准（159937 置顶）。
    assert TABS["band"]["codes"] == ["159937", "518880", "159934", "518800"]


def test_main_tab_sorted_by_scale_desc():
    scales = [ETF_BY_CODE[c]["scale_b"] for c in TABS["main"]["codes"]]
    assert scales == sorted(scales, reverse=True)
    assert TABS["main"]["codes"][0] == "518880"


def test_symbol_orders_and_ounce_constant():
    assert DOMESTIC_SYMBOLS == ["Au99.99", "Au(T+D)", "SHAU", "Au9999"]
    assert INTL_SYMBOLS == ["XAU", "GC", "DXY", "USDCNY"]
    assert GRAMS_PER_OUNCE == 31.1035
