import pandas as pd
import numpy as np
import re
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx
from tqdm import tqdm
import requests
from typing import List, Tuple, Set
from scripts.config import Config
from scripts.get_terms import call_llm

import argparse

config = Config()



def normalize_term(term: str) -> str:
    """Удаляет лишние символы, приводит к нижнему регистру, схлопывает пробелы."""
    term = term.lower().strip()
    term = re.sub(r'[^\w\s]', '', term)
    term = re.sub(r'\s+', ' ', term)
    return term

def remove_exact_duplicates_normalized(df):
    """Удаляет точные дубликаты по нормализованному term + definition (если definition не пуст)."""
    df = df.copy()

    df['term_norm'] = df['term'].apply(normalize_term)
   
    has_def = df['definition'].notna() & (df['definition'].str.strip() != '')
 
    df_with_def = df[has_def].drop_duplicates(subset=['term_norm', 'definition'], keep='first')
    
    df_without_def = df[~has_def].drop_duplicates(subset=['term_norm'], keep='first')
    df_dedup = pd.concat([df_with_def, df_without_def], ignore_index=True)
 
    df_dedup.drop(columns=['term_norm'], inplace=True)
    return df_dedup


def find_candidate_pairs(df, threshold=0.97):
    """Возвращает список пар индексов (i, j), где сходство эмбеддингов >= threshold."""
    mask = df['embedding'].notna()
    indices = df[mask].index.tolist()
    if len(indices) < 2:
        return []
    
    embeddings = np.stack(df.loc[indices, 'embedding'].values)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    
    sim = cosine_similarity(embeddings)
    np.fill_diagonal(sim, 0)
    
    pairs = []
    for i, idx_i in enumerate(indices):
        for j, idx_j in enumerate(indices):
            if i < j and sim[i, j] >= threshold:
                pairs.append((idx_i, idx_j))
    return pairs

def build_clusters(pairs):
    """Строит компоненты связности из списка пар."""
    G = nx.Graph()
    G.add_edges_from(pairs)
    return list(nx.connected_components(G))


def llm_decide_duplicates(terms_defs_list: List[Tuple[int, str, str]], config: Config) -> Set[int]:
    """
    terms_defs_list: список кортежей (индекс в df, термин, определение)
    Возвращает множество индексов, которые следует удалить (лишние дубликаты)
    """
    if len(terms_defs_list) <= 1:
        return set()
    
    items_text = []
    for idx, term, definition in terms_defs_list:
        def_text = definition if definition and pd.notna(definition) else "Нет определения"
        items_text.append(f"Термин: {term}\nОпределение: {def_text}")
    
    user_prompt = f"""
Ты — эксперт по терминологии в медицине, гематологии и онкогематологии. Перед тобой список терминов (каждый с определением), которые, вероятно, относятся к одному понятию (синонимы, варианты написания, опечатки).

Определи, какие из этих терминов являются абсолютными дубликатами (обозначают одну и ту же сущность без смысловых различий). Если термины различаются по смыслу – они НЕ дубликаты.

Список терминов:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(items_text))}

Ответь в формате JSON:
{{
    "canonical_index": <номер (1..N) канонического термина>,
    "duplicate_indices": [<номера остальных, которые являются дубликатами канонического>]
}}

Если все термины разные, то "duplicate_indices": [].
"""
    system_prompt = "Ты полезный помощник, отвечающий только JSON без лишнего текста."
    
    try:
        response = call_llm(system_prompt, user_prompt, temperature=0.0, is_json=True, config=config)
      
        import json
        result = json.loads(response)
        dup_numbers = result.get("duplicate_indices", [])
    
        dup_indices = {terms_defs_list[i-1][0] for i in dup_numbers if 1 <= i <= len(terms_defs_list)}
        return dup_indices
    except Exception as e:
        print(f"Ошибка LLM при обработке кластера: {e}")
        return set()

def deduplicate_with_llm(df, clusters, config, max_cluster_size=8):
    """
    Для каждого кластера решаем, какие индексы удалить.
    Если кластер больше max_cluster_size, разбиваем на подгруппы.
    """
    to_remove = set()

    clusters_sorted = sorted(clusters, key=len, reverse=True)
    
    for cluster in tqdm(clusters_sorted, desc="LLM обработка кластеров"):
        if len(cluster) < 2:
            continue
        

        items = [(idx, df.loc[idx, 'term'], df.loc[idx, 'definition']) for idx in cluster]
        

        if len(items) > max_cluster_size:
            for i in range(0, len(items), max_cluster_size):
                sub_items = items[i:i+max_cluster_size]
                dup = llm_decide_duplicates(sub_items, config)
                to_remove.update(dup)
        else:
            dup = llm_decide_duplicates(items, config)
            to_remove.update(dup)
    
    return to_remove


def main():
    parser = argparse.ArgumentParser(description="Удаление дубликатов")

    parser.add_argument("--thesaurus_path", type=str, default="thesaurus_data/thesaurus_emb_final.parquet",
                        help="Путь для тезауруса")
    parser.add_argument("--output_path", type=str, default="thesaurus_data/thesaurus_deduplicated_final.parquet",
                        help="Путь для тезауруса без дубликатов")
    
    args = parser.parse_args()

    # Пути к файлам
    # PATH_INPUT = "thesaurus_data/thesaurus_emb_final.parquet"
    # PATH_OUTPUT = "thesaurus_data/thesaurus_deduplicated_final.parquet"
    SIMILARITY_THRESHOLD = 0.95 
    
    # Загрузка
    df = pd.read_parquet(args.thesaurus_path)
    print(f"Загружено строк: {len(df)}")
    
   
    df = remove_exact_duplicates_normalized(df)
    print(f"После удаления точных дубликатов: {len(df)}")
    
    candidate_pairs = find_candidate_pairs(df, threshold=SIMILARITY_THRESHOLD)
    print(f"Найдено пар кандидатов: {len(candidate_pairs)}")
    
    if not candidate_pairs:
        print("Нет пар выше порога. Сохраняем без изменений.")
        df.to_parquet(args.output_path, engine="pyarrow")
        return
    

    clusters = build_clusters(candidate_pairs)
    print(f"Получено кластеров (потенциальных дубликатов): {len(clusters)}")
    

    to_remove = deduplicate_with_llm(df, clusters, config)
    print(f"Будет удалено строк (дубликатов): {len(to_remove)}")
    
   
    df_dedup = df.drop(index=to_remove).reset_index(drop=True)
    print(f"Итоговое количество строк: {len(df_dedup)}")
    df_dedup.to_parquet(args.output_path, engine="pyarrow")
    print(f"Сохранено в {args.output_path}")

if __name__ == "__main__":
    main()