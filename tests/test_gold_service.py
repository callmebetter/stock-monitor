"""Service-layer tests: premium formula, cache TTL, stale fallback, envelopes.

All upstream clients are mocked; no network or DB access.
"""
import time

import pytest

import services.gold.cache as cache_mod
import services.gold.service as service
from services.gold.service import calc_premium


@pytest.fixture(autouse=True)
def fresh_cache():
    c = cache_mod.GoldCache(ttl=30)
    orig = cache_mod._cache
    cache_mod._cache = c
    yield
    cache_mod._cache = orig


def test_premium_formula():
    domestic = [{"symbol": "Au9999", "price": 770.0}]
    intl = [
        {"symbol": "XAU", "price": 2500.0},
        {"symbol": "USDCNY", "price": 7.15},
    ]
    res = calc_premium(domestic, intl)
    implied = 2500.0 * 7.15 / 31.1035
    assert res["implied"] == pytest.approx(implied, abs=0.01)
    assert res["premium"] == pytest.approx(770.0 - implied, abs=0.01)


def test_premium_missing_inputs_returns_none():
    res = calc_premium([{"symbol": "Au9999", "price": None}], [{"symbol": "XAU", "price": 2500.0}])
    assert res["premium"] is None


def test_cache_hit_within_ttl(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "spot_client", type("S", (), {"fetch_domestic": staticmethod(lambda: calls.append(1) or [{"symbol": "Au9999", "price": 1}])}))
    r1 = service.get_domestic()
    r2 = service.get_domestic()
    assert r1["code"] == 0 and r2["code"] == 0
    assert len(calls) == 1


def test_stale_fallback_on_upstream_failure(monkeypatch):
    state = {"ok": True, "payload": [{"symbol": "Au9999", "price": 100.0}]}

    def flaky():
        if state["ok"]:
            return state["payload"]
        raise RuntimeError("upstream down")

    monkeypatch.setattr(service, "spot_client", type("S", (), {"fetch_domestic": staticmethod(flaky)}))
    ok = service.get_domestic()
    assert ok["code"] == 0
    state["ok"] = False
    cache_mod.get_cache().clear()  # 使 TTL 缓存过期，仅保留 last-good
    stale = service.get_domestic()
    assert stale["stale"] is True
    assert stale["code"] == 2
    assert stale["data"] == state["payload"]


def test_hard_failure_envelope(monkeypatch):
    def boom():
        raise RuntimeError("no cache, no upstream")

    monkeypatch.setattr(service, "spot_client", type("S", (), {"fetch_domestic": staticmethod(boom)}))
    res = service.get_domestic()
    assert res["code"] == 1
    assert res["data"] == []
    assert "失败" in res["msg"]


def test_etf_group_envelope(monkeypatch):
    payload = [{"code": "518850", "price": 7.5, "change_pct": 0.5}]
    monkeypatch.setattr(service.etf_client, "fetch_etf_batch", lambda codes: payload)
    res = service.get_lowfee()
    assert res["code"] == 0
    assert res["data"] == payload


def test_cache_expiry(monkeypatch):
    calls = []
    cache = cache_mod.GoldCache(ttl=1)
    monkeypatch.setattr(cache_mod, "_cache", cache)
    monkeypatch.setattr(service, "spot_client", type("S", (), {"fetch_domestic": staticmethod(lambda: calls.append(1) or [{"symbol": "Au9999", "price": 1}])}))
    service.get_domestic()
    time.sleep(1.1)
    service.get_domestic()
    assert len(calls) == 2
