# 截图拼接工具集成 & 项目首页 需求文档（PRD）

> 日期：2026-09-06
> 来源：将 `E:\codebase-web\screenshot-stitch.html` 集成入 stock-monitor 项目，并新建项目首页作为统一入口。
> 状态：**待用户确认**（见文末确认清单），确认后方可进入实现阶段。

---

## 1. 需求背景

现有 `screenshot-stitch.html` 是一个**纯前端、移动端优先**的单文件截图拼接工具（上传 → 裁剪 → 纵/横合并 → 预览/撤销 → 分享/保存），目前只能本地双击或由 Express 托管打开。需将其纳入 stock-monitor FastAPI 服务统一访问，与现有黄金行情页面（`/web/gold`）同一服务提供。

同时项目当前**无根页面**（`/` 无内容），各功能 URL 分散、无导航入口。本次一并新建首页，作为所有 Web 功能的统一入口。

## 2. 目标受众

- **主要用户**：手机端用户（iOS Safari / 微信内置浏览器 / Android Chrome），stitch 页面严格移动端优先。
- **次要用户**：桌面浏览器（Chrome / Edge）访问首页与各页面。
- 使用场景：手机截图（如行情 App 长截图）多张拼接为一张长图，直接在手机浏览器完成并保存/分享到相册。

## 3. 功能需求清单

### F1 · 项目首页（新增，`GET /`）

| 项 | 内容 |
|---|---|
| 路由 | 根路径 `/`（当前项目无根路由，新增） |
| 模板 | `templates/home.html`（建议名） |
| 风格 | 项目暗色设计系统：复用本地 vendor 的 Tailwind + DaisyUI，`#0d1117` 暗色底、金色签名色，与黄金页同体系 |
| 布局 | 移动端优先，卡片式入口列表；桌面端居中限宽 |
| 内容 | 4 个入口卡片，每卡含名称 + 一句说明：|

入口卡片：

1. **截图拼接** → `/web/tools/stitch`（说明：多张手机截图纵向/横向拼成一张长图）
2. **黄金行情** → `/web/gold`（说明：国内/国际金价、场外与黄金 ETF 对比）
3. **Au(T+D) 走势** → `/web/gold/trend`（说明：Au(T+D) 日 K 蜡烛图与均线）
4. **API 文档** → `/docs`（说明：FastAPI Swagger 接口文档）

约束：纯静态渲染，无轮询、无 htmx 请求、无外部 CDN。

### F2 · 截图拼接页（新增，`GET /web/tools/stitch`）

| 项 | 内容 |
|---|---|
| 路由 | `/web/tools/stitch` |
| 模板 | `templates/tools/stitch.html` |
| 定位 | 源文件功能**原样迁移**，行为不变，仅做托管方式与依赖路径改造 |

保留的全部功能（与源文件一致）：

1. **上传**：选择/拍摄，可多次追加；最多 12 张；支持 JPG/PNG/WebP；非图片文件跳过；读取失败提示。
2. **列表管理**：缩略图、文件名、有效尺寸显示；上移/下移/删除。
3. **裁剪**：Cropper.js 全屏模态，单指拖拽、双指缩放；可反复重裁、重置；不破坏原图；裁剪后缩略图更新。
4. **合并设置**：纵向/横向切换；缝隙 0–60px；背景白/黑/透明（透明仅 PNG）；输出 PNG/JPG；JPG 质量 60–95 可调。
5. **尺寸规则**：纵向统一宽度为最宽图等比缩放；横向统一高度为最高图等比缩放；合成总面积超 16000×16000 时拒绝并提示。
6. **预览与撤销**：Canvas 预览，输出版本入历史栈，可逐级撤销；显示输出尺寸/方向/缝隙信息。
7. **保存**：优先 `navigator.share` 分享文件（可存相册），不支持或取消时回落 `<a download>` 下载；文件名 `stitch-<时间戳>.png/jpg`。

改造点：

- 删除源文件中「Express 嵌入方法」`<details>` 说明块（FastAPI 托管，不再适用）。
- 页面 `<title>`、header 文案保留（「📱 截图拼接」）。
- **保留自带暗色样式与移动端优先 meta**（`maximum-scale=1.0, user-scalable=no`、`env(safe-area-inset-bottom)` 底部安全区、固定底部操作栏）。
- 所有图片处理均在浏览器内完成，**不新增任何后端 API 调用、不上传、不落库**。
- 按确认结论：**不加返回首页链接**（浏览器后退即可）。

### F3 · Cropper.js Vendor 入仓

- 将 Cropper.js **1.6.2** 的 `cropper.min.css`、`cropper.min.js` 下载至 `static/vendor/cropper/`。
- 模板中两处 cdnjs CDN 引用（`<link>` 与 `<script>`）改为 `/static/vendor/cropper/cropper.min.css`、`/static/vendor/cropper/cropper.min.js`。
- 符合项目「第三方库全部 vendor 入仓、无 CDN 依赖」的既有约定（htmx / Alpine / Tailwind / DaisyUI / ECharts 同目录）。

### F4 · 路由与工程结构

- 现有 `routes/web_routes.py` 的 router 固定 prefix `/web/gold`；首页 `/` 与 `/web/tools/stitch` 需通过**新的无 prefix router** 挂载（实现方式二选一：同文件新增 `APIRouter()` 并在 `main.py` 注册，或新建 `routes/page_routes.py`；以代码整洁为准）。
- `main.py` 注册新 router；`/static` 挂载已存在，无需改动。
- **不改动**黄金页、走势页模板及其路由行为。

