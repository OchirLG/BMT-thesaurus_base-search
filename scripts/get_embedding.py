from sentence_transformers import SentenceTransformer
import torch
import pandas as pd
import numpy as np
from tqdm import tqdm

def get_embeddings_optimized(df, model_name="intfloat/multilingual-e5-large", batch_size=64):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer(model_name, device=device)
    
    valid_mask = df['definition'].notna() & (df['definition'].str.strip() != '')
    

    embeddings_list = [None] * len(df)
    
    valid_texts = [
        f"passage: {row['definition']}" 
        for _, row in df[valid_mask].iterrows()
    ]
    
    if len(valid_texts) > 0:
        valid_embeddings = model.encode(
            valid_texts, 
            batch_size=batch_size, 
            show_progress_bar=True, 
            convert_to_numpy=True
        )
        
        valid_indices = df[valid_mask].index
        for idx, emb in zip(valid_indices, valid_embeddings):
            embeddings_list[idx] = emb
    
    return df, embeddings_list

if __name__ == "__main__":
    path2data = "thesaurus_data/thesaurus_def_final.parquet"
    path2save = "thesaurus_data/thesaurus_emb_final.parquet"
    df = pd.read_parquet(path2data)
    df, embeddings = get_embeddings_optimized(df)
    
    df['embedding'] = embeddings
    
    df['has_embedding'] = df['embedding'].notna()
    
    df.to_parquet(path2save, engine="pyarrow")
    
    # Информация о пропущенных
    missing_count = df['embedding'].isna().sum()
    print(f"Всего строк: {len(df)}")
    print(f"Строк без эмбеддингов: {missing_count}")
    print(f"Строк с эмбеддингами: {len(df) - missing_count}")