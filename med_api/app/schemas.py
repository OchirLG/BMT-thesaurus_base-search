from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from enum import Enum

class StructuredQuery(BaseModel):
    """Структурированный запрос из первого LLM"""
    bmt_days_min: Optional[int] = None
    bmt_days_max: Optional[int] = None
    timestamp_after: Optional[datetime] = None
    timestamp_before: Optional[datetime] = None
    terms: List[str] = Field(default_factory=list)
    gender: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None

class TermCluster(BaseModel):
    """Кластеризованный термин с флагом отрицания"""
    terms: List[Tuple[str, float]] = Field(description="Список кортежей (термин, вес), где вес — семантическая близость к исходному запросу")

class ProcessedQuery(BaseModel):
    """Обработанный запрос после второго LLM"""
    structured_filters: StructuredQuery
    term_clusters: List[TermCluster]

# class RoundScore(BaseModel):
#     """Оценка релевантности обхода"""
#     round_id: int
#     reg_id: str
#     timestamp: datetime
#     bmt_days: int
#     descr: Optional[str]
#     score: float = Field(description="Общий score релевантности")
#     term_matches: Dict[str, Any] = Field(description="Детали совпадений по терминам")
#     matched_terms: List[str] = Field(description="Найденные термины из запроса")

class RoundScore(BaseModel):
    """Оценка релевантности обхода"""
    # Основные поля
    round_id: int
    reg_id: str
    birth_year: Optional[int] = None 
    gender: Optional[str] = None   
    case_id: Optional[str] = None  
    timestamp: datetime
    bmt_days: int
    bmt_timestamp: Optional[datetime] = None 
    descr: Optional[str] = None
    terms_list: Optional[List[str]] = None  
    
    # Результаты поиска
    score: float = Field(description="Общий score релевантности")
    term_matches: Dict[str, Any] = Field(description="Детали совпадений по терминам")
    matched_terms: List[str] = Field(description="Найденные термины из запроса")

class SearchResponse(BaseModel):
    """Ответ API"""
    query: str
    structured_query: StructuredQuery
    term_clusters: List[TermCluster]
    results: List[RoundScore]
    total_count: int
    processing_time_ms: float

class TermSearchRequest(BaseModel):
    query: str
    limit: int = 20

class TermResponse(BaseModel):
    term: str
    expansion: Optional[str]
    definition: Optional[str]

class EditSuggestionRequest(BaseModel):
    term: str
    suggested_expansion: Optional[str] = None
    suggested_definition: Optional[str] = None
    user: Optional[str] = None

class AddTermRequest(BaseModel):
    term: str
    expansion: Optional[str] = None
    definition: Optional[str] = None
    user: Optional[str] = None