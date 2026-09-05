"""首页与截图拼接工具页冒烟测试.

纯静态页面，无网络 / DB 依赖；TestClient 不进入 lifespan。
"""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client():
    # 不进入上下文管理器，跳过 lifespan（避免 DB/调度器）
    return TestClient(main.app)


# ---- 首页 GET / ----

def test_home_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.parametrize("link,label", [
    ("/web/tools/stitch", "截图拼接"),
    ("/web/gold", "黄金行情"),
    ("/web/gold/trend", "Au(T+D) 走势"),
    ("/docs", "API 文档"),
])
def test_home_entry_links(client, link, label):
    body = client.get("/").text
    assert f'href="{link}"' in body
    assert label in body


# ---- 截图拼接页 GET /web/tools/stitch ----

def test_stitch_200(client):
    resp = client.get("/web/tools/stitch")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.parametrize("element", [
    'id="pickBtn"',        # 上传按钮
    'id="list"',           # 图片列表
    'id="previewCanvas"',  # 预览 canvas
    'id="cropModal"',      # 裁剪模态
    'id="genBtn"',         # 生成预览
    'id="saveBtn"',        # 保存
    'id="dirV"',           # 纵向
    'id="dirH"',           # 横向
])
def test_stitch_key_elements(client, element):
    assert element in client.get("/web/tools/stitch").text


def test_stitch_uses_vendored_cropper_no_cdn(client):
    body = client.get("/web/tools/stitch").text
    assert "/static/vendor/cropper/cropper.min.css" in body
    assert "/static/vendor/cropper/cropper.min.js" in body
    assert "cdnjs" not in body
    # Express 托管说明块应已移除
    assert "express" not in body.lower()


def test_stitch_mobile_viewport(client):
    body = client.get("/web/tools/stitch").text
    assert "width=device-width" in body
    assert "maximum-scale=1.0" in body


# ---- Cropper vendor 静态资源 ----

@pytest.mark.parametrize("path", [
    "/static/vendor/cropper/cropper.min.css",
    "/static/vendor/cropper/cropper.min.js",
])
def test_cropper_vendor_assets(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert len(resp.content) > 1000
