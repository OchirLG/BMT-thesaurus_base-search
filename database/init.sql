-- Включаем расширение pgvector
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE gender_type AS ENUM ('M', 'F');

-- Первая таблица: врачебные обходы
CREATE TABLE medical_rounds (
    id SERIAL PRIMARY KEY,
    reg_id VARCHAR(50) NOT NULL,
    birth_year INTEGER,
    gender gender_type,
    case_id VARCHAR(50),
    timestamp TIMESTAMP,
    bmt_days INTEGER,
    bmt_timestamp TIMESTAMP,
    descr TEXT
);

-- Индексы для первой таблицы
CREATE INDEX idx_medical_rounds_reg_id ON medical_rounds(reg_id);
CREATE INDEX idx_medical_rounds_case_id ON medical_rounds(case_id);
CREATE INDEX idx_medical_rounds_timestamp ON medical_rounds(timestamp);
CREATE INDEX idx_medical_rounds_bmt_days ON medical_rounds(bmt_days);

-- Вторая таблица: тезаурус
CREATE TABLE thesaurus (
    id SERIAL PRIMARY KEY,
    term VARCHAR(383) NOT NULL UNIQUE,
    expansion TEXT,
    definition TEXT,
    embedding vector(1024)
);

-- Индексы для второй таблицы (включая векторный индекс)
CREATE INDEX idx_thesaurus_term ON thesaurus(term);
CREATE INDEX idx_thesaurus_embedding ON thesaurus USING ivfflat (embedding vector_cosine_ops);

-- Третья таблица: связь обходов с терминами
CREATE TABLE round_terms (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES medical_rounds(id) ON DELETE CASCADE,
    term_id INTEGER NOT NULL REFERENCES thesaurus(id) ON DELETE CASCADE,
    is_negated BOOLEAN DEFAULT FALSE,
    UNIQUE(round_id, term_id)
);

-- Индексы для третьей таблицы
CREATE INDEX idx_round_terms_round_id ON round_terms(round_id);
CREATE INDEX idx_round_terms_term_id ON round_terms(term_id);


-- Комментарии к таблицам и колонкам
COMMENT ON TABLE medical_rounds IS 'Данные врачебных обходов пациентов после трансплантации костного мозга';
COMMENT ON COLUMN medical_rounds.reg_id IS 'Уникальный id пациента';
COMMENT ON COLUMN medical_rounds.bmt_days IS 'Дней после трансплантации';
COMMENT ON COLUMN medical_rounds.descr IS 'Описание состояния пациента';

COMMENT ON TABLE thesaurus IS 'Тезаурус медицинских терминов с векторными эмбеддингами';
COMMENT ON COLUMN thesaurus.expansion IS 'Расшифровка или каноническое написание термина';

COMMENT ON TABLE round_terms IS 'Связь между обходами и терминами из тезауруса';

-- Пример вставки тестовых данных
-- INSERT INTO medical_rounds (reg_id, birth_year, gender, case_id, timestamp, bmt_days, bmt_timestamp, descr)
-- VALUES 
--     ('REG001', 1985, 'M', 'CASE001', '2024-01-15 10:00:00', 30, '2023-12-16', 'Пациент стабилен, без признаков РТПХ'),
--     ('REG002', 1990, 'F', 'CASE002', '2024-01-16 14:30:00', 45, '2023-12-02', 'Отмечается легкая тошнота, аппетит сохранен');

-- -- Пример вставки терминов
-- INSERT INTO thesaurus (term, expansion, definition) VALUES
--     ('РТПХ', 'Реакция "трансплантат против хозяина"', 'Осложнение после трансплантации, при котором донорские клетки атакуют организм реципиента'),
--     ('ТКМ', 'Трансплантация костного мозга', 'Процедура пересадки стволовых клеток крови'),
--     ('нейтропения', NULL, 'Снижение уровня нейтрофилов в крови');

-- -- Связываем обходы с терминами
-- INSERT INTO round_terms (round_id, term_id) VALUES
--     (1, 1), -- Обход 1 связан с термином РТПХ
--     (2, 2); -- Обход 2 связан с термином ТКМ

-- Функция для поиска похожих терминов по эмбеддингу
CREATE OR REPLACE FUNCTION find_similar_terms(
    embedding_vector vector(1024),
    limit_count INTEGER DEFAULT 5
)
RETURNS TABLE(
    term_id INTEGER,
    term VARCHAR,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        t.term,
        1 - (t.embedding <=> embedding_vector) AS similarity
    FROM thesaurus t
    WHERE t.embedding IS NOT NULL
    ORDER BY t.embedding <=> embedding_vector
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;