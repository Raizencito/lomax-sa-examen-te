-- LOMAX SA - Carga inicial: 3 categorias (idempotente)
INSERT INTO categorias (categoria_id, nombre, descripcion) VALUES
  (1, 'Teclados', 'Teclados mecanicos, membrana e inalambricos'),
  (2, 'Pantallas', 'Monitores y pantallas de distintas pulgadas y resolucion'),
  (3, 'Audifonos', 'Audifonos gamer y de oficina con distintas conexiones')
ON CONFLICT (categoria_id) DO UPDATE SET nombre=EXCLUDED.nombre, descripcion=EXCLUDED.descripcion;

-- Alinear secuencias por si se re-ejecuta
SELECT setval('categorias_categoria_id_seq', (SELECT MAX(categoria_id) FROM categorias));
SELECT setval('productos_producto_id_seq', (SELECT COALESCE(MAX(producto_id),1) FROM productos));
