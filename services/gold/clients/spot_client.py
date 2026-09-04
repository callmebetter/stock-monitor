"""国内现货金价：AkShare-first（SGE 实时行情 + 上海金基准，PRD §6.1 / §8.2）.

新浪 hf_/AU9999 接口已停发空数据，fundgz/估值接口亦停用，
故仅保留 AkShare 源；失败时由 service 层返回 last-good 缓存。
"""
import logging

import pandas as pd

import config

logger = logging.getLogger(__name__)

DOMESTIC_ROWS = ["Au99.99", "Au(T+D)", "SHAU", "Au9999"]


def _fetch_sge_quotes() -> list[dict]:
    import akshare as ak

    df = ak.spot_quotations_sge()
    if df is None or df.empty:
        raise RuntimeError("spot_quotations_sge returned empty")
    sym_col, price_col = df.columns[0], df.columns[2]
    out = []
    for symbol in ("Au99.99", "Au(T+D)", "Au9999"):
        sub = df[df[sym_col].astype(str).str.strip() == symbol]
        if sub.empty:
            continue
        prices = pd.to_numeric(sub[price_col], errors="coerce").dropna()
        if prices.empty:
            continue
        out.append({"symbol": symbol, "name": symbol, "price": float(prices.iloc[-1]),
                    "change_pct": None, "unit": "元/克", "source": "akshare.sge"})
    if not out:
        raise RuntimeError("SGE quotes missing all target symbols")
    logger.info("domestic spot via akshare.sge (%d)", len(out))
    return out


def _fetch_shau() -> list[dict]:
    import akshare as ak

    df = ak.spot_golden_benchmark_sge()
    if df is None or df.empty:
        return []
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return []
    price = float(numeric.iloc[-1, -1])
    return [{"symbol": "SHAU", "name": "上海金基准价", "price": price,
             "change_pct": None, "unit": "元/克", "source": "akshare.sge-benchmark"}]


def _fetch_em_sge(missing: set[str]) -> list[dict]:
    """东方财富 m:118 市场（上金所合约）补拉，AkShare 实时源仅含 Au99.99。"""
    import httpx

    em_map = {"Au(T+D)": "AUTD", "Au9999": "Au9999"}
    wanted = {em_map[s] for s in missing if s in em_map}
    if not wanted:
        return []
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {"pn": "1", "pz": "50", "po": "1", "np": "1", "fltt": "2",
              "invt": "2", "fid": "f43", "fs": "m:118", "fields": "f12,f14,f43,f170"}
    resp = httpx.get(url, params=params, timeout=config.GOLD_CONFIG.get("timeout", 5),
                     headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    diff = ((resp.json().get("data") or {}).get("diff")) or []
    out = []
    for row in diff:
        code = str(row.get("f12", ""))
        if code not in wanted:
            continue
        price = row.get("f43")
        if price in (None, "-", ""):
            continue  # 收盘时段为 "-"
        out.append({"symbol": next(s for s, c in em_map.items() if c == code),
                    "name": str(row.get("f14", "")), "price": float(price),
                    "change_pct": _pct(row.get("f170")), "unit": "元/克",
                    "source": "eastmoney-sge"})
    if out:
        logger.info("domestic spot补拉 via eastmoney m:118 (%d)", len(out))
    return out


def _pct(v):
    if v in (None, "-", ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_domestic() -> list[dict]:
    """返回 PRD §6.1 的 4 项（缺失项以 price=None 占位，保证顺序稳定）。"""
    items: list[dict] = []
    try:
        items += _fetch_sge_quotes()
    except Exception as e:
        logger.warning("SGE quotes failed: %s", e)
    try:
        items += _fetch_shau()
    except Exception as e:
        logger.warning("SHAU benchmark failed: %s", e)
    have = {i["symbol"] for i in items if i["price"] is not None}
    missing = set(DOMESTIC_ROWS) - have
    if missing:
        try:
            items += _fetch_em_sge(missing)
        except Exception as e:
            logger.warning("eastmoney SGE补拉 failed: %s", e)
    return _pad(items)


def _pad(items: list[dict]) -> list[dict]:
    by_symbol = {i["symbol"]: i for i in items}
    out = []
    for symbol in DOMESTIC_ROWS:
        if symbol in by_symbol:
            out.append(by_symbol[symbol])
        else:
            out.append({"symbol": symbol, "name": symbol, "price": None,
                        "change_pct": None, "unit": "元/克", "source": "missing"})
    return out
