# gold package: 黄金行情追踪器后端 (see docs/gold-invest.md PRD v1.0).
from services.gold.service import (
    get_domestic,
    get_international,
    get_otc,
    get_lowfee,
    get_band,
    get_main,
    get_all,
)

__all__ = [
    "get_domestic",
    "get_international",
    "get_otc",
    "get_lowfee",
    "get_band",
    "get_main",
    "get_all",
]
