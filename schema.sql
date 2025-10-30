DROP TABLE IF EXISTS orders;

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL UNIQUE,
    client_email TEXT NOT NULL,
    project_type TEXT NOT NULL,
    budget TEXT,
    timeline TEXT,
    description TEXT NOT NULL,
    quote INTEGER NOT NULL,
    status TEXT NOT NULL,
    payment_method TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);