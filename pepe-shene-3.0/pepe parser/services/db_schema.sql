-- services/db_schema.sql

-- Таблица сессий анализа
CREATE TABLE IF NOT EXISTS analysis_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    excel_filename TEXT NOT NULL,
    json_filename TEXT,
    analysis_filename TEXT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_products INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    status TEXT DEFAULT 'completed',
    session_data TEXT
);

-- Таблица продуктов
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_session_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    product_code TEXT,
    quantity REAL DEFAULT 0,
    revenue REAL DEFAULT 0,
    abc_category TEXT,
    xyz_category TEXT,
    abc_xyz_category TEXT,
    revenue_share REAL,
    cumulative_share REAL,
    rank INTEGER,
    category TEXT,
    FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE
);

-- Таблица статистики категорий
CREATE TABLE IF NOT EXISTS category_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_session_id INTEGER NOT NULL,
    category_type TEXT NOT NULL,
    category_name TEXT NOT NULL,
    products_count INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    revenue_percentage REAL DEFAULT 0,
    FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    UNIQUE(analysis_session_id, category_type, category_name)
);

-- Таблица матрицы
CREATE TABLE IF NOT EXISTS matrix_cells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_session_id INTEGER NOT NULL,
    abc_category TEXT NOT NULL,
    xyz_category TEXT NOT NULL,
    products_count INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    avg_revenue REAL DEFAULT 0,
    min_revenue REAL DEFAULT 0,
    max_revenue REAL DEFAULT 0,
    recommendation TEXT,
    FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    UNIQUE(analysis_session_id, abc_category, xyz_category)
);

-- Таблица графиков
CREATE TABLE IF NOT EXISTS charts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_session_id INTEGER NOT NULL,
    chart_type TEXT NOT NULL,
    chart_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    UNIQUE(analysis_session_id, chart_type)
);

-- Индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_products_session ON products(analysis_session_id);
CREATE INDEX IF NOT EXISTS idx_products_abc ON products(abc_category);
CREATE INDEX IF NOT EXISTS idx_products_xyz ON products(xyz_category);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON analysis_sessions(upload_date);