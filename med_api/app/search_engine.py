from .schemas import ProcessedQuery, RoundScore, TermCluster
from .database import db
from .llm_client import llm_client
import numpy as np
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SearchEngine:
    async def search_rounds(self, 
                           processed_query: ProcessedQuery) -> List[RoundScore]:
        # Предфильтрация по структурированным параметрам
        filtered_rounds = await self._apply_filters(processed_query.structured_filters)
        
        if not filtered_rounds:
            return []
        
        # Получение терминов для каждого обхода
        rounds_with_terms = await self._get_rounds_terms(filtered_rounds)
        
        # Вычисление алгоритмического score
        scored_results = await self._calculate_scores(
            rounds_with_terms, 
            processed_query.term_clusters
        )
        
        
        
        #Сортировка по score
        logger.info("Sorting results")
        scored_results.sort(key=lambda x: x.score, reverse=True)
        
        return scored_results
    
    async def _apply_filters(self, filters) -> List[Dict]:
        """Применить структурированные фильтры к БД"""
        conditions = []
        params = []
        param_idx = 1
        
        query = """
            SELECT 
                id, 
                reg_id, 
                birth_year, 
                gender, 
                case_id, 
                timestamp, 
                bmt_days, 
                bmt_timestamp, 
                descr
            FROM medical_rounds
            WHERE 1=1
                """
        
        if filters.bmt_days_min is not None:
            conditions.append(f"bmt_days >= ${param_idx}")
            params.append(filters.bmt_days_min)
            param_idx += 1
        
        if filters.bmt_days_max is not None:
            conditions.append(f"bmt_days <= ${param_idx}")
            params.append(filters.bmt_days_max)
            param_idx += 1
        
        if filters.timestamp_after is not None:
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(filters.timestamp_after)
            param_idx += 1
        
        if filters.timestamp_before is not None:
            conditions.append(f"timestamp <= ${param_idx}")
            params.append(filters.timestamp_before)
            param_idx += 1
        
        if filters.gender is not None:
            
            conditions.append(f"gender = ${param_idx}::gender_type")
            params.append(filters.gender)
            param_idx += 1
        
        if filters.age_min is not None or filters.age_max is not None:
            current_year = datetime.now().year
            if filters.age_min is not None:
                max_birth_year = current_year - filters.age_min
                conditions.append(f"birth_year <= ${param_idx}")
                params.append(max_birth_year)
                param_idx += 1
            if filters.age_max is not None:
                min_birth_year = current_year - filters.age_max
                conditions.append(f"birth_year >= ${param_idx}")
                params.append(min_birth_year)
                param_idx += 1
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC LIMIT 200"
        
        logger.info(f"Executing query: {query}")
        logger.info(f"Params: {params}")
        
        rows = await db.fetch(query, *params)
        logger.info("query executed")
        return [dict(row) for row in rows]
    
    async def _get_rounds_terms(self, rounds: List[Dict]) -> List[Dict]:
        """Получить термины для списка обходов"""
        if not rounds:
            return []
        
        round_ids = [r["id"] for r in rounds]
        
        query = """
                SELECT 
                    mr.id as round_id,
                    mr.reg_id,
                    mr.birth_year,
                    mr.gender,
                    mr.case_id,
                    mr.timestamp,
                    mr.bmt_days,
                    mr.bmt_timestamp,
                    mr.descr,
                    t.term
                FROM medical_rounds mr
                LEFT JOIN round_terms rt ON mr.id = rt.round_id
                LEFT JOIN thesaurus t ON rt.term_id = t.id
                WHERE mr.id = ANY($1)
                ORDER BY mr.id
                """
        
        logger.info("getting rounds terms from DB")
        rows = await db.fetch(query, round_ids)
        logger.info("terms finded")
        
        rounds_dict = {}
        for round_data in rounds:
            rounds_dict[round_data["id"]] = {
                "id": round_data["id"],
                "reg_id": round_data["reg_id"],
                "birth_year": round_data.get("birth_year"),
                "gender": round_data.get("gender"),
                "case_id": round_data.get("case_id"),
                "timestamp": round_data["timestamp"],
                "bmt_days": round_data["bmt_days"],
                "bmt_timestamp": round_data["bmt_timestamp"],
                "descr": round_data.get("descr"),
                "terms_list": []
            }
        
        for row in rows:
            round_id = row["round_id"]
            if round_id in rounds_dict and row["term"]:
                rounds_dict[round_id]["terms_list"].append({
                    "term": row["term"]
                })
        
        return list(rounds_dict.values())
    
    async def _calculate_scores(self, 
                           rounds_with_terms: List[Dict], 
                           term_clusters: List[TermCluster]) -> List[RoundScore]:
        """
        Вычисляет score для каждого обхода.
        Для каждого кластера ищем максимальный вес среди его терминов,
        которые присутствуют в обходе (точное совпадение).
        Итоговый score = среднее арифметическое весов по кластерам.
        """
        results = []
        
        logger.info("calculating scores")
        for i, round_data in enumerate(rounds_with_terms):
            round_terms_set = set(rt["term"] for rt in round_data.get("terms_list", []))
            cluster_scores = []
            cluster_matches = {}
            all_matched_terms = []

            for cluster in term_clusters:
                best_weight = 0.0
                best_matched_term = None
                
                # Проходим по всем терминам кластера с их весами
                for term, weight in cluster.terms:
                    if term in round_terms_set:
                        # Нашли точное совпадение – берём вес этого термина
                        if weight > best_weight:
                            best_weight = weight
                            best_matched_term = term
                
                # Сохраняем результат для кластера
                cluster_scores.append(best_weight)
                if best_matched_term:
                    all_matched_terms.append(best_matched_term)
                    cluster_matches[f"cluster_{len(cluster_matches)}"] = {
                        "cluster_terms": [t for t, _ in cluster.terms],
                        "matched_terms": [best_matched_term],
                        "weight": best_weight,
                        "found": True
                    }
                else:
                    cluster_matches[f"cluster_{len(cluster_matches)}"] = {
                        "cluster_terms": [t for t, _ in cluster.terms],
                        "matched_terms": [],
                        "weight": 0.0,
                        "found": False
                    }
            
            # Итоговый score = среднее по кластерам
            if cluster_scores:
                final_score = sum(cluster_scores) / len(cluster_scores)
            else:
                final_score = 0.0
            
            results.append(RoundScore(
                round_id=round_data["id"],
                reg_id=round_data["reg_id"],
                birth_year=round_data.get("birth_year"),
                gender=round_data.get("gender"),
                case_id=round_data.get("case_id"),
                timestamp=round_data["timestamp"],
                bmt_days=round_data["bmt_days"],
                bmt_timestamp=round_data.get("bmt_timestamp"),
                descr=round_data.get("descr"),
                terms_list=[rt["term"] for rt in round_data.get("terms_list", [])],
                score=final_score,
                term_matches=cluster_matches,
                matched_terms=list(set(all_matched_terms))
            ))

            if i % 20 == 0:
                logger.info(f"{i} rounds evaluated")
        
        logger.info(f"all {i} rounds evaluated")

        return results

    
    async def _llm_validate_results(self,
                                    scored_results: List[RoundScore],
                                    term_clusters: List[TermCluster],
                                    original_query: str) -> List[RoundScore]:
        """LLM валидация результатов"""
       
        rounds_for_validation = []
        for result in scored_results[:15]:
            rounds_for_validation.append({
                "round_id": result.round_id,
                "reg_id": result.reg_id,
                "bmt_days": result.bmt_days,
                "timestamp": str(result.timestamp),
                "descr": result.descr[:200] if result.descr else "",
                "matched_terms": result.matched_terms,
                "algorithmic_score": result.score
            })
        
        clusters_dict = [
            {
                "terms": cluster.terms,
                "is_negated": cluster.is_negated,
                "weight": cluster.weight
            }
            for cluster in term_clusters
        ]
        
        validation_results = llm_client.validate_and_score_rounds(
            rounds_for_validation,
            clusters_dict,
            original_query
        )
        
        if validation_results:
            validation_map = {v['round_id']: v for v in validation_results}
            for result in scored_results:
                if result.round_id in validation_map:
                    result.score = validation_map[result.round_id].get('score', result.score)
        
        return scored_results
    
    def _term_match(self, term1: str, term2: str) -> bool:
        """Сбалансированная логика сопоставления терминов"""
        if not term1 or not term2:
            return False
        
        term1_lower = term1.lower().strip()
        term2_lower = term2.lower().strip()
        
        # Точное совпадение
        if term1_lower == term2_lower:
            return True
        
        import re
        
        def normalize(t: str) -> str:
        
            t = re.sub(r'(ая|ое|ие|ый|ой|ий|ые|ых|ыми|ому|его|ого)$', '', t)
         
            t = re.sub(r'\b(в|на|с|без|для|о|об|при|через)\b', '', t)
          
            t = ' '.join(t.split())
            return t
        
        norm1 = normalize(term1_lower)
        norm2 = normalize(term2_lower)
        
        # Проверка после нормализации
        if norm1 and norm2 and norm1 == norm2:
            return True
        

        if len(term1_lower.split()) > 3 or len(term2_lower.split()) > 3:
            return False
        
        return False
    
search_engine = SearchEngine()