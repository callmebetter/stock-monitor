#!/usr/bin/env bash
#
# deploy.sh — stock-monitor 一键部署脚本
#
# 流程：环境检查 → 工作区检查 → git pull --ff-only → uv sync --no-dev
#       → pm2 restart/start → 健康检查 → 写 ops-log
#
# 设计原则（对应 2026-09-05 重启 212 次事故的根因）：
#   1. 依赖必须在发布阶段同步完成，不允许推迟到进程启动路径（uv run 隐式 sync）
#   2. 任一环节失败立即中止，绝不在依赖缺失/代码异常时重启线上进程
#
# 用法：
#   ./deploy.sh                    # 推荐（依赖 shebang 用 bash 执行）
#   bash deploy.sh                 # 显式 bash
#   sh deploy.sh                   # 也可：dash/sh 下会自动 exec bash 重跑
#   APP_DIR=/path/to/app bash deploy.sh   # 自定义项目目录
#
# 可选环境变量：
#   UV_INDEX_URL      PyPI 镜像（默认阿里云，VPS 本身在阿里云）
#   UV_HTTP_TIMEOUT   uv 下载超时秒数（默认 120）
#   GIT_TIMEOUT       单次 git 网络操作超时秒数（默认 120）
#   GIT_LD_PRELOAD    （逃生舱，默认留空勿设）VPS 的 /usr/local/bin/git 为静态编译 2.34.1，
#                     自带 libcurl，裸 git 拉取正常；实测强制 LD_PRELOAD 系统 libcurl 反而
#                     导致 HTTP/2 framing 报错/HTTP1.1 挂起。仅当未来 git 二进制更换后
#                     确有需要时再显式设置。
#   GIT_HTTP_VERSION  （默认留空，由 git 自动协商 HTTP/2）；必要时可设 HTTP/1.1 排查
#
# 放置位置：项目根目录（VPS: /var/www/stock-monitor/deploy.sh）；
#           仓库内归档于 scripts/deploy.sh，拉取后可复制/软链到根目录使用。

# 兼容 sh/dash 调用：非 bash 解释器时自动用 bash 重跑（pipefail/BASH_SOURCE 等为 bash 特性）
# 此守卫本身为 POSIX 语法，可在 dash 下安全执行
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

# ---- 路径与变量 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 兼容脚本放在项目根目录或 scripts/ 子目录
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
  DEFAULT_APP_DIR="$(dirname "$SCRIPT_DIR")"
else
  DEFAULT_APP_DIR="$SCRIPT_DIR"
fi
APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
APP_NAME="stock-monitor"
START_SCRIPT="start_panel.sh"
HEALTH_URL="http://127.0.0.1:8000/docs"
HEALTH_TIMEOUT=60

export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-120}"
export UV_INDEX_URL="${UV_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
GIT_TIMEOUT="${GIT_TIMEOUT:-120}"
GIT_LD_PRELOAD="${GIT_LD_PRELOAD:-}"
GIT_HTTP_VERSION="${GIT_HTTP_VERSION:-}"

# git 包装：
#   - VPS 的 /usr/local/bin/git 是静态编译 2.34.1（自带 libcurl），裸 git 即可正常拉取；
#     切勿默认 LD_PRELOAD 系统 libcurl——实测会引发 HTTP/2 framing 报错与挂起（2026-09-05 验证）
#   - GIT_LD_PRELOAD / GIT_HTTP_VERSION 仅作为显式指定时的逃生舱
#   - timeout 兜底，避免网络卡死时无限挂起（Ctrl+C 后部署日志中断无结论的教训）
git_cmd() {
  local -a prefix=() cfg=()
  if [ -n "$GIT_LD_PRELOAD" ] && [ -f "$GIT_LD_PRELOAD" ]; then
    prefix=(env LD_PRELOAD="$GIT_LD_PRELOAD")
  fi
  if [ -n "$GIT_HTTP_VERSION" ]; then
    cfg=(-c "http.version=$GIT_HTTP_VERSION")
  fi
  timeout "$GIT_TIMEOUT" "${prefix[@]}" git "${cfg[@]}" "$@"
}

# 带重试的 git 网络操作（最多 3 次，间隔 10s）；用法：git_retry fetch origin main
git_retry() {
  local attempt
  for attempt in 1 2 3; do
    if git_cmd "$@"; then return 0; fi
    log "git $* 第 ${attempt}/3 次失败（退出码 $?），10s 后重试..."
    sleep 10
  done
  return 1
}

LOG_DIR="$APP_DIR/ops-log"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"

log()  { echo "[$(date '+%F %T')] $*" | tee -a "$LOG_FILE"; }
fail() { log "ERROR: $*"; exit 1; }

log "===== deploy start (app: $APP_DIR) ====="

