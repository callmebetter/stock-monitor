import os

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'database': os.getenv('DB_NAME', 'stock_monitor')
}

# AkShare 配置
AKSHARE_CONFIG = {
    'timeout': 10  # 请求超时时间
}

# 定时任务配置
SCHEDULER_CONFIG = {
    'timezone': 'Asia/Shanghai'
}