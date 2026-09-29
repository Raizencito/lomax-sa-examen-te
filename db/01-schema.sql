-- LOMAX SA - Modelo relacional RDS (PostgreSQL)
-- Base: lomax (crear con CREATE DATABASE lomax;)
-- Idempotente y repetible sin duplicar.

CREATE TABLE IF NOT EXISTS categorias (
    categoria_id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS productos (
    producto_id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    precio NUMERIC(10,2) NOT NULL CHECK (precio >= 0),
    categoria_id INTEGER NOT NULL REFERENCES categorias(categoria_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE','PUBLICADO')),
    CONSTRAINT chk_codigo_no_vacio CHECK (length(trim(codigo)) > 0),
    CONSTRAINT chk_nombre_no_vacio CHECK (length(trim(nombre)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_productos_estado ON productos(estado);
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria_id);
CREATE INDEX IF NOT EXISTS idx_productos_codigo ON productos(codigo);
