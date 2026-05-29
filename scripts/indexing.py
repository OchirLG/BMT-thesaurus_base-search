from utils.splitter import chunk_text_by_sentences
from scripts.get_terms import call_llm, extract_terms
from scripts.config import Config
import pandas as pd
import numpy as np
from tqdm import tqdm
import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

config = Config()


def load_thesaurus_with_embeddings(path):
    """Загружает тезаурус, разделяет на строки с эмбеддингами и без."""
    df = pd.read_parquet(path)
 
    df['embedding'] = df['embedding'].apply(lambda x: np.array(x) if isinstance(x, (list, np.ndarray)) else x)
    # Строки, у которых есть эмбеддинг
    df_with_emb = df[df['embedding'].notna()].copy()
    if len(df_with_emb) == 0:
        raise ValueError("Нет ни одного термина с эмбеддингом! Сначала сгенерируйте эмбеддинги для тезауруса.")
    # Матрица эмбеддингов
    emb_matrix = np.vstack(df_with_emb['embedding'].values)
    return df, df_with_emb, emb_matrix


def get_query_embedding(text, model):
    """Получить эмбеддинг для поискового запроса (с префиксом 'query: ')."""
    text_prefixed = f"query: {text}"
    return model.encode([text_prefixed], normalize_embeddings=True, show_progress_bar=False)[0]


def find_similar_terms(query_emb, emb_matrix, terms_list, top_k=10):
    """Возвращает список кортежей (термин, косинусное сходство)."""
    similarities = cosine_similarity([query_emb], emb_matrix)[0]
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [(terms_list[i], similarities[i]) for i in top_indices]


def llm_select_term(chunk_context, raw_term, candidates):
    """
    Через LLM выбирает наиболее подходящий термин из списка кандидатов.
    candidates: список кортежей (термин, сходство, expansion, definition)
    """
    if not candidates:
        return None


    cand_lines = []
    for term, sim, exp, defin in candidates:
        info = f"{term}"
        if exp and pd.notna(exp):
            info += f" (расшифровка: {exp})"
        if defin and pd.notna(defin):
            info += f" — {defin[:100]}"
        cand_lines.append(info)

    prompt = f"""Контекст (предложение из врачебного обхода):
{chunk_context}

Извлечённый сырой термин (может быть в разной форме): "{raw_term}"

Кандидаты из медицинского тезауруса, семантически близкие к сырому термину:
{chr(10).join(cand_lines)}

Выбери ОДИН кандидат, который наиболее точно соответствует смыслу извлечённого термина в данном контексте.
Если ни один не подходит, ответь "None".
Верни ТОЛЬКО название выбранного термина (в точности как в списке кандидатов) или "None".
Никаких пояснений.
"""
    system_prompt = "Ты ассистент по сопоставлению медицинских терминов с тезаурусом."
    response = call_llm(system_prompt, prompt, temperature=0.0, config=config)
    response = response.strip()
    if response == "None" or not response:
        return None
    
    for term, _, _, _ in candidates:
        if term.lower() == response.lower():
            return term
    return None


