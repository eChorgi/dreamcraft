from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

# 定义项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# 定义缓存目录
CACHE_DIR = BASE_DIR / ".cache"
LOG_DIR = BASE_DIR / "logs"
PROMPT_DIR = BASE_DIR / "src" / "dreamcraft" / "prompts"
MINEFLAYER_DIR = BASE_DIR / "src" / "mineflayer_server"
DATA_DIR = BASE_DIR / "data"
WIKI_DIR = DATA_DIR / "wiki"
SKILL_DIR = DATA_DIR / "skill"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    chat_api_key: str
    embedding_api_key: str

    chat_model_name: str = "gpt-5.4-nano"
    embedding_model_name: str = "text-embedding-v4"
    embedding_url: Optional[str] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    embedding_dimension: int = 1536
    temperature: float = 0.7
    llm_request_timeout: int = 30
    mc_port: Optional[int] = 33333

    mineflayer_host: str = "http://127.0.0.1"
    mineflayer_port: int = 3000
    mineflayer_request_timeout: int = 600
    mineflayer_path: Path = MINEFLAYER_DIR / "index.js"

    wiki_documents_path: Path = WIKI_DIR / "wiki_documents.json"
    wiki_md_path: Path = WIKI_DIR / "md"
    wiki_faiss_index_path: Path = WIKI_DIR / "wiki_faiss.index"

    skill_documents_path: Path = SKILL_DIR / "skill_documents.json"
    skill_embeddings_path: Path = SKILL_DIR / "skill_embeddings.npy"
    skill_faiss_index_path: Path = SKILL_DIR / "skill_faiss.index"
    skill_js_dir: Path = SKILL_DIR / "js"

    snapshot_documents_path: Path = DATA_DIR / "snapshot_documents.json"
    snapshot_faiss_index_path: Path = DATA_DIR / "snapshot_faiss.index"

    quest_pkl_path: Path = DATA_DIR / "quests.pkl"

    log_dir: Path = LOG_DIR
    cache_dir: Path = CACHE_DIR
    prompt_dir: Path = PROMPT_DIR

    azure_client_id: Optional[str] = None
    azure_secret_value: Optional[str] = None
    azure_redirect_url: Optional[str] = "https://127.0.0.1/auth-response"
    azure_minecraft_version: str = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()