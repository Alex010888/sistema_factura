-- ==========================================================
-- 🧾 SISTEMA DE FACTURACIÓN ELECTRÓNICA - ESTRUCTURA SQL
-- Generado automáticamente a partir de modelos SQLAlchemy
-- ==========================================================
CREATE DATABASE IF NOT EXISTS facturacion CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE facturacion;

-- ==========================================================
-- 🧍 TABLA DE USUARIOS
-- ==========================================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'empleado',
    status SMALLINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ==========================================================
-- 👥 TABLA DE CLIENTES
-- ==========================================================
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    dui VARCHAR(15),
    nit VARCHAR(20),
    email VARCHAR(100),
    phone VARCHAR(20),
    address VARCHAR(255),
    status SMALLINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ==========================================================
-- 📦 TABLA DE PRODUCTOS
-- ==========================================================
CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) UNIQUE,
    name VARCHAR(200) NOT NULL,
    price FLOAT NOT NULL DEFAULT 0.0,
    cost FLOAT NOT NULL DEFAULT 0.0,
    tax FLOAT NOT NULL DEFAULT 13.0,
    image_path VARCHAR(255),
    category_id INT,
    CONSTRAINT fk_products_category FOREIGN KEY (category_id)
    REFERENCES categories(id)
    ON DELETE SET NULL ON UPDATE CASCADE

);

-- ==========================================================
-- 🏬 TABLA DE INVENTARIO (STOCK)
-- ==========================================================
CREATE TABLE stock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    qty DECIMAL(12,3) DEFAULT 0,
    location_id INT DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_product FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ==========================================================
-- 🧾 TABLA DE VENTAS (POS)
-- ==========================================================
CREATE TABLE sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sale_number VARCHAR(50) UNIQUE,
    user_id INT NOT NULL,
    customer_id INT,
    total DECIMAL(12,2) DEFAULT 0,
    paid_with VARCHAR(50) DEFAULT 'EFECTIVO',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_sales_user FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_sales_customer FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- ==========================================================
-- 🧮 TABLA DETALLE DE VENTAS
-- ==========================================================
CREATE TABLE sale_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    qty DECIMAL(12,3) DEFAULT 1,
    price DECIMAL(10,2) DEFAULT 0,
    tax DECIMAL(5,2) DEFAULT 0,
    subtotal DECIMAL(12,2) DEFAULT 0,
    CONSTRAINT fk_sale_items_sale FOREIGN KEY (sale_id) REFERENCES sales(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_sale_items_product FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ==========================================================
-- 🧾 TABLA FACTURAS ELECTRÓNICAS
-- ==========================================================
CREATE TABLE invoices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    customer_id INT NOT NULL,
    user_id INT NOT NULL,
    date DATETIME DEFAULT CURRENT_TIMESTAMP,
    subtotal FLOAT NOT NULL DEFAULT 0.0,
    tax_total FLOAT NOT NULL DEFAULT 0.0,
    total FLOAT NOT NULL DEFAULT 0.0,
    CONSTRAINT fk_invoices_customer FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_invoices_user FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ==========================================================
-- 🧾 TABLA DETALLE DE FACTURAS ELECTRÓNICAS
-- ==========================================================
CREATE TABLE invoice_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invoice_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity FLOAT NOT NULL,
    price FLOAT NOT NULL,
    subtotal FLOAT NOT NULL,
    CONSTRAINT fk_invoice_items_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_invoice_items_product FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ==========================================================
-- ✅ DATOS INICIALES
-- ==========================================================
INSERT INTO users (username, password_hash, role) VALUES
('admin', 'admin', 'admin');

-- Crear cliente por defecto
INSERT INTO customers (name) VALUES ('Consumidor Final');

-- ==========================================================
-- 🔚 FIN DE SCRIPT
-- ==========================================================
-- ==========================================================
-- 🏷️ TABLA DE CATEGORÍAS
-- ==========================================================
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Insertar categorías iniciales
INSERT INTO categories (name) VALUES
('Domo'),
('Tostado'),
('Galleta'),
('Empacado'),
('Sin Empaque'),
('Varios');
