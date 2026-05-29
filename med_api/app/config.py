from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):

    db_host: str = os.environ.get("DB_HOST", "localhost")
    db_port: int = os.environ.get("DB_PORT", 5432)
    db_name: str = os.environ.get("DB_NAME", "medical_db")
    db_user: str = os.environ.get("DB_USER", "medical_user")
    db_password: str = os.environ.get("DB_PASSWORD", "medical_password")
    
    
    llm_api_url: str = os.environ.get("API_URL_GENERATE" ,"http://localhost:11434/api/generate")
    llm_api_key: Optional[str] = None
    llm_model: str = os.environ.get("LLM_MODEL","qwen2.5:14b")
    
    emb_model:str = 'intfloat/multilingual-e5-large'
    
    app_host: str = os.environ.get("APP_HOST","0.0.0.0")
    app_port: int = os.environ.get("APP_PORT", 8000)
    debug: bool = os.environ.get("DEBUG", True)
    

settings = Settings()