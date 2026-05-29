import pandas as pd
import re
from pathlib import Path
import argparse

def normalize_term(term: str) -> str:
    """Нормализует термин для сравнения (удаляет пунктуацию, приводит к нижнему регистру)."""
    term = term.lower().strip()
    term = re.sub(r'[^\w\s]', '', term)
    term = re.sub(r'\s+', ' ', term)
    return term

def load_unmatched_terms(indexed_parquet_path: str) -> set:
    """Извлекает все уникальные unmatched_terms из результата индексации."""
    df = pd.read_parquet(indexed_parquet_path)
 
    unmatched_series = df['unmatched_terms'].explode().dropna()
    unique_unmatched = set(unmatched_series.unique())
    print(f"Найдено уникальных unmatched терминов: {len(unique_unmatched)}")
    return unique_unmatched

def add_terms_to_thesaurus(thesaurus_path: str, new_terms: set, output_path: str = None):
    """Добавляет новые термины в тезаурус (без эмбеддингов и прочих полей)."""
    df_thesaurus = pd.read_parquet(thesaurus_path)
    original_count = len(df_thesaurus)
    print(f"Текущий тезаурус содержит {original_count} записей.")
    
    df_thesaurus['term_norm'] = df_thesaurus['term'].apply(normalize_term)
    existing_norm = set(df_thesaurus['term_norm'])
    
    new_terms_filtered = []
    for term in new_terms:
        norm = normalize_term(term)
        if norm not in existing_norm:
            new_terms_filtered.append(term)
        else:
            print(f"  Термин уже есть в тезаурусе (пропускаем): {term}")
    
    if not new_terms_filtered:
        print("Нет новых терминов для добавления.")
        df_thesaurus.drop(columns=['term_norm'], inplace=True)
        if output_path:
            df_thesaurus.to_parquet(output_path, index=False)
        return df_thesaurus
    
    columns = list(df_thesaurus.columns)
    if 'term_norm' in columns:
        columns.remove('term_norm')
    
    new_rows = []
    for term in new_terms_filtered:
        row = {col: None for col in columns}
        row['term'] = term
        new_rows.append(row)
    
    df_new = pd.DataFrame(new_rows)
    df_updated = pd.concat([df_thesaurus, df_new], ignore_index=True)
    df_updated.drop(columns=['term_norm'], inplace=True, errors='ignore')
    
    print(f"Добавлено {len(new_terms_filtered)} новых терминов. Теперь тезаурус содержит {len(df_updated)} записей.")
    
    if output_path is None:
        output_path = thesaurus_path 
    df_updated.to_parquet(output_path, index=False)
    print(f"Обновлённый тезаурус сохранён в {output_path}")
    
    return df_updated

def main():
    parser = argparse.ArgumentParser(description="Удаление дубликатов")

    parser.add_argument("--data_path", type=str, default="data/indexed_rounds_small_final.parquet",
                        help="Путь для индексированного корпуса")
    parser.add_argument("--thesaurus_path", type=str, default="thesaurus_data/thesaurus_deduplicated_final.parquet",
                        help="Путь для тезауруса")
    parser.add_argument("--output_path", type=str, default="thesaurus_data/thesaurus_with_unmatched_final.parquet",
                        help="Путь для финального тезауруса")
    
    args = parser.parse_args()

    # INDEXED_DATA_PATH = "data/indexed_rounds_small_final.parquet"
    # THESAURUS_PATH = "thesaurus_data/thesaurus_deduplicated_final.parquet"
    # OUTPUT_THESAURUS_PATH = "thesaurus_data/thesaurus_with_unmatched_final.parquet"
    

    unmatched_terms = load_unmatched_terms(args.data_path)
    
    if not unmatched_terms:
        print("Нет unmatched терминов. Ничего не делаем.")
        return
    
    add_terms_to_thesaurus(args.thesaurus_path, unmatched_terms, args.output_path)
    

if __name__ == "__main__":
    main()