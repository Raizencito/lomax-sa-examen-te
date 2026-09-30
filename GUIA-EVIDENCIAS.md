# Guia de evidencias fotograficas - Lomax SA (E1-E7)
Todo se ejecuta en **PowerShell** desde `C:\Users\ALAN\Desktop\LOMAX-EXAMEN-TE`.
FLOCI arriba: `docker start floci floci-ecr-registry`. Credenciales `test/test`.

> Si `--key '{"producto_id":...}'` te da error de JSON (comillas comidas por la consola),
> usa archivo: `'{"producto_id":{"S":"2"}}' | Out-File -Encoding utf8 key.json -NoNewline`
> y luego `--key file://key.json`.

> Si FLOCI se reinicio y las tablas/buckets desaparecen (su almacenamiento es en memoria):
> 1. `aws --endpoint-url $EP rds create-db-instance ...` (mismo comando de E2; si crea contenedor
>    vacio, restaura con `scripts/repair.py` tras aplicar `db/01-schema.sql`);
> 2. `python scripts/repair.py` con las env correspondientes (recrea tabla, buckets,
>    atributos, imagenes y deja PUBLICADO). Ver "Recuperacion" al final.

```powershell
$env:AWS_ACCESS_KEY_ID="test"; $env:AWS_SECRET_ACCESS_KEY="test"
$EP="http://localhost:4566"; $KUB="C:\Users\ALAN\AppData\Local\Temp\lomax\kubeconfig"
```

## E2 - RDS y DynamoDB (fotos de terminal)
```powershell
aws --endpoint-url $EP rds describe-db-instances --query "DBInstances[].{ID:DBInstanceIdentifier,Estado:DBInstanceStatus,IP:Endpoint.Address,Puerto:Endpoint.Port}" --output table
docker run --rm --network bridge -e PGPASSWORD=admin123 postgres:16-alpine psql -h 172.17.0.2 -p 7001 -U admin -d admin -c "SELECT * FROM categorias;"
docker run --rm --network bridge -e PGPASSWORD=admin123 postgres:16-alpine psql -h 172.17.0.2 -p 7001 -U admin -d admin -c "SELECT producto_id,codigo,precio,estado FROM productos ORDER BY producto_id LIMIT 5;"
docker run --rm --network bridge -e PGPASSWORD=admin123 postgres:16-alpine psql -h 172.17.0.2 -p 7001 -U admin -d admin -c "INSERT INTO productos (codigo,nombre,precio,categoria_id) VALUES ('TEC-002','Dup',10,1);"
docker run --rm --network bridge -e PGPASSWORD=admin123 postgres:16-alpine psql -h 172.17.0.2 -p 7001 -U admin -d admin -c "INSERT INTO productos (codigo,nombre,precio,categoria_id) VALUES ('NEG-X','Neg',-5,1);"
docker run --rm --network bridge -e PGPASSWORD=admin123 postgres:16-alpine psql -h 172.17.0.2 -p 7001 -U admin -d admin -c "INSERT INTO productos (codigo,nombre,precio,categoria_id) VALUES ('CAT-X','X',10,9999);"
aws --endpoint-url $EP dynamodb describe-table --table-name lomax-productos --query "Table.{Tabla:TableName,Estado:TableStatus}"
aws --endpoint-url $EP dynamodb get-item --table-name lomax-productos --key '{"producto_id":{"S":"2"}}'
python scripts/check_ids.py http://localhost:8080/api lomax-productos-dev
docker restart lomax-examen-te-postgres-1; Start-Sleep 8; docker exec lomax-examen-te-postgres-1 psql -U admin -d lomax -c "SELECT count(*) FROM productos;"
```
Fotos: cada salida + `evidencias/E2/` (conteo antes/despues iguales).

