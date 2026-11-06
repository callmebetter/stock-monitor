FROM python:3.11-slim

# 安装 uv（Python 包管理器）
RUN pip install --no-cache-dir uv

# 设置工作目录
WORKDIR /app

# 复制依赖配置文件
COPY pyproject.toml uv.lock  .

# 使用 uv 安装依赖
RUN uv sync --frozen --index-url https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制项目源码
COPY . .

# 暴露应用端口
EXPOSE 8000

# 启动命令
CMD ["fastapi", "run", "main.py", "--port", "8000"]
