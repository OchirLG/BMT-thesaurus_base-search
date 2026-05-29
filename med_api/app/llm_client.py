import requests
import json
import re
import logging
from typing import List, Dict, Any, Optional
from .config import settings

logger = logging.getLogger(__name__)

def chunk_list(lst: list, n: int) -> list[list]:
    """Разделить список на n примерно равных частей."""
    if n <= 0:
        raise ValueError("n должно быть > 0")
    if n == 1:
        return [lst]
    
    k, m = divmod(len(lst), n)
    return [
        lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)]
        for i in range(n)
    ]

def parse_json(raw: str):
        """Извлекает JSON из сырого ответа, игнорируя markdown и мусор"""
        clean = re.sub(r'```(?:json)?\s*', '', raw, flags=re.I).replace('```', '').strip()
        clean = clean.replace('\\', '/')
        start = clean.find('{')
        if start == -1: return None, None, None, "NO_JSON"
        
        # Находим последнюю закрывающую скобку верхнего уровня
        depth = 0
        end = -1
        for i, char in enumerate(clean[start:], start):
            if char == '{': depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
                    
        if end == -1: return None, None, None, "UNBALANCED_BRACES"
        
        try:
            data = json.loads(clean[start:end+1])
            t = str(data.get("type", "")).strip() or "другое"
            d = str(data.get("definition", "")).strip() or None
            exp = str(data.get("expansion", "")).strip() or None
            if d and d.lower() in ("null", "none", ""): d = None
            return t, d, exp, None
        except json.JSONDecodeError:
            return None, None, None, "INVALID_JSON"

