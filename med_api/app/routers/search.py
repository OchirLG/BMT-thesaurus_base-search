from fastapi import APIRouter, HTTPException, Body, Query
from ..schemas import SearchResponse
from ..query_processor import query_processor
from ..search_engine import search_engine
import time
import logging

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=SearchResponse)
async def search_medical_records(
    query: str = Body(..., embed=True),
    threshold: float = Query(0.8, ge=0.0, le=1.0, description="Минимальный score для отображения результата")
):
    """
    Поиск врачебных обходов по естественно-языковому запросу.
    
    - `query`: поисковый запрос на русском языке.
    - `threshold`: порог релевантности (0.0–1.0), по умолчанию 0.8. Результаты с score ниже порога отфильтровываются.
    """
    start_time = time.time()
    
    try:
        # Шаг 1: Обработка запроса через LLM (создаёт кластеры с весами)
        processed_query = await query_processor.process_user_query(query)
        
        # Шаг 2: Поиск в БД и вычисление score с учётом весов кластеров
        results = await search_engine.search_rounds(processed_query)
        
        # Фильтрация по порогу релевантности
        filtered_results = [r for r in results if r.score >= threshold]
        logger.info("filtering by relevance")
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info("Sending response")
        return SearchResponse(
            query=query,
            structured_query=processed_query.structured_filters,
            term_clusters=processed_query.term_clusters,
            results=filtered_results,
            total_count=len(filtered_results),
            processing_time_ms=round(processing_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/extract-terms")
async def extract_terms(text: str):
    """Тестовый эндпоинт для извлечения терминов"""
    from app.llm_client import llm_client
    terms = llm_client.extract_terms(text)
    return {"text": text, "terms": terms}

@router.get("/health")
async def health_check():
    return {"status": "ok", "llm_available": True}