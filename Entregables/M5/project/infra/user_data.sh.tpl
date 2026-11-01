#!/bin/bash
# Arranque de la instancia: trae la imagen de ECR y levanta el contenedor del servicio.
# La Deep Learning AMI ya trae Docker y el NVIDIA Container Toolkit configurados.
set -euxo pipefail

REGION="${aws_region}"
ACCOUNT_ID="${account_id}"
ECR_REPO="${ecr_repository_url}"
IMAGE_TAG="${image_tag}"
APP_PORT="${app_port}"

if ! command -v aws >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y awscli
fi

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

HF_TOKEN=$(aws ssm get-parameter --name /digitdeck/hf_token --with-decryption --region "$REGION" --query Parameter.Value --output text)
WANDB_API_KEY=$(aws ssm get-parameter --name /digitdeck/wandb_api_key --with-decryption --region "$REGION" --query Parameter.Value --output text)

docker pull "$ECR_REPO:$IMAGE_TAG"

docker rm -f digitdeck 2>/dev/null || true

docker run -d \
  --name digitdeck \
  --restart unless-stopped \
  --gpus all \
  -p "$APP_PORT:$APP_PORT" \
  -e HF_TOKEN="$HF_TOKEN" \
  -e WANDB_API_KEY="$WANDB_API_KEY" \
  -e WANDB_PROJECT="digitdeck-m5" \
  -e APP_PORT="$APP_PORT" \
  --log-driver=awslogs \
  --log-opt awslogs-region="$REGION" \
  --log-opt awslogs-group=/digitdeck/app \
  --log-opt awslogs-create-group=true \
  "$ECR_REPO:$IMAGE_TAG"
