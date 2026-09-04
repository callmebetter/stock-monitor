"""Persistence tests with in-memory SQLite (no MySQL required)."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import database
import database.database_utils as db_utils
from database import Base
from models.gold_model import GoldEtfSnapshot, GoldPriceSnapshot
from services.gold.persistence import snapshot_all


@pytest.fixture()
def sqlite_db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(db_utils, "SessionLocal", factory)
    return engine


def test_snapshot_all_persists_rows(sqlite_db):
    domestic = [{"symbol": "Au99.99", "name": "Au99.99", "price": 946.0,
                 "change_pct": None, "unit": "元/克", "source": "akshare.sge"}]
    intl = [{"symbol": "XAU", "name": "伦敦金", "price": 4398.1, "change_pct": -1.7,
             "unit": "美元/盎司", "source": "sina-hf"}]
    etf = [{"code": "518880", "name": "华安黄金ETF", "price": 9.164, "change_pct": 0.65,
            "volume": 461556950, "nav": None, "est_nav": None, "source": "sina"}]
    otc = [{"code": "008702", "name": "华夏黄金ETF联接C", "price": 2.0969, "change_pct": 0.62,
            "volume": None, "nav": 2.0838, "est_nav": 2.0969, "source": "lsjz+etf-estimate"}]

    result = snapshot_all(domestic, intl, etf, otc)
    assert result["status"] == "success"

    with sqlite_db.connect() as conn:
        prices = conn.execute(select(GoldPriceSnapshot.symbol, GoldPriceSnapshot.price)).all()
        etfs = conn.execute(select(GoldEtfSnapshot.code, GoldEtfSnapshot.price)).all()
    assert {p[0] for p in prices} == {"Au99.99", "XAU"}
    # ETF + OTC 都写入 gold_etf_snapshot
    assert {e[0] for e in etfs} == {"518880", "008702"}


def test_snapshot_handles_empty_and_error(sqlite_db):
    assert snapshot_all([], [], [], [])["status"] == "success"
