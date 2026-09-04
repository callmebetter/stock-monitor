"""Gold tracker API routes (PRD §9). Thin handlers delegating to services/gold."""
import logging

from fastapi import APIRouter

from services.gold import service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/gold/domestic")
def get_domestic():
    """国内现货 4 指标（Au99.99 / Au(T+D) / SHAU / Au9999）"""
    return service.get_domestic()


@router.get("/gold/international")
def get_international():
    """国际金价（伦敦金 / COMEX / DXY / USD-CNY）+ 沪伦溢价"""
    return service.get_international()


@router.get("/etf/otc")
def get_etf_otc():
    """Tab1 · 场外联接基金（默认）"""
    return service.get_otc()


@router.get("/etf/lowfee")
def get_etf_lowfee():
    """Tab2 · 场内低费率（518850 / 518660 / 159830）"""
    return service.get_lowfee()


@router.get("/etf/band")
def get_etf_band():
    """Tab3 · 波段操作（159937 / 518880 / 159934 / 518800）"""
    return service.get_band()


@router.get("/etf/main")
def get_etf_main():
    """Tab4 · 主流高流动性（全部 7 只场内 ETF）"""
    return service.get_main()


@router.get("/etf/all")
def get_etf_all():
    """场内 + 场外合并（全局刷新用）"""
    return service.get_all()
