from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """应用配置"""
    
    # 服务器配置
    APP_NAME: str = "Publisher Proofreader"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS 配置
    ALLOWED_ORIGINS: list = ["*"]
    
    # 文件配置
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    
    # 语言工具配置
    LANGUAGETOOL_URL: str = "http://localhost:8081"
    LANGUAGETOOL_ENABLED: bool = True
    
    # LLM 配置
    LLM_TYPE: str = "ollama"
    OLLAMA_API_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen:7b"
    
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # 出版规范配置
    PUBLISHER_RULES: dict = {
        "max_paragraph_length": 500,
        "check_consistency": True,
        "check_terminology": True,
        "check_formatting": True,
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
