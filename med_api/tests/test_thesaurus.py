import pytest
import pandas as pd
from med_api.app.routers import thesaurus

pytestmark = pytest.mark.asyncio

async def test_suggest_edit(client, tmp_path):
    original_path = thesaurus.EDIT_REQUESTS_PATH
    temp_file = tmp_path / "edit_requests.parquet"
    thesaurus.EDIT_REQUESTS_PATH = str(temp_file)

    response = await client.post("/api/thesaurus/suggest", json={
        "term": "анемия",
        "suggested_expansion": "Новая расшифровка",
        "suggested_definition": "Новое определение"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Suggestion saved"

    df = pd.read_parquet(temp_file)
    assert len(df) == 1
    assert df.iloc[0]["term"] == "анемия"
    thesaurus.EDIT_REQUESTS_PATH = original_path

async def test_add_term(client, tmp_path):
    original_path = thesaurus.EDIT_REQUESTS_PATH
    temp_file = tmp_path / "edit_requests.parquet"
    thesaurus.EDIT_REQUESTS_PATH = str(temp_file)

    response = await client.post("/api/thesaurus/add", json={
        "term": "цитопения",
        "expansion": "снижение клеток крови",
        "definition": "состояние..."
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Term added successfully"

    df = pd.read_parquet(temp_file)
    assert len(df) == 1
    assert df.iloc[0]["term"] == "цитопения"
    thesaurus.EDIT_REQUESTS_PATH = original_path