import json
from tqdm import tqdm
import pandas as pd
from scripts.config import Config
from scripts.get_terms import call_llm
import time
import re
import re
import yaml

import argparse

config = Config()

with open('data/abbr2term.yaml', 'r', encoding='utf-8') as file:
    abbr2term = yaml.safe_load(file)

def parse_json(raw: str):
        """Извлекает JSON из сырого ответа, игнорируя markdown и мусор"""
        clean = re.sub(r'```(?:json)?\s*', '', raw, flags=re.I).replace('```', '').strip()
        clean = clean.replace('\\', '/')
        start = clean.find('{')
        if start == -1: return None, None, None, "NO_JSON"
        
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

def get_med_definition(term: str, context: str, max_retries: int = 2, suggest: str = None) -> dict:
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

    if suggest is not None:
        user_prompt = f"Термин: {term}.(Возможная рашифровка: {suggest})\nКонтекст: {context}\nВерни только JSON."
    else:
        user_prompt = f"Термин: {term}\nКонтекст: {context}\nВерни только JSON."

    for attempt in range(max_retries + 1):
        try:
            raw = call_llm(system_prompt, user_prompt, temperature=0.1, config=config)
            t, d, exp, err = parse_json(raw)
            if err is not None:
                print(err)
                print(raw)
            return {"type": t, "definition": d, "expansion": exp}
        except Exception as e:
            print(f"LLM error (attempt {attempt+1}): {e}")
            time.sleep(0.5)
            continue

    return {
        "type": None,
        "expansion": None,
        "definition": term,
        "_fallback": True
    }

def get_df(df: pd.DataFrame, step=1_000) -> pd.DataFrame:
    print(f"Всего было записей: {len(df)}")
    df = df.groupby(df["term"].str.lower(), as_index=False).first()
    print(f"После удаления дублей: {len(df)}")
    df["expansion"] = None

    i = 0
    for index, row in tqdm(df.iterrows()):
        if i >= step:
            print(f"Последний обработанный индекс: {index-1}")
            break
        if (not isinstance(row["definition"], str)) and (not isinstance(row["type"], str)):
            i += 1
            try:
                term_info: dict = get_med_definition(
                    term=row["term"].strip(), context=row["contexts"][0].strip(), suggest=abbr2term.get(row["term"].strip(), None)
                )
                
                df.at[index, "definition"] = term_info.get("definition")
                df.at[index, "type"] = term_info.get("type")
                df.at[index, "expansion"] = term_info.get("expansion")

            except Exception as e:
                print(f"Error while getting term info: {e}")

            

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Получение определений терминов")

    parser.add_argument("--input", type=str, default="data/data2thesaurus.parquet",
                        help="Путь к исходному parquet с колонкой 'descr'")
    parser.add_argument("--output", type=str, default="thesaurus_data/thesaurus_def_final.parquet",
                        help="Путь для сохранения результата")
   
    args = parser.parse_args()
    # path2data = "thesaurus_data/thesaurus_ctx_final.parquet"
    # path2save = "thesaurus_data/thesaurus_def_final.parquet"

    df = pd.read_parquet(args.input)
    df_def = get_df(df, step=200)

    df_def.to_parquet(args.output)

   
