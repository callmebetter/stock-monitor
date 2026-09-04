"""国际金价：XAU/GC 走新浪 → huilvbiao → Yahoo 三级降级；DXY/USDCNY 走 Yahoo/新浪。

Yahoo 近期持续 403，且 XAUUSD=X 已下架，因此 XAU/GC 优先新浪 hf_XAU/hf_GC，
失败时回退汇率宝 gold_indexApi（同源数据，<1s），再失败才走 Yahoo GC=F。
DXY（美元指数）新浪与汇率宝均不提供，仅 Yahoo DX-Y.NYB。
"""
import logging
import time

import httpx

import config

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.sina.com.cn"}

_HUILVBIAO_URL = "https://www.huilvbiao.com/api/gold_indexApi"

_ROWS = {
    "XAU": {"name": "伦敦金", "unit": "美元/盎司"},
    "GC": {"name": "COMEX黄金期货", "unit": "美元/盎司"},
    "DXY": {"name": "美元指数", "unit": "点"},
    "USDCNY": {"name": "美元/人民币", "unit": "汇率"},
}


def _row(symbol: str, price, change_pct, source: str) -> dict:
    meta = _ROWS[symbol]
    return {"symbol": symbol, "name": meta["name"], "price": price,
            "change_pct": change_pct, "unit": meta["unit"], "source": source}


def _yahoo_chart(client: httpx.Client, ticker: str) -> tuple[float | None, float | None]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    resp = client.get(url, params={"interval": "1d", "range": "5d"})
    resp.raise_for_status()
    result = (resp.json().get("chart") or {}).get("result") or []
    if not result:
        return None, None
    meta = result[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    prev = meta.get("previousClose") or meta.get("chartPreviousClose")
    change_pct = None
    if price and prev:
        try:
            change_pct = (float(price) - float(prev)) / float(prev) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            change_pct = None
    return price, change_pct


def _fetch_yahoo(client: httpx.Client, ticker: str) -> tuple[float | None, float | None]:
    for attempt in (1, 2):
        try:
            return _yahoo_chart(client, ticker)
        except httpx.HTTPStatusError as e:
            # 4xx/5xx 是确定性错误（如 403 Forbidden），重试无意义，直接降级
            logger.warning("yahoo %s attempt %d failed: %s", ticker, attempt, e)
            return None, None
        except Exception as e:
            logger.warning("yahoo %s attempt %d failed: %s", ticker, attempt, e)
    return None, None


def _parse_hf(body: str, symbol: str) -> tuple[float | None, float | None]:
    """新浪 hf_ 行情：[0]最新价 [4]最高 [5]最低 [6]时间 [7]昨结 [8]今开。"""
    import re
    m = re.search(rf'var hq_str_{re.escape(symbol)}="([^"]*)"', body)
    if not m:
        return None, None
    parts = m.group(1).split(",")
    if len(parts) < 9 or not parts[0]:
        return None, None
    try:
        price = float(parts[0])
        prev = float(parts[7]) if parts[7] else None
        change_pct = (price - prev) / prev * 100 if prev else None
        return price, change_pct
    except (ValueError, ZeroDivisionError):
        return None, None


def _sina_quotes(codes: list[str]) -> dict[str, tuple[float | None, float | None]]:
    url = f"https://hq.sinajs.cn/list={','.join(codes)}"
    out: dict[str, tuple[float | None, float | None]] = {}
    try:
        resp = httpx.get(url, timeout=config.GOLD_CONFIG.get("timeout", 5), headers=_HEADERS)
        body = resp.content.decode("gbk", errors="ignore")
        for code in codes:
            out[code] = _parse_hf(body, code)
    except Exception as e:
        logger.warning("sina quotes failed: %s", e)
    return out


def _huilvbiao_quotes(codes: list[str]) -> dict[str, tuple[float | None, float | None]]:
    """汇率宝 gold_indexApi：返回 hf_XAU / hf_GC（格式同新浪 hf_，可复用 _parse_hf）。"""
    out: dict[str, tuple[float | None, float | None]] = {}
    try:
        resp = httpx.get(_HUILVBIAO_URL, params={"t": int(time.time() * 1000)},
                         timeout=config.GOLD_CONFIG.get("timeout", 5), headers=_HEADERS)
        body = resp.content.decode("utf-8", errors="ignore")
        for code in codes:
            out[code] = _parse_hf(body, code)
    except Exception as e:
        logger.warning("huilvbiao quotes failed: %s", e)
    return out


def _parse_fx_susdcny(body: str) -> tuple[float | None, float | None]:
    import re
    m = re.search(r'var hq_str_fx_susdcny="([^"]*)"', body)
    if not m:
        return None, None
    parts = m.group(1).split(",")
    try:
        price = float(parts[1])
        prev = float(parts[3]) if parts[3] else None
        change_pct = (price - prev) / prev * 100 if prev else None
        return price, change_pct
    except (ValueError, IndexError, ZeroDivisionError):
        return None, None


def fetch_international() -> list[dict]:
    # Yahoo 近期持续 403，仅 DXY（美元指数）无其他免费源，仍走 Yahoo；
    # XAU/GC 走 新浪 → huilvbiao → Yahoo 三级降级，USDCNY 走 新浪 → Yahoo。
    yahoo_timeout = 3
    out = []
    with httpx.Client(timeout=yahoo_timeout, headers=_HEADERS) as client:
        sina_batch = _sina_quotes(["hf_XAU", "hf_GC"])
        hui_batch = _huilvbiao_quotes(["hf_XAU", "hf_GC"])

        # 伦敦金：新浪 → huilvbiao（Yahoo XAUUSD=X 已下架，不走 Yahoo）
        price, pct = sina_batch.get("hf_XAU", (None, None))
        src = "sina-hf"
        if price is None:
            price, pct = hui_batch.get("hf_XAU", (None, None))
            src = "huilvbiao"
        out.append(_row("XAU", price, pct, src))

        # COMEX：新浪 → huilvbiao → Yahoo GC=F
        price, pct = sina_batch.get("hf_GC", (None, None))
        src = "sina-hf"
        if price is None:
            price, pct = hui_batch.get("hf_GC", (None, None))
            src = "huilvbiao"
        if price is None:
            price, pct = _fetch_yahoo(client, "GC=F")
            src = "yahoo"
        out.append(_row("GC", price, pct, src))

        # 美元指数：Yahoo DX-Y.NYB（新浪 hf_DIN 与汇率宝均不提供）
        price, pct = _fetch_yahoo(client, "DX-Y.NYB")
        out.append(_row("DXY", price, pct, "yahoo"))

        # USD/CNY：新浪 fx_susdcny → Yahoo CNY=X
        url = "https://hq.sinajs.cn/list=fx_susdcny"
        try:
            resp = client.get(url)
            price, pct = _parse_fx_susdcny(resp.content.decode("gbk", errors="ignore"))
        except Exception as e:
            logger.warning("sina fx_susdcny failed: %s", e)
            price, pct = None, None
        if price is None:
            price, pct = _fetch_yahoo(client, "CNY=X")
            out.append(_row("USDCNY", price, pct, "yahoo"))
        else:
            out.append(_row("USDCNY", price, pct, "sina-fx"))

    if all(i["price"] is None for i in out):
        raise RuntimeError("all international upstreams failed")
    return out
