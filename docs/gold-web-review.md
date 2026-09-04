# 黄金行情前端页面测试与代码 Review 报告

- 日期：2026-09-04
- 范围：`/web/gold` 页面（htmx 架构）浏览器实测 + 变更 Review
- 环境：uvicorn 运行于 http://localhost:8000（MySQL 未启动，按降级设计黄金页面不依赖 DB）
- 结论：**发现并修复 1 个致命渲染 bug（主面板全空）；变更判定合适，14/14 测试通过**

---

## 一、发现的问题

### 🔴 P0：页面主区域全部空白（已修复）

**现象**：浏览器实测 `/web/gold`，骨架屏加载完成后，国内现货 / 国际金价 / 场外联接三个面板内容为空，骨架屏残留；ETF Tab 懒加载同样受影响。

**根因**：两处接线缺陷叠加——

1. **OOB 目标节点缺失**：`fragments/domestic.html`、`fragments/international.html` 均以 `hx-swap-oob` 写入 `#mod-domestic-body` / `#mod-intl-body`，但 `page.html` 初始页面中不存在这两个 id。
2. **主 swap 擦除 OOB 内容**：htmx 先处理 OOB 交换、再执行主 swap。6 个加载容器配置为 `hx-swap="innerHTML"`，而片段响应为**纯 OOB 载荷**（主内容为空），空主 swap 会把刚被 OOB 写入的内容连同骨架屏一起清空。片段模板内 4 个「刷新本栏」按钮同样存在此隐患。

**佐证**：原作者在「刷新全部」按钮上本就使用 `hx-swap="none"`（纯 OOB 响应的标准消费方式），说明 all-OOB 是既定约定，其余 8 处 `innerHTML` 属漏改而非设计。`web_routes.py` 传递的 `oob` 上下文变量未被任何模板使用，佐证条件渲染设计只完成了一半。

### 🟡 P1：「刷新全部」请求被 abort（已修复）

`htmx.config.timeout = 5000`，而 `/fragments/all` 冷缓存实测耗时 **7.4s**（6 个上游串行请求），网络日志中 `fragments/all ... ERR_ABORTED` 实锤，点击后Toast「网络异常」。

### 🟢 P2：溢价条永久半透明（已修复）

`#premium-strip` 的 `opacity-50` 意图为加载态弱化，但 OOB 只替换 innerHTML 不替换外层 div，数据到达后半透明永久残留。

---

## 二、变更清单（6 文件，+56/-39）

| 文件 | 变更 | 判定 | 依据 |
|---|---|---|---|
| `templates/gold/page.html` | 补 `#mod-domestic-body` / `#mod-intl-body` 包装节点（与 Tab 的 `#tab-body-*` 同构，骨架屏包在 `.card` 内避免双层卡片） | ✅ 合适 | OOB 目标落点修复，浏览器实证 |
| `templates/gold/page.html` | 6 个加载容器 `hx-swap="innerHTML"` → `"none"` | ✅ 合适 | 与原作者「刷新全部」按钮模式对齐；htmx 对纯 OOB 响应的官方推荐 |
| `templates/gold/page.html` | `#premium-strip` 去掉 `opacity-50` | ✅ 合适 | OOB 不换外层 div，半透明会永久残留 |
| `templates/gold/page.html` | `htmx.config.timeout` 5s → 20s | ✅ 合适 | 冷缓存 7.4s > 5s，必然 abort |
| `templates/gold/fragments/*.html`（4 个） | 模块内刷新按钮 `hx-swap="innerHTML"` → `"none"` | ✅ 合适 | 同主 swap 擦除隐患 |
| `tests/test_gold_web.py` | 新增 `test_page_shell_contains_oob_target_ids`：断言 6 个加载容器 `id ... hx-swap="none"` 接线 + 6 个 OOB 目标 id 存在 | ✅ 合适 | 旧测试只渲染片段本身，覆盖不到 page.html 与片段的 id/swap 契约 |

修复后浏览器实证：

- 首屏：国内现货 4 格（Au99.99 / Au(T+D) / SHAU / Au9999，缺数据显示 —）、国际金价 4 格（伦敦金 / COMEX / 美元指数 / USD/CNY，涨红跌绿正确）、沪伦溢价条实时值、场外基金表（C 类 4 行 + 推荐徽标，A 类折叠于 `<details>`）
- Tab：低费率 / 波段 / 主流流动性首次激活懒加载（3 / 4 / 7 行），切回不重复请求
- 「刷新全部」：6 模块全部更新、骨架屏清零、按钮恢复 idle，不再超时
- 模块内「刷新本栏」：内容存活不被擦除，表头时间同步
- 控制台无应用报错；`pytest tests/test_gold_web.py` **14/14 通过**

---

## 三、Review 结论：合适，为最小一致性修复

相对「给每个片段模板加条件 OOB 分支（`{% if oob %}`）」的重构路线，本次选择**统一 all-OOB 约定**：改动面小、与原作者已有模式（刷新全部按钮）对齐、已浏览器实证。

## 四、遗留建议（本次未动）

1. **死代码**：`routes/web_routes.py` 6 处传递的 `oob` 参数均未被模板使用，可全删。
2. **治本项（性能）**：`fragment_all` 串行调 6 个上游是 7.4s 延迟的根因，建议 `ThreadPoolExecutor` 并发化，可压至最慢单路耗时；20s 超时只是不报错，不解决慢。
3. **约定文档化**：all-OOB 约定目前纯靠模板间默契，建议在 `web_routes.py` 模块 docstring 注明「片段响应为纯 OOB 载荷，消费者必须 `hx-swap="none"`」。
4. **无害瑕疵（可不改）**：`module-btn` class 无对应 CSS；`<body hx-headers='{}'>` 无作用。

## 五、附注

- 测试期间观察到 IDE 预览 WebView 偶发整页重载并注入 `/@vite/client` 请求，为环境行为；页面本身无 `setInterval`、无 reload 逻辑、服务端无 `HX-Refresh`/`HX-Redirect` 响应头，空闲 7 分钟无重载，普通浏览器不受影响。
- 截图取证：`gold-page-top.png`（首屏）、`gold-etf-lowfee.png`（ETF Tab），存于 `%TEMP%\trae\screenshots\`。
