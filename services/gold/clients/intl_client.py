"""国际金价：Yahoo 优先（GC/DXY/USDCNY），伦敦金走新浪 hf_XAU.

Yahoo 已将 XAUUSD=X 下架（404），伦敦金现改用新浪 hf_XAU；
COMEX/美元指数/汇率 Yahoo 正常，新浪 hf_GC / fx_susdcny 作降级备选。
"""
import logging

import httpx

import config

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.sina.com.cn"}

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
    timeout = config.GOLD_CONFIG.get("timeout", 5)
    out = []
    with httpx.Client(timeout=timeout, headers=_HEADERS) as client:
        sina_batch = _sina_quotes(["hf_XAU", "hf_GC"])

        # 伦敦金：新浪 hf_XAU（Yahoo XAUUSD=X 已下架）
        price, pct = sina_batch.get("hf_XAU", (None, None))
        out.append(_row("XAU", price, pct, "sina-hf"))

        # COMEX：Yahoo GC=F 优先，新浪 hf_GC 降级
        price, pct = _fetch_yahoo(client, "GC=F")
        if price is None:
            price, pct = sina_batch.get("hf_GC", (None, None))
            out.append(_row("GC", price, pct, "sina-hf"))
        else:
            out.append(_row("GC", price, pct, "yahoo"))

        # 美元指数：Yahoo DX-Y.NYB（hf_DIN 已停发）
        price, pct = _fetch_yahoo(client, "DX-Y.NYB")
        out.append(_row("DXY", price, pct, "yahoo"))

        # USD/CNY：Yahoo CNY=X 优先，新浪 fx_susdcny 降级
        price, pct = _fetch_yahoo(client, "CNY=X")
        if price is None:
            url = "https://hq.sinajs.cn/list=fx_susdcny"
            try:
                resp = client.get(url)
                price, pct = _parse_fx_susdcny(resp.content.decode("gbk", errors="ignore"))
            except Exception as e:
                logger.warning("sina fx_susdcny failed: %s", e)
            out.append(_row("USDCNY", price, pct, "sina-fx"))
        else:
            out.append(_row("USDCNY", price, pct, "yahoo"))

    if all(i["price"] is None for i in out):
        raise RuntimeError("all international upstreams failed")
    return out
