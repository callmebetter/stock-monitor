"""Pydantic schemas for the gold tracker API (PRD §9 unified envelope)."""
from typing import Any, Optional
from pydantic import BaseModel, Field


class GoldQuote(BaseModel):
    symbol: str = Field(description="展示标识，如 Au9999 / XAU / 518880 / 008702")
    name: str = ""
    price: Optional[float] = None
    change_pct: Optional[float] = None
    unit: str = ""
    source: str = ""


class EtfQuote(BaseModel):
    code: str
    name: str = ""
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    nav: Optional[float] = None
    est_nav: Optional[float] = None
    fee: Optional[float] = None


class Envelope(BaseModel):
    code: int = 0
    ts: int = 0
    stale: bool = False
    msg: str = ""
    data: Any = []
