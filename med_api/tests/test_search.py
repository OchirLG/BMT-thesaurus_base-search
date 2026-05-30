import pytest
from med_api.app.search_engine import search_engine

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_search_endpoint(client, mock_llm, mock_embedder):
    async def mock_apply_filters(filters):
        return [
            {"id": 1, "reg_id": "P001", "birth_year": 1990, "gender": "F",
             "case_id": "C001", "timestamp": "2023-01-01", "bmt_days": 30,
             "bmt_timestamp": "2022-12-01", "descr": "Пациент с анемией и мукозитом"},
            {"id": 2, "reg_id": "P002", "birth_year": 1985, "gender": "M",
             "case_id": "C002", "timestamp": "2023-01-02", "bmt_days": 45,
             "bmt_timestamp": "2022-11-15", "descr": "Только мукозит"},
        ]

    async def mock_get_rounds_terms(rounds):
        return [
            {**r, "terms_list": [{"term": "анемия"}, {"term": "мукозит"}] if r["id"] == 1 else [{"term": "мукозит"}]}
            for r in rounds
        ]

    original_apply = search_engine._apply_filters
    original_get = search_engine._get_rounds_terms
    search_engine._apply_filters = mock_apply_filters
    search_engine._get_rounds_terms = mock_get_rounds_terms

    response = await client.post("/api/search/", json={"query": "анемия и мукозит"}, params={"threshold": 0.5})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    assert data["results"][0]["score"] > data["results"][1]["score"]

    search_engine._apply_filters = original_apply
    search_engine._get_rounds_terms = original_get