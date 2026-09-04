"""黄金行情前端页面与 HTML 片段端点（htmx 架构，PRD §3~§6 / §10）.

现有 /api/* JSON 端点保留；/web/gold 页面通过片段端点直调
services.gold.service（同进程、共享 30s 缓存），服务端渲染 HTML。

⚠️ all-OOB 约定：本模块所有片段响应均为纯 OOB 载荷（响应内每个顶层
元素都带 hx-swap-oob，无正常主内容），消费者必须以 hx-swap="none"
发起请求（页面初始容器与各「刷新本栏」按钮均已如此配置）。
新增片段模板时，顶层元素必须携带 hx-swap-oob 并匹配页面上的目标 id。

浏览器侧超时 20s（page.html 内 htmx.config.timeout）：/fragments/all
聚合 6 路上游，冷缓存耗时约等于最慢一路，远超 PRD 的上游 5s 单路
超时（后者由 GOLD_CONFIG 在服务层强制，与本跳无关）。

降级协议：
- envelope code=1（上游硬失败）→ HTTP 204 + HX-Trigger gold-error，
  htmx 对 204 不 swap，旧数据原样保留，仅弹 Toast。
- code=2（last-good 降级）→ 正常渲染 + 「缓存」徽标 + HX-Trigger gold-stale。
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from services.gold import service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/web/gold", tags=["gold-web"])

templates = Jinja2Templates(directory="templates")

# 各 ETF Tab 的列配置（PRD §4.2），次要在移动端隐藏（PRD §10）
ETF_TABS = {
    "lowfee": {"title": "场内低费率", "recommend": "518850", "cols": ["pct", "fee", "scale"],
               "hint": "华夏黄金ETF 费率最低（0.20%），成本最优"},
    "band": {"title": "波段操作", "recommend": "159937", "cols": ["pct", "turnover"],
             "hint": "按日均成交额降序，侧重价差与成交活跃度"},
    "main": {"title": "主流高流动性", "recommend": "518880", "cols": ["pct", "turnover", "scale", "fee"],
             "hint": "全部 7 只场内 ETF，按规模降序（518880 置顶）"},
}


def _fmt_num(v, nd=3):
    return "—" if v is None else f"{v:.{nd}f}"


def _fmt_pct(v):
    return "—" if v is None else f"{v:+.2f}%"


def _fmt_yi(v):
    return "—" if v is None else f"{v / 1e8:.2f}亿"


def _fmt_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "--:--:--"


def _pct_class(v):
    if v is None or v == 0:
        return "text-muted"
    return "text-up" if v > 0 else "text-down"


templates.env.filters["num"] = _fmt_num
templates.env.filters["pct"] = _fmt_pct
templates.env.filters["yi"] = _fmt_yi
templates.env.filters["ts"] = _fmt_ts
templates.env.filters["pctcls"] = _pct_class


def _render(request: Request, name: str, ctx: dict, headers: dict | None = None) -> Response:
    return templates.TemplateResponse(request=request, name=name, context=ctx, headers=headers or None)


def _hx_headers(env: dict) -> dict:
    headers = {}
    if env.get("code") == 2:
        headers["HX-Trigger"] = json.dumps({"gold-stale": env.get("msg") or "上游超时，已返回上次缓存"})
    return headers


def _envelope_fragment(request: Request, env: dict, template: str, ctx: dict) -> Response:
    if env.get("code") == 1:
        msg = env.get("msg") or "数据获取失败，请稍后重试"
        return Response(status_code=204, headers={"HX-Trigger": json.dumps({"gold-error": msg})})
    ctx.update(data=env.get("data"), stale=bool(env.get("stale")), ts=env.get("ts"))
    return _render(request, template, ctx, _hx_headers(env))


@router.get("", response_class=HTMLResponse)
def page(request: Request):
    return _render(request, "gold/page.html", {"etf_tabs": ETF_TABS})


@router.get("/trend", response_class=HTMLResponse)
def trend_page(request: Request):
    """走势子页面（Au(T+D) 日K）。

    图表数据由前端 fetch /api/gold/kline（ECharts 需要原始 JSON，
    不适用 all-OOB 片段协议）；页面骨架为静态渲染，无 htmx 交互。
    """
    return _render(request, "gold/trend.html", {})


@router.get("/fragments/domestic", response_class=HTMLResponse)
def fragment_domestic(request: Request):
    return _envelope_fragment(request, service.get_domestic(), "gold/fragments/domestic.html", {})


@router.get("/fragments/international", response_class=HTMLResponse)
def fragment_international(request: Request):
    return _envelope_fragment(request, service.get_international(), "gold/fragments/international.html", {})


@router.get("/fragments/otc", response_class=HTMLResponse)
def fragment_otc(request: Request):
    return _envelope_fragment(request, service.get_otc(), "gold/fragments/otc_tab.html", {})


@router.get("/fragments/etf/{tab}", response_class=HTMLResponse)
def fragment_etf(tab: str, request: Request):
    if tab not in ETF_TABS:
        return Response(status_code=404)
    getters = {"lowfee": service.get_lowfee, "band": service.get_band, "main": service.get_main}
    return _envelope_fragment(request, getters[tab](), "gold/fragments/etf_tab.html",
                              {"tab": tab, "tab_meta": ETF_TABS[tab]})


def _fail_env(exc: Exception) -> dict:
    logger.warning("gold fragment upstream error: %s", exc)
    return {"code": 1, "ts": 0, "stale": False, "msg": "数据获取失败，请稍后重试", "data": []}


@router.get("/fragments/all", response_class=HTMLResponse)
def fragment_all(request: Request):
    """刷新全部：一次请求渲染全部模块，经 hx-swap-oob 一次换 6 处。

    上游并发拉取（ThreadPoolExecutor），总耗时 ≈ 最慢单路；
    单路失败时该模块旧数据保留，其余照常更新；全部失败返回 204。
    """
    specs = [
        ("gold/fragments/domestic.html", {}, service.get_domestic),
        ("gold/fragments/international.html", {}, service.get_international),
        ("gold/fragments/otc_tab.html", {}, service.get_otc),
    ]
    getters = {"lowfee": service.get_lowfee, "band": service.get_band, "main": service.get_main}
    for tab in ("lowfee", "band", "main"):
        specs.append(("gold/fragments/etf_tab.html",
                      {"tab": tab, "tab_meta": ETF_TABS[tab]}, getters[tab]))

    with ThreadPoolExecutor(max_workers=len(specs)) as pool:
        futures = [pool.submit(spec[2]) for spec in specs]
        envs = []
        for fut in futures:
            try:
                envs.append(fut.result())
            except Exception as e:  # 服务层约定不抛异常，此处仅兜底
                envs.append(_fail_env(e))

    parts = []
    failed = 0
    for (template, ctx, _), env in zip(specs, envs):
        if env.get("code") == 1:
            failed += 1  # 该模块旧数据保留，其余照常更新
            continue
        resp = _envelope_fragment(request, env, template, dict(ctx))
        parts.append(resp.body.decode("utf-8"))
    if failed == len(specs):
        return Response(status_code=204,
                        headers={"HX-Trigger": json.dumps({"gold-error": "数据获取失败，请稍后重试"})})
    return HTMLResponse("".join(parts))