class LLMClient:
    def __init__(self):
        self.api_url_generate = settings.llm_api_url
        self.model_name = settings.llm_model
    
    def call_llm(self, 
                 system_prompt: str, 
                 user_prompt: str, 
                 temperature: float = 0.0, 
                 is_json: bool = False) -> str:
        payload = {
            "model": self.model_name,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "keep_alive": 0,
            "options": {
                "temperature": temperature,
                "seed": 42,
                "num_ctx": 6144,
                "repetition_penalty": 1.05,
                "num_predict": 1024,
            },
        }
        if is_json:
            payload["format"] = "json"
        
        try:
            response = requests.post(self.api_url_generate, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def get_med_definition(self, term: str, context: str, max_retries: int = 2) -> dict:
        """
        Генерирует каноническое медицинское определение для векторной БД.
        """
        system_prompt = """Ты — медицинский лексикограф в области онкогематологии. Твоя задача: создать каноническое определение термина.

        ### 1. ЭТАЛОННЫЙ СЛОВАРЬ (Приоритет 100%):
        Если видишь эти аббревиатуры, используй ТОЛЬКО эти значения:
        - ИДЛ: Инфузия донорских лимфоцитов (маркеры: CD3+, клетки/кг).
        - МОБ: Минимальная остаточная болезнь (маркеры: WT1, ИФТ, ПЦР).
        - ГЛГ: Гемофагоцитарный лимфогистиоцитоз (осложнение после ТКМ).
        - ЗГТ: Заместительная гемокомпонентная терапия (переливание крови/тромбоцитов).
        - ТМА: Тромботическая микроангиопатия.
        - РТПХ: Реакция «трансплантат против хозяина».

        ### 2. ПРАВИЛО "NULL" ПРИ НЕУВЕРЕННОСТИ:
        Если термин — аббревиатура, и она:
        А) Отсутствует в "Эталонном словаре" выше.
        Б) Не расшифрована явно в предоставленном тексте.
        В) Ты не можешь со 100% уверенностью определить её значение из контекста (якорей домена).
        ТОГДА: установи значения "expansion": null и "definition": null.

        ### 3. СТРУКТУРА JSON (СТРОГО):
        {
        "reasoning": "Пошаговый разбор: поиск словарей-якорей, проверка по эталонному словарю, оценка уверенности.",
        "expansion": "Расшифровка аббревиатуры или каноническое написание термина или null",
        "type": "заболевание" | "осложнение" | "симптом" | "процедура" | "анализ" | "генетика" | "препарат" | "протокол" | "другое" | null,
        "definition": "Текст определения или null"
        }

        ### 4. КРИТЕРИИ ОПРЕДЕЛЕНИЯ (если не null):
        - Без цикличности.
        - Без данных конкретного пациента.
        - Академический стиль.
        """

        
        user_prompt = f"Термин: {term}\nКонтекст: {context}\nВерни только JSON."

        for attempt in range(max_retries + 1):
            try:
                raw = self.call_llm(system_prompt, user_prompt, temperature=0.1)
                t, d, exp, err = parse_json(raw)
                if err is not None:
                    print(err)
                    print(raw)
                return {"type": t, "definition": d, "expansion": exp}
            except Exception as e:
                print(f"LLM error (attempt {attempt+1}): {e}")
                continue

        
        return {
            "type": None,
            "expansion": None,
            "definition": term,
            "_fallback": True
        }
    
    def extract_structured_query(self, user_query: str) -> Dict[str, Any]:
        """Извлечение структурированного запроса (адаптировано под ваш формат)
        return 
        {
            "bmt_days_min": число или null,
            "bmt_days_max": число или null,
            "timestamp_after": "YYYY-MM-DD HH:MM:SS" или null,
            "timestamp_before": "YYYY-MM-DD HH:MM:SS" или null,
            "terms": ["термин1", "термин2"],
            "gender": "M"/"F" или null,
            "age_min": число или null,
            "age_max": число или null
        }
        """
        system_prompt = """
        Ты — инструмент для структурирования медицинских поисковых запросов для поиска в базе по пациентам получившим трансплантацию костного мозга.
        Твоя задача: преобразовать запрос пользователя в структурированный JSON.

        ПРАВИЛА:
        1. Извлеки критерии поиска из запроса
        2. Если критерий не указан — ставь null
        3. Даты в формате "YYYY-MM-DD HH:MM:SS"
        4. terms — список медицинских терминов/симптомов

        "bmt_days" - это дни до трасплантация костного мозга(ТКМ), может быть отрицательным.
        Пример:
            "все пациенты за 20 дней до ТКМ и 30 после"
            структура:
                "bmt_days_min": -20,
                "bmt_days_max": 30
            "все пациенты за более чем 30 дней до трасплантации"
            структура:
                "bmt_days_min": null,
                "bmt_days_max": -30,

        timestamp - это дата медицинского обхода
        Пример:
            "все пациенты за март и февраль 2021 года"
            структура:
                "timestamp_after": "2021-02-01 00:00:00",
                "timestamp_before": "2021-03-31 23:59:59"

        gender - пол пациента, "M" - мужчина, "F" - женщина

        age - год рождения пациентов
        Пример:
            "пациенты с 1980 по 2000 г.р"
            Структура:
                "age_min": 1980,
                "age_max": 2000

        term - термины, касающиеся пациента

        ФОРМАТ JSON (НИЧЕГО кроме этого не пиши):
        {
            "bmt_days_min": число или null,
            "bmt_days_max": число или null,
            "timestamp_after": "YYYY-MM-DD HH:MM:SS" или null,
            "timestamp_before": "YYYY-MM-DD HH:MM:SS" или null,
            "terms": ["термин1", "термин2"],
            "gender": "M"/"F" или null,
            "age_min": число или null,
            "age_max": число или null
        }
        """
        
        user_prompt = f"Запрос пользователя: {user_query}"
        
        try:
            result_str = self.call_llm(system_prompt, user_prompt, temperature=0.1, is_json=True)
            result = json.loads(result_str)
            logger.info(f"Extracted structured query: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to extract structured query: {e}")
            # Fallback: извлекаем термины через extract_terms
            return {
                "bmt_days_min": None,
                "bmt_days_max": None,
                "timestamp_after": None,
                "timestamp_before": None,
                "terms": self.extract_terms(user_query),
                "gender": None,
                "age_min": None,
                "age_max": None
            }
    
    def extract_terms(self, text: str) -> List[str]:
        """Извлечение терминов из текста
        """
        system_prompt = """
        Ты — инструмент для извлечения медицинских терминов. 
        Твоя задача: найти в тексте и выписать все медицинские сущности.

        ПРАВИЛА:
        1. Выписывай термины как они есть в тексте. Просто КОПИРУЙ(подстрока)
        2. НЕ сокращай и НЕ расшифровывай: если в тексте "ОМЛ" — пиши "ОМЛ", если "острый миелоидный лейкоз" — пиши "острый миелоидный лейкоз".
        3. Извлекай ВСЁ: болезни, симптомы, лекарства, сокращения (ЩФ, ГГТП, ИСТ), генетические маркеры (FLT3, 46XX), процедуры, протоколы(FluBu10, AML-MRD2018) и нормальные/патологические показатели.
        4. Если термин содержит степень или локализацию — извлекай вместе с ними (н-р: ОМЛ (м5а вариант), "РТПХ кожи", "мукозит 2 степени").
        5. Извлекай анатомические зоны (печень, илеоцекальный угол, правая височная доля, левое легкое)
        6. Используй только РУССКИЙ язык (за исключением латинских названий лекарств или генов).
        7. НЕ извлекай даты, дозировки.

        ФОРМАТ(НИЧЕГО кроме этого не пиши):
        ["термин1", "термин2", ...]
        """
        
        user_prompt = text.replace('\\', '/')
        
        try:
            content = self.call_llm(system_prompt, user_prompt, temperature=0.0, is_json=True)
            content_fixed = content.replace("\\", "/")
            data = json.loads(content_fixed)
            logger.info(f"Extracted terms: {data}")
            return data
        except Exception as e:
            logger.error(f"Failed to extract terms: {e}")
            return []
    
    def validate_terms(self, original_term: str, possible_terms) -> List[Dict[str, Any]]:
        """валидация терминов"""
        system_prompt = """
        Ты — эксперт по медицинской онтологии, в частности трансплантации костного мозга.
        
        Задача:
        Выдели подходящие термину к оригинальному
        
        
        Правила:
        - Подходящие - это точные совпадения, близкие по смыслу или гипоним к оригинальному
        - НЕ бери термины, которые не относятся к оригинальному

        Примеры:
             Оригинальный термин: мукозит
             Предложенные термины: [лейкоз, поражение слизистых рта, мукозит 1 ст.,мукозит ЖКТ]
             Ответ: [поражение слизистых рта, мукозит 1 ст.,мукозит ЖКТ]

             Оригинальный термин: противовирусные препараты
             Предложенные термины: [арбидол, ганцикловир, меропенем, пенициллин]
             Ответ: [арбидол, ганцикловир]

             Оригинальный термин: анемия
             Предложенные термины: [анемия, аплазия, анемия 2 ст, идиопатическая апластическая анемия]
             Ответ: [анемия, анемия 2 ст, идиопатическая апластическая анемия]
        
        ФОРМАТ JSON(БОЛЬШЕ НИЧЕГО НЕ ПИШИ):
        {
            "response": ["термин1", "термин2", ...]
        }
        """
        
        final_response = {"response": []}
        possible_terms_chunks = chunk_list(possible_terms, 20)
        for chunk in possible_terms_chunks:
            user_prompt = f"""        
            Оригинальный термин: {original_term}
            Преложенные термины: {chunk}
            
            """
            try:
                result_str = self.call_llm(system_prompt, user_prompt, temperature=0.0, is_json=True)
                result = json.loads(result_str)
                logger.info(f"validated terms: {result}")
                #return result
            except Exception as e:
                logger.error(f"Failed to cluster terms: {e}")
                # Fallback
                resp = [t for t in possible_terms if original_term in t]
                result = {"response": resp}
                # return {
                #     "response": resp
                # }
            
            final_response["response"].extend(result["response"])
        
        return final_response
    
        
    def _fallback_clustering(self, terms: List[str], query: str) -> List[Dict[str, Any]]:
        """Fallback кластеризация с простым определением отрицания"""
        negation_words = ['нет', 'без', 'отсутствует', 'исключая', 'не обнаружен', 'отрицается']
        query_lower = query.lower()
        
        clusters = []
        for term in terms:
            is_negated = any(neg_word in query_lower and term.lower() in query_lower 
                           for neg_word in negation_words)
            clusters.append({
                "terms": [term],
                "is_negated": is_negated,
                "weight": 1.0
            })
        return clusters
    
    def validate_and_score_rounds(self, 
                                  rounds_data: List[Dict],
                                  term_clusters: List[Dict],
                                  original_query: str) -> List[Dict[str, Any]]:
        """Дополнительная валидация результатов через LLM"""
        if not rounds_data:
            return []
        
        rounds_to_validate = rounds_data[:20]
        
        system_prompt = """
        Ты — эксперт по валидации медицинских данных.
        Оцени релевантность каждой записи обхода запросу пользователя.
        
        Критерии оценки (0-100):
        - Полнота совпадения симптомов
        - Учет отрицаний
        - Контекстуальная релевантность
        
        ФОРМАТ JSON:
        [
            {
                "round_id": число,
                "relevance_score": число (0-100),
                "relevance_reason": "краткое объяснение"
            }
        ]
        """
        
        user_prompt = f"""
        Оригинальный запрос: "{original_query}"
        
        Кластеры терминов из запроса:
        {json.dumps(term_clusters, ensure_ascii=False, indent=2)}
        
        Данные обходов для оценки:
        {json.dumps(rounds_to_validate, ensure_ascii=False, indent=2, default=str)}
        
        Оцени релевантность каждого обхода.
        """
        
        try:
            result_str = self.call_llm(system_prompt, user_prompt, temperature=0.1, is_json=True)
            validation = json.loads(result_str)
            logger.info(f"Validation completed for {len(validation)} rounds")
            
            
            validation_dict = {v['round_id']: v for v in validation}
            for round_data in rounds_data:
                if round_data['round_id'] in validation_dict:
                    llm_score = validation_dict[round_data['round_id']]['relevance_score'] / 100.0
                    
                    round_data['score'] = round_data.get('score', 0.5) * 0.3 + llm_score * 0.7
                    round_data['validation_reason'] = validation_dict[round_data['round_id']].get('relevance_reason')
            
            return rounds_data
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return rounds_data

llm_client = LLMClient()