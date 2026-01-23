-- Упрощенная таблица analysis (только ABC/XYZ)
CREATE TABLE analysis (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES store(id) ON DELETE CASCADE,
    product_name VARCHAR(200) NOT NULL,
    abc_category CHAR(1) NOT NULL CHECK (abc_category IN ('A', 'B', 'C')),
    xyz_category CHAR(1) NOT NULL CHECK (xyz_category IN ('X', 'Y', 'Z')),
    abc_xyz_category VARCHAR(2) NOT NULL,
    revenue DECIMAL(15, 2) NOT NULL,
    analysis_date DATE DEFAULT CURRENT_DATE
);

-- Индексы
CREATE INDEX idx_analysis_store_id ON analysis(store_id);
CREATE INDEX idx_analysis_abc ON analysis(abc_category);
CREATE INDEX idx_analysis_xyz ON analysis(xyz_category);
CREATE INDEX idx_analysis_abc_xyz ON analysis(abc_xyz_category);