## E3 - S3 y Lambda (fotos de terminal + 2 archivos)
```powershell
aws --endpoint-url $EP s3 ls
python ./s3-lambda/make_test_images.py
aws --endpoint-url $EP s3 cp s3-lambda/test-1200x800.jpg s3://lomax-originales/originales/TEST-1200.jpg
python -c "import sys; sys.path.insert(0,'s3-lambda'); from lambda_function import lambda_handler; import json; print(json.dumps(lambda_handler({'producto_id':'999','bucket_original':'lomax-originales','key_original':'originales/TEST-1200.jpg','bucket_miniatura':'lomax-miniaturas','dynamodb_table':'lomax-productos-dev'}),indent=2))"
aws --endpoint-url $EP s3 ls s3://lomax-originales/originales/ --recursive
aws --endpoint-url $EP s3 ls s3://lomax-miniaturas/miniaturas/ --recursive
aws --endpoint-url $EP s3 cp s3://lomax-miniaturas/miniaturas/999.jpg E3-thumb.jpg
python -c "from PIL import Image; print('original:', Image.open('s3-lambda/test-1200x800.jpg').size, '| miniatura:', Image.open('E3-thumb.jpg').size)"
aws --endpoint-url $EP dynamodb get-item --table-name lomax-productos-dev --key '{"producto_id":{"S":"999"}}'
# repetir invocacion (misma clave, sin objetos extra) y archivo invalido -> ERROR:
aws --endpoint-url $EP s3 cp s3-lambda/invalido.txt s3://lomax-originales/originales/BAD.txt
```
Fotos: invoke con `"dimensiones":"300x200"`, ambos `ls`, dimensiones PIL, get-item LISTA/ERROR. Adjuntar `evidencias/E3/original-1200x800.jpg` y `thumb-300x200.jpg`. Limpiar: borrar keys TEST-1200.jpg, BAD.txt, item 999.

## E4 - API (foto de terminal + comparacion)
```powershell
python scripts/test_e4b.py http://localhost:8080/api
python -c "a=open('evidencias/E4/img-endpoint.jpg','rb').read(); b=open('evidencias/E4/img-s3.jpg','rb').read(); print('endpoint==s3:', a==b, len(a))"
Invoke-RestMethod http://localhost:8080/api/categorias | ConvertTo-Json -Depth 3
Invoke-RestMethod http://localhost:8080/api/productos/2 | ConvertTo-Json -Depth 4
```
Fotos: `reporte-E4.txt` (201 PENDIENTE, 200 PUBLICADO, 404, 415/413/409 del test inicial) + comparacion `True`.

## E5 - Frontend (fotos de NAVEGADOR + terminal)
1. Abrir http://localhost:8080/registrar : llenar codigo `E5-DEMO-01`, categoria Teclados + atributos, subir JPG -> foto del mensaje y del `producto_id`.
2. Boton "Reintentar/Reprocesar" visible si queda PENDIENTE -> foto.
3. http://localhost:8080/ : foto del catalogo con las tarjetas (miniatura, nombre, precio, categoria).
4. Clic en un producto -> foto del detalle (descripcion + atributos).
5. Repetir con codigo duplicado y con archivo `.txt` -> foto del error en la interfaz.
6. Terminal:
```powershell
docker compose ps
Invoke-RestMethod http://localhost:8080/api/productos | Select-Object -ExpandProperty total
python scripts/check_ids.py http://localhost:8080/api lomax-productos-dev
```

## E6 - ECR (fotos de terminal)
```powershell
aws --endpoint-url $EP ecr describe-repositories --query "repositories[].{repo:repositoryName,uri:repositoryUri}" --output table
docker push localhost:5100/lomax-backend:1.0.0
docker push localhost:5100/lomax-frontend:1.0.0
docker push localhost:5100/lomax-proxy:1.0.0
docker rmi localhost:5100/lomax-backend:1.0.0; docker pull localhost:5100/lomax-backend:1.0.0
docker run --rm localhost:5100/lomax-backend:1.0.0 ls /app/app
docker run --rm localhost:5100/lomax-frontend:1.0.0 ls /usr/share/nginx/html
```
Fotos: cada push con digest, pull `up to date`/descargado, `ls` mostrando `main.py` e `index.html+assets`.

