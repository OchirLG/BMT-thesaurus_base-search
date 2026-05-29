from sentence_transformers import SentenceTransformer, util
import torch
from .config import settings
import logging
from .database import db

logger = logging.getLogger(__name__)

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Используется устройство: {device}")


class EmbedderModel:
    def __init__(self):
        self.model = SentenceTransformer(settings.emb_model, device=device)
        

    async def get_similar_terms_with_scores(self, term: str, threshold: float = 0.78, num: int = 150) -> list[tuple[str, float]]:
        """
            Возвращает список кортежей (термин, similarity_score) для семантически близких терминов.
            Также включает точные совпадения с similarity = 1.0.
        """

        vector = self.model.encode(f"query: {term}")
        
        query = """
            WITH semantic_matches AS (
                SELECT 
                    t.term,
                    1 - (t.embedding <=> $1::vector) AS similarity
                FROM thesaurus t
                WHERE t.embedding IS NOT NULL
                AND 1 - (t.embedding <=> $1::vector) > $3  -- filter by threshold
                ORDER BY t.embedding <=> $1::vector
                LIMIT $2
            ),
            exact_matches AS (
                SELECT DISTINCT term, 1.0 AS similarity
                FROM thesaurus
                WHERE term ILIKE $4
            )
            SELECT DISTINCT term, similarity
            FROM (
                SELECT term, similarity FROM semantic_matches
                UNION
                SELECT term, similarity FROM exact_matches
            ) combined
            ORDER BY similarity DESC, term;
        """
        
        res = await db.fetch(query, vector, num, threshold, f"%{term}%")
        
        return [(row['term'], float(row['similarity'])) for row in res]
    
embedder = EmbedderModel()