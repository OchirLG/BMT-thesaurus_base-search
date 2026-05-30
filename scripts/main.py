import argparse
import logging
import pandas as pd
from pathlib import Path

# Импорт функций из скриптов
from scripts.get_terms import get_terms_df
from scripts.get_term_def import get_df as get_definitions_df
from scripts.get_embedding import get_embeddings_optimized
from scripts.dedup import (
    remove_exact_duplicates_normalized,
    find_candidate_pairs,
    build_clusters,
    deduplicate_with_llm,
)
from scripts.add_unmatched import load_unmatched_terms, add_terms_to_thesaurus
from scripts.indexing import (
    load_thesaurus_with_embeddings,
    process_rounds,
)
from scripts.config import Config
from scripts.get_terms import call_llm

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_full_pipeline(args):
    """Запускает все этапы обработки."""
    config = Config()

    # 1. Построение тезауруса из корпуса (извлечение терминов и контекстов)
    logger.info("=== STAGE 1: Build thesaurus from corpus ===")
    if args.skip_build_thesaurus:
        logger.info("Skipping thesaurus building (using existing file).")
        thesaurus_ctx_path = args.thesaurus_ctx
    else:
        thesaurus_ctx_path = args.thesaurus_ctx
        logger.info(f"Input corpus: {args.corpus_path}")
        logger.info(f"Output thesaurus (ctx): {thesaurus_ctx_path}")
        df_ctx = get_terms_df(args.corpus_path)
        df_ctx.to_parquet(thesaurus_ctx_path, index=False)
        logger.info(f"Thesaurus with contexts saved to {thesaurus_ctx_path}")

    # 2. Генерация определений терминов (LLM)
    logger.info("=== STAGE 2: Generate definitions for terms ===")
    if args.skip_generate_definitions:
        logger.info("Skipping definition generation (using existing file).")
        thesaurus_def_path = args.thesaurus_def
    else:
        thesaurus_def_path = args.thesaurus_def
        logger.info(f"Reading thesaurus from {thesaurus_ctx_path}")
        df_ctx = pd.read_parquet(thesaurus_ctx_path)
        logger.info(f"Generating definitions (step={args.def_step})...")
        df_def = get_definitions_df(df_ctx, step=args.def_step)
        df_def.to_parquet(thesaurus_def_path, index=False)
        logger.info(f"Thesaurus with definitions saved to {thesaurus_def_path}")

    # 3. Генерация эмбеддингов
    logger.info("=== STAGE 3: Generate embeddings for terms ===")
    if args.skip_generate_embeddings:
        logger.info("Skipping embedding generation (using existing file).")
        thesaurus_emb_path = args.thesaurus_emb
    else:
        thesaurus_emb_path = args.thesaurus_emb
        logger.info(f"Reading thesaurus from {thesaurus_def_path}")
        df_def = pd.read_parquet(thesaurus_def_path)
        df_emb, embeddings = get_embeddings_optimized(df_def, batch_size=args.emb_batch_size)
        df_emb['embedding'] = embeddings
        df_emb['has_embedding'] = df_emb['embedding'].notna()
        df_emb.to_parquet(thesaurus_emb_path, index=False)
        logger.info(f"Thesaurus with embeddings saved to {thesaurus_emb_path}")

    # 4. Дедупликация терминов
    logger.info("=== STAGE 4: Deduplicate thesaurus ===")
    if args.skip_deduplicate:
        logger.info("Skipping deduplication (using existing file).")
        thesaurus_dedup_path = args.thesaurus_dedup
    else:
        thesaurus_dedup_path = args.thesaurus_dedup
        logger.info(f"Reading thesaurus from {thesaurus_emb_path}")
        df = pd.read_parquet(thesaurus_emb_path)
        logger.info(f"Initial rows: {len(df)}")

        # Точные дубликаты по нормализованному term + definition
        df = remove_exact_duplicates_normalized(df)
        logger.info(f"After exact dedup: {len(df)}")

        # Поиск кандидатов по эмбеддингам
        candidate_pairs = find_candidate_pairs(df, threshold=args.similarity_threshold)
        logger.info(f"Candidate pairs found: {len(candidate_pairs)}")

        if candidate_pairs:
            clusters = build_clusters(candidate_pairs)
            logger.info(f"Clusters: {len(clusters)}")
            to_remove = deduplicate_with_llm(df, clusters, config, max_cluster_size=args.max_cluster_size)
            logger.info(f"Rows to remove: {len(to_remove)}")
            df_dedup = df.drop(index=to_remove).reset_index(drop=True)
        else:
            df_dedup = df

        logger.info(f"Final rows after dedup: {len(df_dedup)}")
        df_dedup.to_parquet(thesaurus_dedup_path, index=False)
        logger.info(f"Deduplicated thesaurus saved to {thesaurus_dedup_path}")

    # 5. (Опционально) Добавление unmatched терминов из индексированного корпуса
    logger.info("=== STAGE 5: Add unmatched terms from previous indexing (optional) ===")
    if args.add_unmatched and args.indexed_corpus_for_unmatched:
        logger.info(f"Loading unmatched terms from {args.indexed_corpus_for_unmatched}")
        unmatched_terms = load_unmatched_terms(args.indexed_corpus_for_unmatched)
        if unmatched_terms:
            logger.info(f"Adding {len(unmatched_terms)} unmatched terms to thesaurus")
            thesaurus_with_unmatched_path = args.thesaurus_with_unmatched or thesaurus_dedup_path
            add_terms_to_thesaurus(thesaurus_dedup_path, unmatched_terms, thesaurus_with_unmatched_path)
            # обновляем путь для следующего этапа
            thesaurus_for_indexing = thesaurus_with_unmatched_path
        else:
            logger.info("No unmatched terms found, skipping.")
            thesaurus_for_indexing = thesaurus_dedup_path
    else:
        logger.info("Skipping addition of unmatched terms (not requested or no input).")
        thesaurus_for_indexing = thesaurus_dedup_path

    # 6. Индексация корпуса (сопоставление терминов)
    logger.info("=== STAGE 6: Index corpus ===")
    if args.skip_indexing:
        logger.info("Skipping indexing (using existing file).")
    else:
        logger.info(f"Input corpus: {args.corpus_path}")
        logger.info(f"Thesaurus for indexing: {thesaurus_for_indexing}")
        logger.info(f"Output indexed corpus: {args.indexed_output}")
        logger.info(f"Unmatched terms output: {args.unmatched_csv}")

        # Загрузка тезауруса с эмбеддингами
        thesaurus_full, thesaurus_emb, emb_matrix = load_thesaurus_with_embeddings(thesaurus_for_indexing)
        logger.info(f"Thesaurus: {len(thesaurus_full)} terms, with embeddings: {len(thesaurus_emb)}")

        # Загрузка модели эмбеддингов
        from sentence_transformers import SentenceTransformer
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {device}")
        model = SentenceTransformer(config.EMBEDDING_MODEL, device=device)

        # Загрузка корпуса
        corpus_df = pd.read_parquet(args.corpus_path)
        logger.info(f"Corpus contains {len(corpus_df)} records.")

        # Индексация
        result_df = process_rounds(corpus_df, thesaurus_full, thesaurus_emb, emb_matrix, model)

        # Сохранение
        result_df.to_parquet(args.indexed_output, index=False)
        logger.info(f"Indexed corpus saved to {args.indexed_output}")

        # Сохранение unmatched терминов
        unmatched_series = result_df['unmatched_terms'].explode().dropna()
        if len(unmatched_series) > 0:
            unique_unmatched = pd.Series(unmatched_series.unique())
            unique_unmatched.to_csv(args.unmatched_csv, index=False, header=False)
            logger.info(f"Saved {len(unique_unmatched)} unique unmatched terms to {args.unmatched_csv}")
        else:
            logger.info("All extracted terms were matched successfully!")

    logger.info("=== PIPELINE FINISHED ===")


