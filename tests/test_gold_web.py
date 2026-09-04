"""Gold web page + fragment endpoint tests (htmx architecture).

Service functions are mocked at services.gold.service; no network or DB.
"""
import json

import pytest
from fastapi.testclient import TestClient

import main
import services.gold.service as service


@pytest.fixture()
def client():
    # 不进入上下文管理器，跳过 lifespan（避免 DB/调度器）
    return TestClient(main.app)


def _env(code=0, data=None, stale=False, msg=""):
    return {"code": code, "ts": 1725451200, "stale": stale, "msg": msg, "data": data}


DOMESTIC_DATA = [
    {"symbol": "Au99.99", "name": "Au99.99", "price": 946.0, "change_pct": None,
     "unit": "元/克", "source": "akshare.sge"},
    {"symbol": "Au(T+D)", "name": "Au(T+D)", "price": None, "change_pct": None,
     "unit": "元/克", "source": "missing"},
    {"symbol": "SHAU", "name": "上海金基准价", "price": 954.28, "change_pct": None,
     "unit": "元/克", "source": "akshare.sge-benchmark"},
    {"symbol": "Au9999", "name": "Au9999", "price": None, "change_pct": None,
     "unit": "元/克", "source": "missing"},
]

INTL_DATA = {
    "quotes": [
        {"symbol": "XAU", "name": "伦敦金", "price": 4398.1, "change_pct": -1.68,
         "unit": "美元/盎司", "source": "sina-hf"},
        {"symbol": "GC", "name": "COMEX黄金期货", "price": 4447.3, "change_pct": -2.0,
         "unit": "美元/盎司", "source": "yahoo"},
        {"symbol": "DXY", "name": "美元指数", "price": 99.385, "change_pct": 0.1,
         "unit": "点", "source": "yahoo"},
        {"symbol": "USDCNY", "name": "美元/人民币", "price": 6.7125, "change_pct": None,
         "unit": "汇率", "source": "yahoo"},
    ],
    "premium": {"premium": -3.16, "implied": 949.16,
                "formula": "国内金价 ≈ 国际金价 × USD/CNY ÷ 31.1035 + 境内溢价"},
}

ETF_DATA = [
    {"code": "518880", "name": "华安黄金ETF", "price": 9.164, "change_pct": 0.65,
     "volume": 100, "turnover": 1.2e9, "nav": None, "est_nav": None,
     "fee": 0.006, "scale": 600, "source": "sina"},
    {"code": "518850", "name": "华夏黄金ETF", "price": 9.257, "change_pct": 0.5,
     "volume": 100, "turnover": 5e8, "nav": None, "est_nav": None,
     "fee": 0.002, "scale": 160, "source": "sina"},
    {"code": "518660", "name": "工银黄金ETF", "price": 9.193, "change_pct": -0.3,
     "volume": 100, "turnover": 3e8, "nav": None, "est_nav": None,
     "fee": 0.002, "scale": 50, "source": "sina"},
]

OTC_DATA = [
    {"code": "008702", "name": "华夏黄金ETF联接C", "price": 2.0969, "change_pct": 0.62,
     "volume": None, "turnover": None, "nav": 2.0838, "est_nav": 2.0969,
     "fee": 0.002, "cls": "C", "parent": "518850", "source": "lsjz+etf-estimate"},
    {"code": "000218", "name": "华安黄金ETF联接C", "price": 3.5079, "change_pct": 0.65,
     "volume": None, "turnover": None, "nav": 3.4853, "est_nav": 3.5079,
     "fee": 0.006, "cls": "C", "parent": "518880", "source": "lsjz+etf-estimate"},
    {"code": "008701", "name": "华夏黄金ETF联接A", "price": 2.0985, "change_pct": 0.62,
     "volume": None, "turnover": None, "nav": 2.0854, "est_nav": 2.0985,
     "fee": 0.002, "cls": "A", "parent": "518850", "source": "lsjz+etf-estimate"},
]


@pytest.fixture()
def happy_paths(monkeypatch):
    monkeypatch.setattr(service, "get_domestic", lambda: _env(data=DOMESTIC_DATA))
    monkeypatch.setattr(service, "get_international", lambda: _env(data=INTL_DATA))
    monkeypatch.setattr(service, "get_otc", lambda: _env(data=OTC_DATA))
    monkeypatch.setattr(service, "get_lowfee", lambda: _env(data=ETF_DATA))
    monkeypatch.setattr(service, "get_band", lambda: _env(data=ETF_DATA))
    monkeypatch.setattr(service, "get_main", lambda: _env(data=ETF_DATA))


def test_page_renders_shell(client):
    resp = client.get("/web/gold")
    assert resp.status_code == 200
    html = resp.text
    assert "黄金行情追踪器" in html
    assert "刷新全部" in html
    assert "/web/gold/fragments/all" in html
    assert "/static/vendor/htmx.js" in html
    assert "/static/vendor/alpine.js" in html
    assert "setInterval" not in html


