import json
import requests
from tqdm import tqdm
from nltk.stem.snowball import SnowballStemmer
import nltk
import re
import pandas as pd
from utils.splitter import chunk_text_by_sentences
from scripts.config import Config

stemmer = SnowballStemmer("russian")
config = Config()

# API_URL = "http://10.0.0.9:11434/api/chat"
# API_URL_GENERATE = "http://10.0.0.9:11434/api/generate"
# MODEL_NAME = "qwen2.5:14b"


def call_llm(system_prompt: str, user_prompt: str, temperature = 0.0, is_json = False, config: Config = config):
    payload = {
        "model": config.MODEL_NAME,
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
    r = requests.post(config.API_URL_GENERATE, json=payload, timeout=120)
    return r.json()["response"]


def extract_terms(text: str) -> list:

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
    ["термин1", "термин2", ...]"""

    user_prompt = text.replace('\\', '/')
    content = call_llm(system_prompt, user_prompt)
    # print(content)

    try:
        content_fixed = content.replace("\\", "/")
        data = json.loads(content_fixed)
        # for item in data:
        return data
        # return [item["term"] for item in data if "term" in item]
    except:
        # fallback
        return []
    
    
def stem_text(text: str) -> str:
    tokens = re.findall(r"\w+", text.lower())
    stems = [stemmer.stem(t) for t in tokens]
    return set(stems)

def find_contexts(term: str, text: str) -> list[str]:
    contexts = []

    term_stems = stem_text(term)
    sentences = nltk.sent_tokenize(text)

    for sent in sentences:
        sent_stems = stem_text(sent)

        overlap = term_stems & sent_stems

        if len(overlap) >= max(1, len(term_stems)//2):
            contexts.append(sent)

    return contexts

def get_terms_df(path2data: str) -> pd.DataFrame:
    thesaurus = {}

    df = pd.read_parquet(path2data)

    texts = df['descr'].to_numpy()
    for i in range(texts.size):
        try:
            texts[i] = texts[i].split('\n')[1] 
        except IndexError:
            continue

    chunks = []
    for text in texts:
        chunks.extend(chunk_text_by_sentences(text=text, target_chunk_size=1000))
    del texts
    print(f"Разбивка на чанки выполнена. Число чанков: {len(chunks)}")

    print("Получение терминов и контекста")
    for chunk in tqdm(chunks):
        try:
            terms = extract_terms(chunk)
        except Exception as e:
            print(f"текст обрабатывался слишком долго: {e}")

        for term in terms:

            if term not in thesaurus:
                thesaurus[term] = {
                    "contexts": [],
                    "definition": None,
                    "type": None
                }

            # ищем контексты
            new_contexts = find_contexts(term, chunk)
            for ctx in new_contexts:
                if ctx not in thesaurus[term]["contexts"]:
                    thesaurus[term]["contexts"].append(ctx)

            # fallback по контекстам
            if len(new_contexts) == 0:
                thesaurus[term]["contexts"].append(chunk)

    df = pd.DataFrame.from_dict(thesaurus, orient='index').reset_index().rename(columns={'index': 'term'})
    return df

if __name__ == "__main__":
    path2data = "data/data2thesaurus.parquet"
    path2save = "thesaurus_data/thesaurus_ctx_final.parquet"

    df = get_terms_df(path2data)

    df.to_parquet(path2save)
    print(f"Результат сохранен по пути: {path2save}")

    
