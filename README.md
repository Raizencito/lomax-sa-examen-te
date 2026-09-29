# Lomax SA - Primera evaluacion (FLOCI, credenciales test/test)

Plataforma de registro y consulta de productos: **FastAPI + React + Nginx + RDS (Postgres) + DynamoDB + S3 + Lambda + ECR + EKS (k3s)**.
Estado actual: **21 productos PUBLICADOS** (20 de carga inicial + EKS-001 registrado desde EKS), 3 categorias, 2+ conjuntos de atributos.

## 1. Requisitos
Docker Desktop, Python 3.11+, AWS CLI v2, Node 20 (solo build frontend).
FLOCI corriendo: `docker start floci floci-ecr-registry` (puertos 4566 y 5100).
Credenciales `test/test`, region `us-east-1`, endpoint `http://localhost:4566`.

## 2. Puesta en marcha por etapas
```powershell
cd C:\Users\ALAN\Desktop\LOMAX-EXAMEN-TE
docker start floci floci-ecr-registry

# E2: RDS lomax-db (idempotente) + schema + DynamoDB
aws --endpoint-url http://localhost:4566 rds create-db-instance --db-instance-identifier lomax-db --db-instance-class db.t3.micro --engine postgres --master-username admin --master-user-password admin123 --allocated-storage 20
# aplicar db/01-schema.sql y db/02-seed.sql con psql via contenedor (RDS solo visible dentro de docker):
docker run --rm --network bridge -v ${PWD}/db:/db -e PGPASSWORD=admin123 postgres:16-alpine psql -h 172.17.0.2 -p 7001 -U admin -d admin -f /db/01-schema.sql
docker run --rm --network bridge -v ${PWD}/db:/db -e PGPASSWORD=admin123 postgres:16-alpine psql -h 172.17.0.2 -p 7001 -U admin -d admin -f /db/02-seed.sql
python ./dynamodb/create_table.py                       # tabla lomax-productos
$env:DYNAMODB_TABLE="lomax-productos-dev"; python ./dynamodb/create_table.py   # tabla dev para compose

# E3: S3 + Lambda
aws --endpoint-url http://localhost:4566 s3 mb s3://lomax-originales
aws --endpoint-url http://localhost:4566 s3 mb s3://lomax-miniaturas
python ./s3-lambda/make_test_images.py   # genera test-1200x800.jpg
# La funcion s3-lambda/lambda_function.py se invoca desde el backend (sincrona).
# Si FLOCI no registra la funcion, el backend usa fallback local con IDENTICA logica Pillow.

# E4/E5: compose (backend+postgres-dev, frontend, proxy :8080, frontend :3000)
docker compose up -d --build
docker exec lomax-examen-te-postgres-1 psql -U admin -d lomax -f - < db/01-schema.sql
docker exec lomax-examen-te-postgres-1 psql -U admin -d lomax -f - < db/02-seed.sql
pip install requests pillow boto3
python scripts/seed_20_productos.py http://localhost:8080/api   # 20 PUBLICADOS (TEC-001..008, MON-001..007, AUD-001..005)
python scripts/test_e4b.py http://localhost:8080/api            # reporte E4
python scripts/check_ids.py http://localhost:8080/api lomax-productos-dev   # correspondencia RDS<->Dynamo

# E6: ECR (FLOCI registry localhost:5000->5100)
.\scripts\E6-ecr.ps1

# E7: EKS
aws --endpoint-url http://localhost:4566 eks create-cluster --name lomax-cluster --role-arn arn:aws:iam::000000000000:role/eks-role --resources-vpc-config subnetIds=subnet-default-us-east-1-a
aws --endpoint-url http://localhost:4566 eks update-kubeconfig --name lomax-cluster --kubeconfig k8s/kubeconfig-lomax.yaml
# importar imagenes al k3s (nombres localhost:5100/... con IfNotPresent):
docker save -o backend.tar localhost:5100/lomax-backend:1.0.0
docker cp backend.tar floci-eks-lomax-cluster:/tmp/backend.tar
docker exec floci-eks-lomax-cluster ctr --namespace k8s.io images import /tmp/backend.tar  # repetir frontend/proxy
$env:KUBECONFIG="k8s/kubeconfig-lomax.yaml"
kubectl apply -f k8s/all.yaml
kubectl scale deployment lomax-backend --replicas=3
kubectl port-forward svc/backend 8002:8000
python scripts/new_product_eks.py http://localhost:8002 EKS-001
```