def main():
    parser = argparse.ArgumentParser(description="Полный пайплан обработки данных")

    # Основные пути
    parser.add_argument("--corpus_path", type=str, default="data/data2indexing_small_clean.parquet",
                        help="Path to input corpus (with 'descr' column)")
    parser.add_argument("--thesaurus_ctx", type=str, default="thesaurus_data/thesaurus_ctx_final.parquet",
                        help="Output for thesaurus with contexts")
    parser.add_argument("--thesaurus_def", type=str, default="thesaurus_data/thesaurus_def_final.parquet",
                        help="Output for thesaurus with definitions")
    parser.add_argument("--thesaurus_emb", type=str, default="thesaurus_data/thesaurus_emb_final.parquet",
                        help="Output for thesaurus with embeddings")
    parser.add_argument("--thesaurus_dedup", type=str, default="thesaurus_data/thesaurus_deduplicated_final.parquet",
                        help="Output for deduplicated thesaurus")
    parser.add_argument("--thesaurus_with_unmatched", type=str, default=None,
                        help="Output thesaurus after adding unmatched terms (optional)")
    parser.add_argument("--indexed_output", type=str, default="data/indexed_rounds_small_finalv2.parquet",
                        help="Output for indexed corpus")
    parser.add_argument("--unmatched_csv", type=str, default="data/unmatched_termsv2.csv",
                        help="Output CSV for unmatched terms")

    # Параметры для добавления unmatched терминов
    parser.add_argument("--add_unmatched", action="store_true",
                        help="Whether to add unmatched terms from previous indexing")
    parser.add_argument("--indexed_corpus_for_unmatched", type=str, default=None,
                        help="Path to previously indexed corpus (with 'unmatched_terms' column)")

    # Параметры этапов (пропуск)
    parser.add_argument("--skip_build_thesaurus", action="store_true", help="Skip stage 1")
    parser.add_argument("--skip_generate_definitions", action="store_true", help="Skip stage 2")
    parser.add_argument("--skip_generate_embeddings", action="store_true", help="Skip stage 3")
    parser.add_argument("--skip_deduplicate", action="store_true", help="Skip stage 4")
    parser.add_argument("--skip_indexing", action="store_true", help="Skip stage 6")

    # Дополнительные параметры
    parser.add_argument("--def_step", type=int, default=200, help="Number of terms to process in one step for definition generation")
    parser.add_argument("--emb_batch_size", type=int, default=64, help="Batch size for embedding generation")
    parser.add_argument("--similarity_threshold", type=float, default=0.95, help="Cosine similarity threshold for candidate pairs")
    parser.add_argument("--max_cluster_size", type=int, default=8, help="Max cluster size for LLM dedup")

    args = parser.parse_args()

    # Создаём необходимые директории
    for path in [args.thesaurus_ctx, args.thesaurus_def, args.thesaurus_emb, args.thesaurus_dedup, args.indexed_output]:
        dir_path = Path(path).parent
        dir_path.mkdir(parents=True, exist_ok=True)

    run_full_pipeline(args)


if __name__ == "__main__":
    main()