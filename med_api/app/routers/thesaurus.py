from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Optional
import pandas as pd
from datetime import datetime
import logging
from ..database import db
from ..schemas import TermResponse, TermSearchRequest, EditSuggestionRequest, AddTermRequest

router = APIRouter(prefix="/api/thesaurus", tags=["thesaurus"])
logger = logging.getLogger(__name__)

# Путь к файлу для хранения предложений
EDIT_REQUESTS_PATH = "data/thesaurus_edit_requests.parquet"



@router.post("/search", response_model=List[TermResponse])
async def search_terms(request: TermSearchRequest):
    """Поиск терминов по точному совпадению или подстроке."""
    conn = await db.pool.acquire()
    try:
        # Сначала точные совпадения
        rows = await conn.fetch(
            "SELECT term, expansion, definition FROM thesaurus WHERE term ILIKE $1 ORDER BY term LIMIT $2",
            f"%{request.query}%", request.limit
        )
        return [{"term": r["term"], "expansion": r["expansion"], "definition": r["definition"]} for r in rows]
    finally:
        await db.pool.release(conn)


@router.post("/suggest")
async def suggest_edit(suggestion: EditSuggestionRequest):
    """Сохранить предложение по изменению термина."""
    # Загружаем существующие предложения или создаём новый DataFrame
    try:
        df = pd.read_parquet(EDIT_REQUESTS_PATH)
    except:
        df = pd.DataFrame(columns=["term", "suggested_expansion", "suggested_definition", "status", "created_at"])
    
    new_row = {
        "term": suggestion.term,
        "suggested_expansion": suggestion.suggested_expansion,
        "suggested_definition": suggestion.suggested_definition,
        "status": "pending",
        "created_at": datetime.now()
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_parquet(EDIT_REQUESTS_PATH, index=False)
    return {"message": "Suggestion saved", "term": suggestion.term}


@router.post("/add")
async def add_term(term_data: AddTermRequest):
    """Добавить новый термин в тезаурус (в БД и в файл)."""
    try:
        # Пытаемся загрузить существующий файл предложений
        try:
            thesaurus_df = pd.read_parquet(EDIT_REQUESTS_PATH)
        except:
            thesaurus_df = pd.DataFrame(columns=["term", "suggested_expansion", "suggested_definition", "status", "created_at"])

        new_row = {
            "term": term_data.term,
            "suggested_expansion": term_data.expansion,
            "suggested_definition": term_data.definition,
            "status": "pending",
            "created_at": datetime.now()
        }
        thesaurus_df = pd.concat([thesaurus_df, pd.DataFrame([new_row])], ignore_index=True)
        thesaurus_df.to_parquet(EDIT_REQUESTS_PATH, index=False)

        return {"message": "Term added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Получить список предложений
@router.get("/suggestions", response_model=List[dict])
async def get_suggestions(status: Optional[str] = "pending"):
    """Получить все предложения с определённым статусом."""
    try:
        df = pd.read_parquet(EDIT_REQUESTS_PATH)
    except:
        return []
    filtered = df[df["status"] == status].to_dict(orient="records")
    return filtered