def process_rounds(data_df, thesaurus_full_df, thesaurus_emb_df, emb_matrix, model):
    """
    Основная функция обработки: для каждого обхода разбивает на чанки,
    извлекает термины, ищет соответствия в тезаурусе.
    """
    data_df['concepts'] = None
    data_df['unmatched_terms'] = None 

    # Для быстрого точного совпадения
    exact_match_map = {term.lower(): term for term in thesaurus_full_df['term']}

    # Список всех терминов с эмбеддингами 
    emb_terms_list = thesaurus_emb_df['term'].tolist()

    for idx, row in tqdm(data_df.iterrows(), total=len(data_df), desc="Processing rounds"):
       
        text = row['descr']
        if pd.isna(text) or not isinstance(text, str):
            data_df.at[idx, 'concepts'] = []
            data_df.at[idx, 'unmatched_terms'] = []
            continue

        # Разбиваем на чанки
        chunks = chunk_text_by_sentences(text)
        all_concepts = []
        all_unmatched = []

        for chunk in chunks:
            # Извлекаем сырые термины из чанка
            raw_terms = extract_terms(chunk)
            if not raw_terms:
                continue

            for raw_term in raw_terms:
                raw_term_clean = raw_term.strip()
                if not raw_term_clean:
                    continue

                # Пытаемся найти точное совпадение (без учёта регистра)
                key = raw_term_clean.lower()
                if key in exact_match_map:
                    canonical = exact_match_map[key]
                    all_concepts.append(canonical)
                    continue

                # Векторный поиск среди терминов, у которых есть эмбеддинги
                query_emb = get_query_embedding(raw_term_clean, model)
                similar = find_similar_terms(query_emb, emb_matrix, emb_terms_list, top_k=10)

                if not similar:
                    # Нет даже близких по смыслу - сохраняем как unmatched
                    all_unmatched.append(raw_term_clean)
                    continue

                candidates = []
                for term, sim in similar:
                    # Берём первую строку из полного тезауруса 
                    term_row = thesaurus_full_df[thesaurus_full_df['term'] == term].iloc[0]
                    expansion = term_row.get('expansion', '') if pd.notna(term_row.get('expansion')) else ''
                    definition = term_row.get('definition', '') if pd.notna(term_row.get('definition')) else ''
                    candidates.append((term, sim, expansion, definition))

                # LLM решает, какой из кандидатов (или никакой) подходит
                selected = llm_select_term(chunk, raw_term_clean, candidates)

                if selected:
                    all_concepts.append(selected)
                else:
                    all_unmatched.append(raw_term_clean)

        # Убираем дубликаты (сохраняя порядок первого появления)
        all_concepts = list(dict.fromkeys(all_concepts))
        all_unmatched = list(dict.fromkeys(all_unmatched))

        data_df.at[idx, 'concepts'] = all_concepts
        data_df.at[idx, 'unmatched_terms'] = all_unmatched

    return data_df


def main():
    # Параметры путей
    corpus_path = "data/data2indexing_small_clean.parquet"
    thesaurus_path = "thesaurus_data/thesaurus_deduplicated_final.parquet"
    output_path = "data/indexed_rounds_small_finalv2.parquet"
    unmatched_csv = "data/unmatched_termsv2.csv"

    print("Загрузка корпуса...")
    corpus_df = pd.read_parquet(corpus_path)
    print(f"Корпус содержит {len(corpus_df)} записей.")

    print("Загрузка тезауруса и эмбеддингов...")
    thesaurus_full, thesaurus_emb, emb_matrix = load_thesaurus_with_embeddings(thesaurus_path)
    print(f"Тезаурус: {len(thesaurus_full)} терминов, из них с эмбеддингами: {len(thesaurus_emb)}")

    # Загружаем модель эмбеддингов
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Используем устройство: {device}")
    model = SentenceTransformer("intfloat/multilingual-e5-large", device=device)

    # Обработка
    print("Начинаем индексацию обходов...")
    result_df = process_rounds(corpus_df, thesaurus_full, thesaurus_emb, emb_matrix, model)

    # Сохраняем результат
    result_df.to_parquet(output_path, index=False)
    print(f"Сохранено в {output_path}")

    # Сохраняем все уникальные неподходящие термины в CSV
    unmatched_series = result_df['unmatched_terms'].explode().dropna()
    if len(unmatched_series) > 0:
        unique_unmatched = pd.Series(unmatched_series.unique())
        unique_unmatched.to_csv(unmatched_csv, index=False, header=False)
        print(f"{len(unique_unmatched)} уникальных терминов без соответствия сохранены в {unmatched_csv}")
    else:
        print("Все извлечённые термины успешно сопоставлены!")

    # Небольшая статистика
    # total_concepts = result_df['concepts'].apply(len).sum()
    # total_unmatched = result_df['unmatched_terms'].apply(len).sum()
    # print(f"\nСтатистика:")
    # print(f"  Всего найдено связей: {total_concepts}")
    # print(f"  Всего не найденных сырых терминов: {total_unmatched}")


if __name__ == "__main__":
    main()