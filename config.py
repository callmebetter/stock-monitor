import os

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),  # 必须在 .env 中配置
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

# 黄金行情追踪器配置（gold-invest.md）
GOLD_CONFIG = {
    'timeout': int(os.getenv('GOLD_TIMEOUT', 5)),        # 上游请求超时（秒）
    'cache_ttl': int(os.getenv('GOLD_CACHE_TTL', 30)),   # 内存缓存 TTL（秒）
    'snapshot': os.getenv('GOLD_SNAPSHOT', '1') == '1',  # 是否启用每日 DB 快照
}