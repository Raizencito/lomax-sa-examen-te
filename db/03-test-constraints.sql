-- Pruebas de restricciones E2 (RDS). Ejecutar despues de schema+seed.
-- 1. Insercion valida
INSERT INTO productos (codigo, nombre, descripcion, precio, categoria_id, estado)
VALUES ('LOMAX-TEST-001','Teclado Prueba','Valido', 99.99, 1, 'PENDIENTE')
ON CONFLICT (codigo) DO NOTHING
RETURNING producto_id, codigo, estado;

-- 2. Codigo duplicado (debe fallar 23505). Descomentar para probar:
-- INSERT INTO productos (codigo, nombre, precio, categoria_id) VALUES ('LOMAX-TEST-001','Duplicado', 10.00, 1);

-- 3. Precio negativo (debe fallar CHECK). Descomentar para probar:
-- INSERT INTO productos (codigo, nombre, precio, categoria_id) VALUES ('LOMAX-NEG-001','Negativo', -5.00, 1);

-- 4. Categoria inexistente (debe fallar FK 23503). Descomentar para probar:
-- INSERT INTO productos (codigo, nombre, precio, categoria_id) VALUES ('LOMAX-CAT-001','SinCategoria', 10.00, 9999);

-- Limpieza del registro de prueba (para repetir sin duplicar):
-- DELETE FROM productos WHERE codigo='LOMAX-TEST-001';
