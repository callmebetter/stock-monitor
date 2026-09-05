"""项目首页与纯前端工具页路由.

- GET /                ：项目首页（功能入口导航，静态渲染）
- GET /web/tools/stitch：截图拼接工具（纯浏览器端 Canvas 处理，无后端交互）

与 routes/web_routes.py（prefix=/web/gold 的黄金行情页）区分：
本 router 不带 prefix，承载与黄金业务无关的通用页面。
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """项目首页：各 Web 功能入口（截图拼接 / 黄金行情 / 走势 / API 文档）。"""
    return templates.TemplateResponse(request=request, name="home.html", context={})


@router.get("/web/tools/stitch", response_class=HTMLResponse)
def stitch(request: Request):
    """截图拼接工具页（移动端优先，图片处理全部在浏览器内完成）。"""
    return templates.TemplateResponse(request=request, name="tools/stitch.html", context={})
