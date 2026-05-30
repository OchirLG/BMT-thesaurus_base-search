import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from med_api.app.main import app
from med_api.app.database import db

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_db_pool():
    """Мок пула соединений БД."""
    pool = AsyncMock()
    mock_conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchval = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock()
    return pool

@pytest.fixture
def mock_llm():
    """Мок LLMClient (все методы)."""
    with pytest.MonkeyPatch().context() as mp:
        # call_llm – базовый
        mp.setattr("med_api.app.llm_client.LLMClient.call_llm", MagicMock(return_value='{"response": 5}'))
        # extract_terms
        mp.setattr("med_api.app.llm_client.LLMClient.extract_terms", MagicMock(return_value=["анемия", "мукозит"]))
        # extract_structured_query
        mp.setattr("med_api.app.llm_client.LLMClient.extract_structured_query", MagicMock(return_value={
            "bmt_days_min": None,
            "bmt_days_max": None,
            "timestamp_after": None,
            "timestamp_before": None,
            "terms": ["анемия", "мукозит"],
            "gender": None,
            "age_min": None,
            "age_max": None
        }))
        # validate_terms
        mp.setattr("med_api.app.llm_client.LLMClient.validate_terms", MagicMock(return_value={"response": ["анемия", "мукозит"]}))
        # get_med_definition (если используется)
        mp.setattr("med_api.app.llm_client.LLMClient.get_med_definition", MagicMock(return_value={"type": None, "definition": None, "expansion": None}))
        # validate_and_score_rounds (если используется)
        mp.setattr("med_api.app.llm_client.LLMClient.validate_and_score_rounds", MagicMock(return_value=[]))
        yield

@pytest.fixture
def mock_embedder():
    with pytest.MonkeyPatch().context() as mp:
        async def mock_get_similar_terms_with_scores(self, term, threshold=0.78, num=150):
            return [(term, 1.0), (f"{term}_syn", 0.85)]
        mp.setattr("med_api.app.embedd_search.EmbedderModel.get_similar_terms_with_scores", mock_get_similar_terms_with_scores)
        yield

@pytest.fixture(autouse=True)
def override_db_pool(mock_db_pool):
    """Автоматически подменяем db.pool на мок во всех тестах."""
    original_pool = db.pool
    db.pool = mock_db_pool
    yield
    db.pool = original_pool