## E7 - EKS (fotos de terminal)
```powershell
$env:KUBECONFIG=$KUB
kubectl get nodes; kubectl get pods -o wide
kubectl scale deployment lomax-backend --replicas=3; Start-Sleep 20; kubectl get pods -l app=lomax-backend
# un pod distinto por puerto (foto de los 3 instance-id):
$pods=kubectl get pods -l app=lomax-backend -o jsonpath='{.items[*].metadata.name}'; $i=0
foreach ($p in $pods.Split(' ')) {$i++; $port=8010+$i; $pf=Start-Process kubectl -ArgumentList 'port-forward',"pod/$p","$port`:8000" -PassThru; Start-Sleep 4; $url='http://localhost:'+$port+'/health'; echo "$p => $((Invoke-RestMethod $url).instance)"; Stop-Process -Id $pf.Id -Force}
kubectl get pods -l app=lomax-backend -o custom-columns=NOMBRE:.metadata.name,UID:.metadata.uid
kubectl delete pod <nombre-victima>; Start-Sleep 15
kubectl get pods -l app=lomax-backend -o custom-columns=NOMBRE:.metadata.name,UID:.metadata.uid,READY:.status.containerStatuses[0].ready
$pf=Start-Process kubectl -ArgumentList 'port-forward','svc/backend','8002:8000' -PassThru; Start-Sleep 5
python scripts/new_product_eks.py http://localhost:8002 EKS-001; Stop-Process -Id $pf.Id -Force
aws --endpoint-url $EP dynamodb get-item --table-name lomax-productos --key '{"producto_id":{"S":"22"}}'
aws --endpoint-url $EP s3 ls s3://lomax-miniaturas/miniaturas/22.jpg
kubectl delete pods -l app=lomax-backend; Start-Sleep 20; kubectl get pods -l app=lomax-backend
# port-forward de nuevo y foto de TOTAL con EKS-001 presente
```
Fotos: 3 Ready, 3 instance-id distintos, UID antes (ej. `ffce33af…`) vs despues (`63600894…`), producto 22 en RDS/Dynamo/S3, catalogo intacto tras recrear pods.

## Recuperacion tras reinicio (FLOCI pierde tablas/buckets/instancias)
```powershell
docker start floci floci-ecr-registry
docker start <contenedor-floci-rds-viejo>   # si existe, conserva los datos
aws --endpoint-url $EP rds create-db-instance --db-instance-identifier lomax-db --db-instance-class db.t3.micro --engine postgres --master-username admin --master-user-password admin123 --allocated-storage 20
# si el proxy apunta a un contenedor nuevo y vacio: aplicar db/01-schema.sql y restaurar datos,
# luego reparar canonico (bridge) y dev (host):
docker run --rm --network bridge -v ${PWD}/scripts:/scripts -e DATABASE_URL=postgresql://admin:admin123@172.17.0.2:7001/admin -e AWS_ENDPOINT_URL=http://172.17.0.2:4566 -e DYNAMODB_TABLE=lomax-productos lomax-backend:1.0.0 python /scripts/repair.py
$env:DATABASE_URL="postgresql://admin:admin123@localhost:5433/lomax"; $env:AWS_ENDPOINT_URL="http://localhost:4566"; $env:DYNAMODB_TABLE="lomax-productos-dev"; python scripts/repair.py
foreach ($r in @("lomax-backend","lomax-frontend","lomax-proxy")) { aws --endpoint-url $EP ecr create-repository --repository-name $r }
docker push localhost:5100/lomax-backend:1.0.0; docker push localhost:5100/lomax-frontend:1.0.0; docker push localhost:5100/lomax-proxy:1.0.0
$env:KUBECONFIG=$KUB; kubectl rollout restart deployment/lomax-backend
```

## E1/P9-P10 (portafolio y repo)
```powershell
git log --oneline; git status --short
gh repo create lomax-sa-examen-te --public --source=. --push
```
Fotos: diagrama de arquitectura (dibujarlo con proxy->frontend/API->RDS/Dynamo/S3/Lambda), tablero de tareas, `git log` por integrante.