def test_static_vendor_served(client):
    assert client.get("/static/vendor/htmx.js").status_code == 200
    assert client.get("/static/vendor/alpine.js").status_code == 200


def test_domestic_fragment(client, happy_paths):
    resp = client.get("/web/gold/fragments/domestic")
    assert resp.status_code == 200
    html = resp.text
    assert "946.00" in html
    assert "mod-domestic-body" in html and "hx-swap-oob" in html
    assert 'id="header-ts"' in html


def test_domestic_fragment_placeholder_for_missing(client, happy_paths):
    html = client.get("/web/gold/fragments/domestic").text
    assert "—" in html  # Au(T+D)/Au9999 缺数据占位


def test_international_fragment_premium_strip(client, happy_paths):
    resp = client.get("/web/gold/fragments/international")
    html = resp.text
    assert "沪伦溢价" in html
    assert "-3.16" in html
    assert "premium-strip" in html
    # 跌绿涨红
    assert "text-down" in html


def test_etf_fragment_columns_and_recommend(client, happy_paths):
    html = client.get("/web/gold/fragments/etf/main").text
    assert "华夏黄金ETF" in html
    assert "推荐" in html
    assert "1.60亿" in html or "160亿" in html
    assert "0.20%" in html
    assert "tab-body-main" in html


def test_etf_fragment_unknown_tab_404(client):
    assert client.get("/web/gold/fragments/etf/nope").status_code == 404


def test_otc_fragment_c_first_a_folded(client, happy_paths):
    html = client.get("/web/gold/fragments/otc").text
    assert "华夏黄金ETF联接C" in html
    assert "<details" in html and "展开 A 类份额" in html
    assert "2.0969" in html


def test_stale_envelope_renders_badge_and_event(client, monkeypatch):
    monkeypatch.setattr(service, "get_domestic",
                        lambda: _env(code=2, data=DOMESTIC_DATA, stale=True, msg="上游超时，已返回上次缓存"))
    resp = client.get("/web/gold/fragments/domestic")
    assert resp.status_code == 200
    assert "缓存" in resp.text
    assert "gold-stale" in resp.headers["HX-Trigger"]


def test_hard_failure_returns_204_and_keeps_old_data(client, monkeypatch):
    monkeypatch.setattr(service, "get_domestic",
                        lambda: _env(code=1, data=[], msg="数据获取失败，请稍后重试"))
    resp = client.get("/web/gold/fragments/domestic")
    assert resp.status_code == 204
    assert resp.text == "" or resp.content == b""
    trigger = json.loads(resp.headers["HX-Trigger"])
    assert "gold-error" in trigger


def test_refresh_all_oob_swaps_all_modules(client, happy_paths):
    resp = client.get("/web/gold/fragments/all")
    assert resp.status_code == 200
    html = resp.text
    for target in ("mod-domestic-body", "mod-intl-body", "premium-strip",
                   "tab-body-otc", "tab-body-lowfee", "tab-body-band", "tab-body-main"):
        assert target in html
    assert "hx-swap-oob" in html


def test_refresh_all_partial_failure_keeps_others(client, monkeypatch):
    fail = lambda: _env(code=1, data=[], msg="失败")  # noqa: E731
    monkeypatch.setattr(service, "get_domestic", fail)  # 国内现货失败 → 旧数据保留
    monkeypatch.setattr(service, "get_international", lambda: _env(data=INTL_DATA))
    monkeypatch.setattr(service, "get_otc", lambda: _env(data=OTC_DATA))
    monkeypatch.setattr(service, "get_lowfee", lambda: _env(data=ETF_DATA))
    monkeypatch.setattr(service, "get_band", lambda: _env(data=ETF_DATA))
    monkeypatch.setattr(service, "get_main", lambda: _env(data=ETF_DATA))
    resp = client.get("/web/gold/fragments/all")
    assert resp.status_code == 200
    assert "mod-domestic-body" not in resp.text  # 失败模块不输出，旧数据保留
    assert "premium-strip" in resp.text


def test_refresh_all_total_failure_204(client, monkeypatch):
    fail = lambda: _env(code=1, data=[], msg="失败")  # noqa: E731
    monkeypatch.setattr(service, "get_domestic", fail)
    monkeypatch.setattr(service, "get_international", fail)
    monkeypatch.setattr(service, "get_otc", fail)
    monkeypatch.setattr(service, "get_lowfee", fail)
    monkeypatch.setattr(service, "get_band", fail)
    monkeypatch.setattr(service, "get_main", fail)
    resp = client.get("/web/gold/fragments/all")
    assert resp.status_code == 204
    assert "gold-error" in resp.headers["HX-Trigger"]
