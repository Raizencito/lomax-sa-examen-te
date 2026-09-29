"""
Esquema DynamoDB - Lomax SA
Tabla: lomax-productos
  PK: producto_id (S)  -> mismo identificador de RDS (string del entero)
  Atributos:
    atributos (M: {str: str})  -> variables por categoria
    imagen_original_key (S, opcional)
    miniatura_key (S, opcional)
    estado_procesamiento (S): PENDIENTE | LISTA | ERROR
    actualizado_en (S ISO8601)

Dos conjuntos distintos de atributos (ejemplo):
  Teclados (cat 1): {conexion, distribucion, retroiluminado}
  Pantallas (cat 2): {pulgadas, resolucion, tasa_refresco}
  Audifonos (cat 3): {tipo, conexion, cancelacion_ruido}
"""
TABLE_NAME = "lomax-productos"
KEY_SCHEMA = [{"AttributeName": "producto_id", "KeyType": "HASH"}]
ATTR_DEFS = [{"AttributeName": "producto_id", "AttributeType": "S"}]
BILLING = "PAY_PER_REQUEST"
