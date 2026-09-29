# E6 - Publicar imagenes en ECR (FLOCI registry en localhost:5100)
$ErrorActionPreference = "Stop"
$ENDPOINT = "http://localhost:4566"
$env:AWS_ACCESS_KEY_ID = "test"; $env:AWS_SECRET_ACCESS_KEY = "test"; $env:AWS_DEFAULT_REGION = "us-east-1"
$REG = "localhost:5100"
$VER = "1.0.0"
foreach ($r in @("lomax-backend", "lomax-frontend", "lomax-proxy")) {
  aws --endpoint-url $ENDPOINT ecr create-repository --repository-name $r 2>&1 | Select-Object -First 5
}
docker build -t "$REG/lomax-backend:$VER" ./backend
docker build -t "$REG/lomax-frontend:$VER" ./frontend
docker build -t "$REG/lomax-proxy:$VER" ./proxy
docker push "$REG/lomax-backend:$VER"
docker push "$REG/lomax-frontend:$VER"
docker push "$REG/lomax-proxy:$VER"
aws --endpoint-url $ENDPOINT ecr describe-images --repository-name lomax-backend
aws --endpoint-url $ENDPOINT ecr describe-images --repository-name lomax-frontend