## 3. Decisiones de arquitectura
- **RDS canonico**: instancia FLOCI `lomax-db` (proxy 172.17.0.2:7001, solo alcanzable desde contenedores; user admin/admin123/db admin). El compose trae su propio postgres para demo local (E5) porque el bridge de compose no alcanza el proxy RDS.
- **DynamoDB**: tabla canonica `lomax-productos` <-> `lomax-db`; tabla `lomax-productos-dev` <-> postgres de compose. Separadas para que los `producto_id` de cada RDS correspondan 1:1 sin huerfanos (`scripts/check_ids.py`).
- **S3 compartido**: `lomax-originales` (`originales/{id}.jpg`) y `lomax-miniaturas` (`miniaturas/{id}.jpg` determinista: repetir no crea extras).
- **Lambda**: `s3-lambda/lambda_function.py` valida JPEG/PNG, miniatura max 300x300 proporcional, actualiza Dynamo LISTA/ERROR. El backend la invoca via `lambda:Invoke`; si FLOCI no la tiene registrada usa fallback local identico e informa `"via":"local-fallback"` en el detalle del paso.
- **Publicacion**: solo pasa a PUBLICADO cuando hay atributos en Dynamo + miniatura LISTA verificada con HeadObject en S3.

## 4. Endpoints API (prefijo /api tras el proxy)
GET /categorias | POST /productos (201 PENDIENTE) | POST /productos/{id}/imagen (200 PUBLICADO) |
POST /productos/{id}/reprocesar (409 si no hay original) | GET /productos (solo PUBLICADO) |
GET /productos/{id} (200/404) | GET /productos/{id}/imagen (bytes + Content-Type, 404 si falta).
Errores: 400 entradas invalidas, 409 codigo duplicado, 413 >5MB, 415 formato, 502/503 con `{"paso":"rds|dynamodb|s3|lambda"}`.

## 5. Modelo de datos
RDS: `categorias(categoria_id, nombre UNIQUE, descripcion)`; `productos(producto_id, codigo UNIQUE, nombre, descripcion, precio CHECK>=0, categoria_id FK, fecha, estado PENDIENTE|PUBLICADO)`.
DynamoDB `lomax-productos`: PK `producto_id (S)` = mismo id RDS; `atributos (M)`, `imagen_original_key`, `miniatura_key`, `estado_procesamiento`.
Atributos: Teclados `{conexion, distribucion, retroiluminado}`; Pantallas `{pulgadas, resolucion, tasa_refresco}`; Audifonos `{tipo, conexion, cancelacion_ruido}`.

## 6. Evidencias (carpeta evidencias/)
- **E2**: servicios.txt (rds/dynamodb/s3), conteo-antes/despues.txt (20 = 20 tras restart sin borrar volumenes), restricciones probadas en terminal (duplicado 23505, precio CHECK, FK categoria).
- **E3**: original-1200x800.jpg + thumb-300x200.jpg (1200x800 -> 300x200), repeticion misma clave sin extras, invalido -> ERROR sin miniatura.
- **E4**: reporte-E4.txt, img-endpoint.jpg == img-s3.jpg (comparados byte a byte).
- **E5**: catalogo.json (21 publicados), ids-dev.txt (0 huerfanos), frontend http://localhost:3000 y proxy http://localhost:8080.
- **E6**: repos.txt (3 repos + URIs), imagenes.txt, salidas de push/pull en terminal.
- **E7**: pods.txt (3/3 Ready), scale.txt, svc.txt; escalamiento 1->3 con instance-id por pod; borrado ctlcg (UID ffce33af...) reemplazado por hpxvt (UID 63600894...); EKS-001 (id 22) verificado en RDS/Dynamo/S3 y presente tras recrear los 3 pods.

## 7. Portafolio / GitHub (P10)
```powershell
git init; git add -A; git commit -m "Lomax SA entrega E2-E7"; git branch -M main
gh repo create lomax-sa-examen-te --public --source=. --push
```
Asignar roles por etapa en el tablero y vincular commits por integrante antes de la defensa.
