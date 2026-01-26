-- Упрощенная таблица store (только то, что есть в JSON)
CREATE TABLE store (
    id INTEGER PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    revenue DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX idx_store_product_name ON store(product_name);
CREATE INDEX idx_store_revenue ON store(revenue DESC);