# ---- 0. 环境与依赖探测 ----
cd "$APP_DIR" || fail "目录不存在：$APP_DIR"
command -v git >/dev/null 2>&1 || fail "git 未安装"
command -v uv  >/dev/null 2>&1 || fail "uv 未安装"
command -v pm2 >/dev/null 2>&1 || fail "pm2 未安装"
[ -f "$START_SCRIPT" ] || fail "$START_SCRIPT 不存在"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "当前目录不是 git 仓库"

# 软提醒：start_panel.sh 建议加 --no-sync，避免进程启动时隐式联网装包
if ! grep -q -- '--no-sync' "$START_SCRIPT"; then
  log "WARN: $START_SCRIPT 未使用 'uv run --no-sync'，进程启动时仍可能隐式联网同步依赖，建议加固"
fi

# ---- 1. 工作区检查 ----
# 已跟踪文件有改动则中止（会被 pull/旧代码混淆）；未跟踪文件仅告警
# （pull 引入同路径文件时 git 会自行报错；自动忽略本脚本自身与 ops-log/ 目录）
TRACKED_DIRTY="$(git status --porcelain --untracked-files=no)"
if [ -n "$TRACKED_DIRTY" ]; then
  log "工作区已跟踪文件有未提交改动："
  echo "$TRACKED_DIRTY" | tee -a "$LOG_FILE"
  fail "请先提交或 stash 后再部署"
fi
UNTRACKED="$(git status --porcelain --untracked-files=normal | grep '^??' | grep -vE '^\?\? (deploy\.sh|ops-log/)' || true)"
if [ -n "$UNTRACKED" ]; then
  log "WARN: 存在未跟踪文件（不阻断，但若与远端新增文件同名 pull 会报错）："
  echo "$UNTRACKED" | tee -a "$LOG_FILE"
fi

# ---- 2. 拉取代码（仅允许快进，分叉时中止而不是自动 merge）----
OLD_REV="$(git rev-parse HEAD)"
log "git fetch/pull ... (old rev: ${OLD_REV:0:12}, timeout: ${GIT_TIMEOUT}s${GIT_HTTP_VERSION:+, http: $GIT_HTTP_VERSION}${GIT_LD_PRELOAD:+, preload: $GIT_LD_PRELOAD})"
git_retry fetch origin main >>"$LOG_FILE" 2>&1 || fail "git fetch 连续 3 次失败（网络波动，详见 $LOG_FILE；可稍后重试，或手动 git fetch 排查）"
# --no-rebase 显式覆盖全局 pull.rebase=true；--ff-only 分叉即中止
git_cmd pull --no-rebase --ff-only origin main >>"$LOG_FILE" 2>&1 || fail "git pull --ff-only 失败（本地与远端分叉，请人工处理）"
NEW_REV="$(git rev-parse HEAD)"
if [ "$OLD_REV" = "$NEW_REV" ]; then
  log "代码无更新（${NEW_REV:0:12}），继续同步依赖并重启"
else
  log "代码已更新：${OLD_REV:0:12} -> ${NEW_REV:0:12}"
fi

# ---- 3. 同步生产依赖（不含 dev 组；失败即中止，旧进程继续跑旧代码）----
log "uv sync --no-dev ... (index: $UV_INDEX_URL, timeout: ${UV_HTTP_TIMEOUT}s)"
if ! uv sync --no-dev >>"$LOG_FILE" 2>&1; then
  fail "uv sync 失败，已中止部署（线上旧进程未受影响，详见 $LOG_FILE）"
fi
log "依赖同步完成"

# ---- 4. 重启 PM2 进程（首次部署则 start 并 save）----
if pm2 describe "$APP_NAME" >/dev/null 2>&1; then
  log "pm2 restart $APP_NAME ..."
  pm2 restart "$APP_NAME" --update-env >>"$LOG_FILE" 2>&1
else
  log "pm2 中不存在 $APP_NAME，执行首次启动 ..."
  pm2 start "$START_SCRIPT" --name "$APP_NAME" >>"$LOG_FILE" 2>&1
  pm2 save >>"$LOG_FILE" 2>&1 || log "WARN: pm2 save 失败（不影响本次运行）"
fi

# ---- 5. 健康检查（轮询 /docs，最多 60s）----
log "健康检查 $HEALTH_URL （最长 ${HEALTH_TIMEOUT}s）..."
ok=0
for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 3 "$HEALTH_URL" || true)"
  if [ "$code" = "200" ]; then ok=1; break; fi
  sleep 1
done
[ "$ok" = "1" ] || fail "健康检查失败：$HEALTH_URL 未返回 200，请执行 'pm2 logs $APP_NAME' 排查"
log "健康检查通过"

pm2 list | tee -a "$LOG_FILE" >/dev/null
log "===== deploy done: ${OLD_REV:0:12} -> ${NEW_REV:0:12} ====="
