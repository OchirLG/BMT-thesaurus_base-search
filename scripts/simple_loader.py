import pandas as pd
import psycopg2
import numpy as np

from scripts.config import Config

import argparse

config = Config()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Загрузка в БД")

    parser.add_argument("--data_path", type=str, default="data/indexed_rounds_small_final.parquet",
                        help="Путь для индексированного корпуса")
    parser.add_argument("--thesaurus_path", type=str, default="thesaurus_data/thesaurus_deduplicated_final.parquet",
                        help="Путь для тезауруса")
    
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD
    )

    try:
        with conn.cursor() as cur:
            # # Очищаем таблицы
            # cur.execute("DROP TABLE IF EXISTS round_terms CASCADE;")
            # cur.execute("DROP TABLE IF EXISTS medical_rounds CASCADE;")
            # cur.execute("DROP TABLE IF EXISTS thesaurus CASCADE;")
            
            # # Создаем таблицы
            # cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # cur.execute("""
            #     CREATE TABLE thesaurus (
            #         id SERIAL PRIMARY KEY,
            #         term VARCHAR(255) NOT NULL UNIQUE,
            #         expansion TEXT,
            #         definition TEXT,
            #         embedding vector(1024)
            #     );
                
            #     CREATE TABLE medical_rounds (
            #         id SERIAL PRIMARY KEY,
            #         reg_id VARCHAR(50) NOT NULL,
            #         birth_year INTEGER,
            #         gender gender_type,
            #         case_id VARCHAR(50),
            #         timestamp TIMESTAMP,
            #         bmt_days INTEGER,
            #         bmt_timestamp TIMESTAMP,
            #         descr TEXT
            #     );
                
            #     CREATE TABLE round_terms (
            #         id SERIAL PRIMARY KEY,
            #         round_id INTEGER REFERENCES medical_rounds(id),
            #         term_id INTEGER REFERENCES thesaurus(id),
            #         is_negated BOOLEAN DEFAULT FALSE,
            #         UNIQUE(round_id, term_id)
            #     );
            # """)
            
            # Загружаем тезаурус
            print("Загружаем тезаурус...")
            thesaurus = pd.read_parquet(args.thesaurus_path)
            
            for _, row in thesaurus.iterrows():
                emb = row['embedding']
                if isinstance(emb, (list, tuple, np.ndarray)):
                    if isinstance(emb, np.ndarray):
                        emb = emb.tolist()
                    
                    if len(emb) != 1024:
                        print(f"Длина {len(emb)} != 1024 для термина: {row['term']}")
                else:
                    emb = None
            
                cur.execute("""
                    INSERT INTO thesaurus (term, expansion, definition, embedding)
                    VALUES (%s, %s, %s, %s)
                """, (row['term'], row['expansion'], row['definition'], emb))
            
            conn.commit()
            print(f"Загружено {len(thesaurus)} терминов")
            
            print("\nзагружем обходы...")
            corpus = pd.read_parquet(args.data_path)
            
            round_ids = []
            for idx, row in corpus.iterrows():
                gender = row['gender'] if row['gender'] in ['M', 'F'] else None
                cur.execute("""
                    INSERT INTO medical_rounds 
                    (reg_id, birth_year, gender, case_id, timestamp, bmt_days, bmt_timestamp, descr)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    str(row['reg_id']), row['birth_year'], gender, str(row['case_id']),
                    row['timestamp'], row['bmt_days'], row['bmt_timestamp'], row['descr']
                ))
                round_ids.append(cur.fetchone()[0])
            
            conn.commit()
            print(f"загружено {len(round_ids)} обходов")
            

            all_terms = set()
            
            for idx, row in corpus.iterrows():
                concepts = row['concepts']
                if concepts is not None:
                    if isinstance(concepts, np.ndarray):
                        concepts = concepts.tolist()
                    if isinstance(concepts, list):
                        for c in concepts:
                            if c and str(c).strip():
                                all_terms.add(str(c).strip())
            
            print(f"Found {len(all_terms)} unique terms")
            print("First 20 terms:")
            for term in sorted(all_terms)[:20]:
                print(f"  - {term}")
            
        
            cur.execute("SELECT term FROM thesaurus")
            existing = {row[0] for row in cur.fetchall()}
            
            missing = all_terms - existing
            
            if missing:
                for term in sorted(missing):
                    if len(term) > 200:
                        continue
                    print(f"  добавляю: {term}")
                    cur.execute("""
                        INSERT INTO thesaurus (term, expansion, definition, embedding)
                        VALUES (%s, NULL, NULL, NULL)
                        ON CONFLICT (term) DO NOTHING
                    """, (term,))
                
                conn.commit()
                
                cur.execute("SELECT term FROM thesaurus WHERE expansion IS NULL AND definition IS NULL")
                added = [row[0] for row in cur.fetchall()]
                print(f"\nAdded {len(added)} new terms")
                
                for term in sorted(added)[:20]:
                    print(f"  ОК - {term}")
            
            cur.execute("SELECT id, term FROM thesaurus")
            term_map = {term: id for id, term in cur.fetchall()}
            
    
            associations = []
            not_found = set()
            
            for idx, row in corpus.iterrows():
                concepts = row['concepts']
                if concepts is None:
                    continue
                if isinstance(concepts, np.ndarray):
                    concepts = concepts.tolist()
                if not isinstance(concepts, list):
                    concepts = [concepts]
                
                for concept in concepts:
                    if concept and str(concept).strip():
                        term = str(concept).strip()
                        if term in term_map:
                            associations.append((round_ids[idx], term_map[term], False))
                        else:
                            not_found.add(term)
            
            if associations:
                for round_id, term_id, neg in associations:
                    cur.execute("""
                        INSERT INTO round_terms (round_id, term_id, is_negated)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (round_id, term_id, neg))
                conn.commit()
                
            
            if not_found:
                print(f"\nВсе ещё нету после добавелния: {len(not_found)}")
                for term in sorted(not_found)[:20]:
                    print(f"  - {term}")
            
            print("\n" + "="*50)
            cur.execute("SELECT COUNT(*) FROM medical_rounds")
            print(f"Rounds: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM thesaurus")
            print(f"Thesaurus: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM round_terms")
            print(f"Associations: {cur.fetchone()[0]}")
            print("="*50)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()