from .schemas import StructuredQuery, ProcessedQuery, TermCluster
from .llm_client import llm_client
from .database import db
from .embedd_search import embedder
import logging
from typing import List

logger = logging.getLogger(__name__)


class QueryProcessor:
    async def process_user_query(self, user_query: str) -> ProcessedQuery:
        # Шаг 1: Извлечение структурированного запроса
        extracted = llm_client.extract_structured_query(user_query)
        structured = StructuredQuery(**extracted)
        
        # Шаг 2: Если термины не извлечены в структурированном запросе,
        # используем extract_terms напрямую
        if not structured.terms:
            structured.terms = llm_client.extract_terms(user_query)
        
        clusters_raw = []
        for term in structured.terms:
            #definition = llm_client.get_med_definition(term=term, context=user_query).get("definition")
            possible_terms_with_scores = await embedder.get_similar_terms_with_scores(term=term)
            logger.info(f"SIMILAR TERMS FOR {term}: {possible_terms_with_scores}")
            possible_terms = [t[0] for t in possible_terms_with_scores]

            # clusters_raw.append(llm_client.validate_terms(original_term=term, possible_terms=possible_terms))

            validated_terms: dict = llm_client.validate_terms(original_term=term, possible_terms=possible_terms)
            validated_terms: list = validated_terms.get("response", [])
            val_with_scores: list[tuple] = [tsim for tsim in possible_terms_with_scores if tsim[0] in validated_terms]

            clusters_raw.append(val_with_scores)
        
        
        term_clusters = [
            TermCluster(
                terms=cluster,
                #is_negated=cluster.get("is_negated", False)
            )
            for cluster in clusters_raw
        ]
        
        return ProcessedQuery(
            structured_filters=structured,
            term_clusters=term_clusters
        )
    
    async def _get_all_terms(self) -> List[str]:
        """Получить все термины из тезауруса"""
        query = "SELECT term FROM thesaurus LIMIT 200"
        rows = await db.fetch(query)
        return [row["term"] for row in rows]

query_processor = QueryProcessor()