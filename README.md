# Medical Rounds Search System

Система для семантического поиска по врачебным обходам пациентов после трансплантации костного мозга.  
Использует **LLM** (через Ollama) для извлечения терминов из запросов, векторное сходство (pgvector) и кластеризацию синонимов.  
Frontend на React с возможностью фильтрации, сортировки и управления тезаурусом.

---

## Технологии

### Backend
- **FastAPI** – асинхронное REST API
- **PostgreSQL + pgvector** – хранение данных и векторный поиск
- **Ollama** – локальные LLM (для извлечения терминов, валидации)
- **Asyncpg** – асинхронное подключение к БД
- **Sentence‑Transformers** – эмбеддинги для семантического поиска (e5‑large)

### Frontend
- **React 18** – пользовательский интерфейс
- **Axios** – HTTP‑клиент
- **CSS** – адаптивный дизайн

---

## Структура проекта

```
.
├── med_api/                # Backend FastAPI
│   ├── app/
│   │   ├── routers/        # Эндпоинты (search, thesaurus)
│   │   ├── database.py     # Подключение к БД
│   │   ├── llm_client.py   # Общение с Ollama
│   │   ├── embedd_search.py # Векторный поиск (E5)
│   │   ├── query_processor.py # Обработка запроса → кластеры
│   │   ├── search_engine.py   # Поиск и расчёт score
│   │   ├── schemas.py      # Pydantic модели
│   │   └── main.py         # Точка входа
|   ├── tests/               # pytest тесты API
│   ├── requirements.txt
│   └── Dockerfile          (опционально)
├── frontend/               # React‑приложение
│   ├── public/
│   ├── src/
│   │   ├── components/     # SearchBar, ResultsTable, ThesaurusManager
│   │   ├── api.js
│   │   ├── App.js
│   │   └── index.js
│   ├── package.json
│   └── .env
├── data/                   # Исходные данные (parquet)
│   ├── thesaurus.parquet
│   ├── corpus.parquet
│   └── indexed_rounds.parquet  # после индексации
├── scripts/                # Скрипты индексации и загрузки
│   ├── load_to_postgres.py
│   └── index_corpus_v2.py
├── database/   
│   └── init.sql # начальный скрипт настройки БД
├── docker-compose.yml
└── README.md
```

---


### 1. Настройка базы данных

Запустите БД через docker:
```bash
docker-compose up -d
```

### 2. Backend

```bash
cd med_api
python -m venv venv
source venv/bin/activate  # или .\venv\Scripts\activate на Windows
pip install -r requirements.txt
```

Создайте файл `.env`:
```ini
DB_HOST=localhost
DB_PORT=5432
DB_NAME=medical_db
DB_USER=medical_user
DB_PASSWORD=medical_password
LLM_API_URL=http://localhost:11434/api/generate
LLM_MODEL=qwen2.5:14b
EMBEDDING_MODEL=intfloat/multilingual-e5-large
```

Запустите сервер:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # настройте REACT_APP_API_URL=http://localhost:8000
npm start
```

Откройте `http://localhost:3000`.

---

##  API Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/search/` | Поиск обходов по естественному запросу. Параметр `threshold` (0..1). |
| POST | `/api/thesaurus/search` | Поиск терминов в тезаурусе (ILIKE). |
| POST | `/api/thesaurus/suggest` | Предложить изменение (сохраняется в `data/thesaurus_edit_requests.parquet`). |
| POST | `/api/thesaurus/add` | Добавить новый термин (сразу в БД и файл `thesaurus.parquet`). |
| GET  | `/api/thesaurus/suggestions` | Просмотр предложений. |
| GET  | `/health` | Проверка работоспособности. |

> Пример запроса поиска:
```bash
curl -X POST "http://localhost:8000/api/search/" \
  -H "Content-Type: application/json" \
  -d '{"query": "пациенты с анемией и мукозитом"}' \
  -G -d threshold=0.6
```

Полная документация в SwaggerUI: [Яндекс Диск](https://disk.yandex.ru/d/RDI-YzDvYgMmaw)
Посмотреть  можно через [redocly](https://redocly.github.io/redoc/)

---

## Индексация корпуса и получение тезауруса

Если вы имеете исходные parquet‑файлы (`corpus.parquet`, `thesaurus.parquet`), выполните:

```bash
# Полный пайплайн со значениями по умолчанию
python main.py

# С пропуском этапа дедупликации и добавлением unmatched терминов
python main.py --skip_deduplicate --add_unmatched --indexed_corpus_for_unmatched data/indexed_rounds_small_final.parquet

# Только индексация (с использованием уже готового тезауруса)
python main.py --skip_build_thesaurus --skip_generate_definitions --skip_generate_embeddings --skip_deduplicate
```



