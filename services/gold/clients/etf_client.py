"""场内 ETF 行情：AkShare-first，降级链 新浪批量 → 腾讯逐个（PRD §8.3）.

实测东财富 push2 单票接口对本环境强制断连（clist 亦不稳定），
故降级链不依赖 push2；AkShare 底层同为东财，被限流时由新浪/腾讯兜底。
"""
import logging
import re
from typing import Optional

import httpx

from services.gold.catalog import ETF_BY_CODE

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.sina.com.cn"}


def _normalize_change_pct(v):
    """AkShare 的 fund_etf_spot_em 泄露 push2 原始 f170（×100），>10 视为已放大。"""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 100 if abs(v) > 10 else v


def _row(code: str, name: str, price, change_pct, volume, turnover, source: str) -> dict:
    return {"code": code, "name": name or ETF_BY_CODE[code]["name"], "price": price,
            "change_pct": change_pct, "volume": volume, "turnover": turnover,
            "nav": None, "est_nav": None, "fee": ETF_BY_CODE[code]["fee"],
            "source": source}


def _sina_symbol(code: str) -> str:
    return ("sh" if ETF_BY_CODE[code]["exchange"] == "沪" else "sz") + code


def _fetch_via_akshare(codes: list[str]) -> list[dict]:
    import akshare as ak

    for func_name in ("fund_etf_spot_em", "stock_zh_a_spot_em"):
        func = getattr(ak, func_name, None)
        if func is None:
            continue
        try:
            df = func()
        except Exception as e:
            logger.warning("akshare %s failed: %s", func_name, e)
            continue
        if df is None or df.empty:
            continue
        out = []
        for _, row in df.iterrows():
            data = row.to_dict()
            code = str(data.get("代码", "")).strip()
            if code not in codes:
                continue
            out.append(_row(code, str(data.get("名称", "")), _num(data.get("最新价")),
                            _normalize_change_pct(_num(data.get("涨跌幅"))),
                            _num(data.get("成交量")), _num(data.get("成交额")),
                            f"akshare.{func_name}"))
        if out:
            logger.info("gold ETF quotes via akshare.%s (%d)", func_name, len(out))
            return out
    raise RuntimeError("akshare returned no gold ETF rows")


def _num(v):
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fetch_via_sina(codes: list[str]) -> list[dict]:
    symbols = ",".join(_sina_symbol(c) for c in codes)
    resp = httpx.get(f"https://hq.sinajs.cn/list={symbols}", timeout=10, headers=_HEADERS)
    resp.raise_for_status()
    body = resp.content.decode("gbk", errors="ignore")
    out = []
    for code in codes:
        m = re.search(rf'var hq_str_{_sina_symbol(code)}="([^"]*)"', body)
        if not m:
            continue
        parts = m.group(1).split(",")
        if len(parts) < 10 or not parts[0]:
            continue
        price, prev = _num(parts[3]), _num(parts[2])
        change_pct = (price - prev) / prev * 100 if price and prev else None
        out.append(_row(code, parts[0], price, change_pct, _num(parts[8]), _num(parts[9]), "sina"))
    if not out:
        raise RuntimeError("sina returned no gold ETF rows")
    logger.info("gold ETF quotes via sina (%d)", len(out))
    return out


def _fetch_via_tencent(codes: list[str]) -> list[dict]:
    out = []
    with httpx.Client(timeout=5, headers=_HEADERS) as client:
        for code in codes:
            try:
                resp = client.get(f"https://qt.gtimg.cn/q={_sina_symbol(code)}")
                resp.raise_for_status()
                m = re.search(r'="([^"]*)"', resp.text)
                if not m:
                    continue
                parts = m.group(1).split("~")
                if len(parts) < 6 or not parts[3]:
                    continue
                price, prev = _num(parts[3]), _num(parts[4])
                change_pct = (price - prev) / prev * 100 if price and prev else None
                out.append(_row(code, parts[1], price, change_pct,
                                _num(parts[36]) if len(parts) > 36 else None,
                                _num(parts[37]) if len(parts) > 37 else None, "tencent"))
            except Exception as e:
                logger.warning("tencent fetch failed for %s: %s", code, e)
    if not out:
        raise RuntimeError("tencent returned no gold ETF rows")
    logger.info("gold ETF quotes via tencent (%d)", len(out))
    return out


def fetch_etf_batch(codes: list[str]) -> list[dict]:
    """AkShare-first；整体失败时新浪批量，再失败腾讯逐个。"""
    wanted = [c for c in codes if c in ETF_BY_CODE]
    attempts = (_fetch_via_akshare, _fetch_via_sina, _fetch_via_tencent)
    last_err: Optional[Exception] = None
    for fetch in attempts:
        try:
            got = fetch(wanted)
            missing = [c for c in wanted if c not in {g["code"] for g in got}]
            if missing:
                logger.warning("ETF补拉 missing: %s", missing)
            return sorted(got, key=lambda g: wanted.index(g["code"]))
        except Exception as e:
            logger.warning("ETF source %s failed: %s", fetch.__name__, e)
            last_err = e
    raise RuntimeError(f"all ETF sources failed: {last_err}")
