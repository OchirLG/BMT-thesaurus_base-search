import os
from dotenv import load_dotenv
from typing import List, Tuple, Set, Dict, Optional, Any
from dataclasses import dataclass, field

load_dotenv()

class Config():
    API_URL = os.environ.get('API_URL')
    API_URL_GENERATE = os.environ.get('API_URL_GENERATE')
    MODEL_NAME = os.environ.get('MODEL_NAME')
    N_CONTEXTS = os.environ.get('N_CONTEXTS')

    # Пути к файлам
    CORPUS_PATH: str = "data/data2indexing_small.parquet"
    THESAURUS_PATH: str = "thesaurus_data/thesaurus_emb_small.parquet"
    OUTPUT_PATH: str = "data/indexed_rounds_small.parquet"
    
    # PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5435
    DB_NAME: str = "medical_db"
    DB_USER: str = "medical_user"
    DB_PASSWORD: str = "medical_password"
    
    # Эмбеддинги
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
    EMBEDDING_DIM: int = 1024  # Размерность для e5-large
    
    # Параметры чанкинга
    CHUNK_SIZE_CHARS: int = 1000
    CHUNK_LANGUAGE: str = "russian"
    
    
    # Паттерны отрицаний
    NEGATION_PATTERNS: List[str] = field(default_factory=lambda: [
        r'(нет|не обнаружен|отсутствует|исключая|без)\s+([а-яА-ЯёЁ][а-яА-ЯёЁ\s]{2,30})',
        r'не\s+([а-яА-ЯёЁ][а-яА-ЯёЁ\s]{2,30})',
        r'отрицается\s+([а-яА-ЯёЁ][а-яА-ЯёЁ\s]{2,30})',
        r'не выявлен\s+([а-яА-ЯёЁ][а-яА-ЯёЁ\s]{2,30})',
        r'не наблюдается\s+([а-яА-ЯёЁ][а-яА-ЯёЁ\s]{2,30})',
        r'отсутствие\s+([а-яА-ЯёЁ][а-яА-ЯёЁ\s]{2,30})',
    ])