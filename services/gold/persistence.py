"""Async DB snapshot writes (hybrid persistence).

Realtime GETs never touch MySQL; this module is only called from a
daily scheduler job / BackgroundTasks so history accrues for later
premium-chart queries without slowing manual refresh.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def snapshot_all(domestic: list[dict], intl: list[dict], etf: list[dict], otc: list[dict]) -> dict:
    from database.database_utils import db_session_scope
    from models.gold_model import GoldEtfSnapshot, GoldPriceSnapshot

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC，pymysql 写入友好
    trade_date = now.date()
    try:
        with db_session_scope() as db:
            for q in (domestic or []) + (intl or []):
                db.add(GoldPriceSnapshot(
                    symbol=str(q.get("symbol", "")),
                    name=str(q.get("name", "")),
                    price=q.get("price"),
                    change_pct=q.get("change_pct"),
                    unit=str(q.get("unit", "")),
                    source=str(q.get("source", "")),
                    ts=now,
                ))
            for q in (etf or []) + (otc or []):
                db.add(GoldEtfSnapshot(
                    code=str(q.get("code", "")),
                    trade_date=trade_date,
                    price=q.get("price"),
                    change_pct=q.get("change_pct"),
                    volume=q.get("volume"),
                    nav=q.get("nav"),
                    est_nav=q.get("est_nav"),
                    source=str(q.get("source", "")),
                    ts=now,
                ))
    except Exception as e:
        logger.error("gold snapshot failed: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    logger.info("gold snapshot saved (%d price + %d etf rows)",
                len(domestic or []) + len(intl or []), len(etf or []) + len(otc or []))
    return {"status": "success", "saved_at": now.isoformat()}


def snapshot_gold_job() -> dict:
    """Daily scheduler entry: fresh-fetch (bypass 30s cache) then persist."""
    from services.gold import cache as cache_mod
    from services.gold import service

    cache_mod.get_cache().clear()
    domestic = service.get_domestic().get("data") or []
    intl_env = service.get_international().get("data") or {}
    intl = intl_env.get("quotes", []) if isinstance(intl_env, dict) else []
    all_env = service.get_all().get("data") or {}
    etf = all_env.get("etf", []) if isinstance(all_env, dict) else []
    otc = all_env.get("otc", []) if isinstance(all_env, dict) else []
    return snapshot_all(domestic, intl, etf, otc)
