from pathlib import Path

# 定义项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
# 定义缓存目录
CACHE_DIR = BASE_DIR / ".cache"
LOG_DIR = BASE_DIR / "logs"