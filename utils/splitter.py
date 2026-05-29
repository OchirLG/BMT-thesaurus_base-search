import nltk
from nltk.tokenize import sent_tokenize

def chunk_text_by_sentences(text, target_chunk_size=1000, language='russian'):
    """
    Разбивает текст на части примерно по target_chunk_size символов,
    строго соблюдая границы предложений.
    """
    sentences = sent_tokenize(text, language=language)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        
        # Если добавление предложения превысит лимит (с небольшим допуском),
        # сохраняем текущий чанк и начинаем новый
        if current_length + sentence_len > target_chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk).strip())
            current_chunk = []
            current_length = 0
            
        current_chunk.append(sentence)
        current_length += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk).strip())
        
    return chunks

if __name__ == "__main__":
    pass
    
    # chunks = chunk_text_by_sentences(huge_text, target_chunk_size=1500)