### F5 · 测试

- `tests/` 新增冒烟测试（遵循现有 `test_gold_web.py` 模式）：
  - `GET /` 返回 200，页面包含 4 个入口的正确链接（`/web/tools/stitch`、`/web/gold`、`/web/gold/trend`、`/docs`）。
  - `GET /web/tools/stitch` 返回 200，包含关键元素（上传按钮、预览 canvas、裁剪模态容器、合并设置区）。
  - `GET /static/vendor/cropper/cropper.min.js` 与 `cropper.min.css` 返回 200。
- 现有全部测试保持通过，无回归。

## 4. 非功能需求

| 维度 | 要求 |
|---|---|
| 兼容性 | iOS Safari、微信内置浏览器、Android Chrome 主测；桌面 Chrome/Edge 可用；移动端视口（375px 宽）布局正常 |
| 性能 | 页面服务端静态渲染；首屏无任何外部 CDN 请求；拼接计算为浏览器本地 Canvas，无网络开销 |
| 安全 | 图片数据不离开浏览器、不经服务端；页面裸 GET 可访问（与现有 `/web/gold` 一致，不引入认证） |
| 部署 | VPS 经 `scripts/deploy.sh` 部署后，外网手机访问可用，不依赖外网 CDN |
| 可观测 | 页面访问走现有 uvicorn access log（已落 `app.log`），无需新增日志 |
| 代码规范 | 遵循 `../AGENTS.md`：路由薄层、模板置 `templates/`、静态资源置 `static/`；依赖仍由 `pyproject.toml` 统一管理（本次无新增 Python 依赖） |

## 5. 范围边界

### ✅ 本期包含（In-scope）

1. 根路径首页 `/`（暗色卡片式，4 个入口）。
2. 截图拼接页 `/web/tools/stitch`，源功能原样迁移。
3. Cropper.js 1.6.2 vendor 入仓（CSS + JS）。
4. 新路由注册、`main.py` 挂载。
5. 首页/拼接页/vendor 资源的冒烟测试。
6. 实现完成后按项目惯例在 `../AGENTS.md` Changelog 追加一条记录。

### ❌ 本期不包含（Out-of-scope）

1. 拼接流程的服务端化：图片上传、服务端合成、结果存储、历史记录、用户/登录体系。
2. 用 Tailwind/DaisyUI 重写 stitch 页面 UI（保留其自带自包含样式）。
3. 黄金页、走势页的模板改动（含不加返回首页链接——本期仅首页单向链接到子页面）。
4. 智能重合检测/自动去重（源文件「撤销」为手动历史回退，不做图像匹配）。
5. PWA、Service Worker、离线缓存、添加到主屏幕等能力。
6. 除 4 个既定入口外的新功能页/工具页。

## 6. 验收标准

1. 浏览器访问 `http://<host>:8000/` 返回 200：暗色首页，4 张入口卡片，链接地址分别正确。
2. 手机视口（375px）下首页卡片排列整齐、无横向滚动；桌面端居中限宽显示正常。
3. 访问 `/web/tools/stitch` 返回 200；DevTools Network 中 Cropper 的 CSS/JS 均来自 `/static/vendor/cropper/`，**无 cdnjs 等外部请求**。
4. 功能回归（手机实测）：上传 ≥2 张截图 → 单张裁剪 → 纵向/横向分别生成预览 → 撤销 → 保存（iOS 走分享面板、其他环境走下载），全流程可用。
5. 缝隙 px、白/黑/透明背景、PNG/JPG 切换、JPG 质量滑块均对输出生效；透明背景输出 PNG 带 alpha 通道。
6. 超限提示：第 13 张图被拒绝并提示「最多 12 张」；合成尺寸超 16000×16000 时提示且不生成。
7. `/web/gold` 与 `/web/gold/trend` 行为、样式与本期前完全一致。
8. `pytest` 全套通过（含新增冒烟用例，现有 44+ 用例无回归）。
9. VPS 部署后外网手机访问首页与拼接页正常，断外网 CDN 场景下页面功能不受影响。

## 7. 确认清单（请逐项核对）

- [ ] 首页挂载在根路径 `/`，采用项目 Tailwind + DaisyUI 暗色风格、移动端卡片布局
- [ ] 首页 4 个入口：截图拼接 `/web/tools/stitch`、黄金行情 `/web/gold`、Au(T+D) 走势 `/web/gold/trend`、API 文档 `/docs`
- [ ] 拼接页路径 `/web/tools/stitch`，模板 `templates/tools/stitch.html`，功能与源文件完全一致
- [ ] Cropper.js 1.6.2（CSS + JS）vendor 入仓 `static/vendor/cropper/`，移除全部 CDN 引用
- [ ] 拼接页保留自带暗色样式与移动端优先设置，纯浏览器端计算，无后端交互
- [ ] 删除源文件中的 Express 嵌入说明块
- [ ] 子页面（stitch / 黄金页）**不**加返回首页链接，仅首页单向出口
- [ ] 新增冒烟测试，现有测试全部保持通过
- [ ] 本期不做服务端上传/存储、不做 stitch 页 UI 重构、不改动黄金页模板
