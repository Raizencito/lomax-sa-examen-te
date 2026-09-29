# E3 - S3 + Lambda (FLOCI)
$ErrorActionPreference = "Stop"
$ENDPOINT = "http://localhost:4566"
$env:AWS_ACCESS_KEY_ID = "test"; $env:AWS_SECRET_ACCESS_KEY = "test"; $env:AWS_DEFAULT_REGION = "us-east-1"
aws --endpoint-url $ENDPOINT s3 mb s3://lomax-originales 2>&1
aws --endpoint-url $ENDPOINT s3 mb s3://lomax-miniaturas 2>&1
Write-Host "== Empaquetando lambda =="
Compress-Archive -Force -Path ./s3-lambda/lambda_function.py -DestinationPath ./s3-lambda/func.zip
aws --endpoint-url $ENDPOINT lambda create-function --function-name lomax-thumbnail `
  --runtime python3.11 --role arn:aws:iam::000000000000:role/lambda-exec --handler lambda_function.lambda_handler `
  --zip-file fileb://s3-lambda/func.zip 2>&1 | Select-Object -First 20
Write-Host "Si create-function falla en FLOCI (runtime no soportado), el backend usa fallback local con identica logica Pillow."
Write-Host "== Imagen de prueba 1200x800 =="
python ./s3-lambda/make_test_images.py
