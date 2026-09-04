"""K线服务层与路由测试：归一化 / upsert 语句 / 信封降级 / 参数校验.

全部 mock，无网络与 DB 访问（MySQL 不可用环境下照常运行）。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import mysql

import services.gold.kline as kline
from main import app
from services.gold.cache import GoldCache
from services.gold.clients.kline_client import normalize, parse_day

RAW_VALID = [  # 上游原样（新→旧）
    {"day": "2026/09/07", "open": "964.99", "high": "967.0", "low": "940.0",
     "close": "957.31", "volume": 18674, "change": "-7.69", "amplitude": "27.0"},
    {"day": "2026/09/04", "open": "958.0", "high": "967.5", "low": "955.0",
     "close": "965.0", "volume": 17382, "change": "5.31", "amplitude": "13.0"},
]
BARS = [  # 旧→新（图表行序）
    ["2026-09-04", 958.0, 965.0, 955.0, 967.5, 5.31, 13.0, 17382],
    ["2026-09-07", 964.99, 957.31, 940.0, 967.0, -7.69, 27.0, 18674],
]


@pytest.fixture(autouse=True)
def fresh_caches(monkeypatch):
    monkeypatch.setattr(kline, "_sync_gate", GoldCache(ttl=60))
    monkeypatch.setattr(kline, "_upstream", GoldCache(ttl=30))
    monkeypatch.setattr(kline, "_last_fail_ts", 0.0)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


# ---------- 客户端归一化 ----------

def test_parse_day():
    from datetime import date

    assert parse_day("2026/09/07") == date(2026, 9, 7)
    assert parse_day("bad") is None
    assert parse_day(None) is None


def test_normalize_filters_invalid():
    rows = normalize(RAW_VALID + [
        {"day": "bad-date", "open": "1", "close": "1"},
        {"day": "2026/09/03", "open": "x", "close": None},
    ])
    assert [r["trade_date"].isoformat() for r in rows] == ["2026-09-07", "2026-09-04"]
    assert rows[0]["close"] == pytest.approx(957.31)
    assert rows[0]["volume"] == 18674


# ---------- upsert 语句（无需真实 DB，直接编译 SQL 验证） ----------

def test_insert_stmt_has_upsert():
    from datetime import date

    stmt = kline._insert_stmt([{"trade_date": date(2026, 9, 7), "open": 1.0,
                                "high": 2.0, "low": 0.5, "close": 1.5,
                                "change": 0.1, "amplitude": 10.0, "volume": 100}])
    sql = str(stmt.compile(dialect=mysql.dialect()))
    assert "INSERT INTO gold_kline_daily" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "close = VALUES(close)" in sql


# ---------- get_kline 信封与降级链 ----------

def test_get_kline_db_ok(monkeypatch):
    monkeypatch.setattr(kline, "_ensure_fresh", lambda: None)
    monkeypatch.setattr(kline, "_read_db", lambda days: BARS[-days:])
    res = kline.get_kline(2)
    assert res["code"] == 0 and res["stale"] is False
    assert res["data"]["columns"] == kline.COLUMNS
    assert res["data"]["bars"] == BARS


def test_get_kline_db_down_reads_upstream(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(kline, "_ensure_fresh", boom)
    monkeypatch.setattr(kline, "_read_db", boom)
    monkeypatch.setattr(kline, "kline_client",
                        type("K", (), {"fetch_kline": staticmethod(lambda: normalize(RAW_VALID))}))
    res = kline.get_kline(2)
    assert res["code"] == 0
    assert "直读上游" in res["msg"]
    assert res["data"]["bars"] == BARS  # 上游新→旧 反转为旧→新


def test_get_kline_upstream_stale(monkeypatch):
    def db_boom(*a, **k):
        raise RuntimeError("db down")

    state = {"ok": True}

    def flaky(*a, **k):
        if state["ok"]:
            return normalize(RAW_VALID)
        raise RuntimeError("upstream down")

    monkeypatch.setattr(kline, "_ensure_fresh", db_boom)
    monkeypatch.setattr(kline, "_read_db", db_boom)
    monkeypatch.setattr(kline, "kline_client",
                        type("K", (), {"fetch_kline": staticmethod(flaky)}))
    assert kline.get_kline(2)["code"] == 0  # 首取经上游路径成功，填充 last-good
    state["ok"] = False
    kline._upstream.clear()  # 仅保留 last-good
    res = kline.get_kline(2)
    assert res["code"] == 2 and res["stale"] is True
    assert res["data"]["bars"] == BARS


def test_get_kline_db_cooldown_skips_retry(monkeypatch):
    calls = {"n": 0}

    def db_boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("db down")

    monkeypatch.setattr(kline, "_ensure_fresh", lambda *a, **k: None)  # 真实实现自吞异常
    monkeypatch.setattr(kline, "_read_db", db_boom)
    monkeypatch.setattr(kline, "kline_client",
                        type("K", (), {"fetch_kline": staticmethod(lambda: normalize(RAW_VALID))}))
    r1 = kline.get_kline(2)
    assert r1["code"] == 0 and "数据库不可用" in r1["msg"]
    r2 = kline.get_kline(2)
    assert r2["code"] == 0
    assert calls["n"] == 1  # 冷却期内不再触碰 DB，降级路径零等待


def test_get_kline_total_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("all down")

    monkeypatch.setattr(kline, "_ensure_fresh", boom)
    monkeypatch.setattr(kline, "_read_db", boom)
    monkeypatch.setattr(kline, "kline_client",
                        type("K", (), {"fetch_kline": staticmethod(boom)}))
    res = kline.get_kline(10)
    assert res["code"] == 1
    assert res["data"]["bars"] == []
    assert "失败" in res["msg"]


# ---------- 路由 ----------

def test_api_kline_ok(client, monkeypatch):
    monkeypatch.setattr(kline, "get_kline",
                        lambda days: {"code": 0, "ts": 1, "stale": False, "msg": "",
                                      "data": {"symbol": "AUTD", "columns": [], "bars": []}})
    r = client.get("/api/gold/kline?days=30")
    assert r.status_code == 200
    assert r.json()["code"] == 0


def test_api_kline_days_validation(client):
    assert client.get("/api/gold/kline?days=0").status_code == 422
    assert client.get("/api/gold/kline?days=1000").status_code == 422


def test_trend_page_skeleton(client):
    r = client.get("/web/gold/trend")
    assert r.status_code == 200
    assert 'id="kline-chart"' in r.text
    assert "/static/vendor/echarts.min.js" in r.text
    assert "/static/js/gold_kline.js" in r.text


def test_gold_page_links_trend(client):
    r = client.get("/web/gold")
    assert r.status_code == 200
    assert 'href="/web/gold/trend"' in r.text
