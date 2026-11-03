#!/usr/bin/env bash
# Redespliega el servicio en la instancia, por SSM y sin push local (ARCHITECTURE.md §9, ADR-11).
#
#   bash redesplegar.sh <sha-completo> <tag-nuevo>   la instancia baja ese commit de GitHub, construye la
#                                                     imagen, la sube a ECR y reinicia el contenedor
#   bash redesplegar.sh --tag <tag-existente>        solo reinicia con una imagen que ya está en ECR
#                                                     (para volver atrás, p. ej. 2026-11-02-frontend)
#
# Los tags de ECR son inmutables (§9, riesgo 11): cada código nuevo necesita un tag que no exista.
# El contenedor se levanta con los mismos flags que user_data.sh.tpl. Mientras carga los cuatro modelos,
# GET /salud no responde ok (unos minutos); este script espera hasta que lo haga.
#
# Credenciales: el perfil de AWS CLI de AWS_PROFILE (por defecto «digitdeck», el usuario que crea
# bootstrap/). En AWS CloudShell, con la consola abierta en la cuenta del proyecto: AWS_PROFILE= bash …
set -euo pipefail

REGION="us-east-1"
INSTANCIA="i-00ca25dc4ee7c3557"
URL_SALUD="http://54.173.61.242:8000/salud"
REPO_GITHUB="AlejandroSPosada/Topicos_IA_Proyecto_Digitdeck"

if [[ "${1:-}" == "--tag" ]]; then
  SHA=""
  TAG="${2:?uso: redesplegar.sh --tag <tag-existente>}"
else
  SHA="${1:?uso: redesplegar.sh <sha-completo> <tag-nuevo>  |  redesplegar.sh --tag <tag-existente>}"
  TAG="${2:?falta el tag nuevo, p. ej. $(date +%F)-frontend}"
  [[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "el sha tiene que ser el completo (40 caracteres): git rev-parse HEAD" >&2; exit 2; }
fi
[[ "$TAG" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "tag inválido: $TAG" >&2; exit 2; }

PERFIL="${AWS_PROFILE-digitdeck}"
aws_() { if [[ -n "$PERFIL" ]]; then aws --profile "$PERFIL" --region "$REGION" "$@"; else env -u AWS_PROFILE aws --region "$REGION" "$@"; fi; }

ESTADO=$(aws_ ec2 describe-instances --instance-ids "$INSTANCIA" --query 'Reservations[0].Instances[0].State.Name' --output text)
[[ "$ESTADO" == "running" ]] || { echo "la instancia está «$ESTADO»: enciéndela primero (aws ec2 start-instances --instance-ids $INSTANCIA)" >&2; exit 1; }

# Lo que corre en la instancia, como root. Sin `set -x`: lee el token de HF y la clave de W&B de SSM y
# la salida de send-command queda guardada en la consola de SSM.
REMOTO=$(cat <<EOF
set -euo pipefail
REGION="$REGION"
SHA="$SHA"
TAG="$TAG"
REPO_GITHUB="$REPO_GITHUB"
EOF
cat <<'EOF'
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRO="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
IMAGEN="$REGISTRO/digitdeck/app:$TAG"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRO" >/dev/null

YA_EXISTE=no
aws ecr describe-images --repository-name digitdeck/app --image-ids imageTag="$TAG" --region "$REGION" >/dev/null 2>&1 && YA_EXISTE=si
if [[ -n "$SHA" ]]; then
  [[ "$YA_EXISTE" == no ]] || { echo "ERROR: el tag $TAG ya existe en ECR (son inmutables); usa otro"; exit 1; }
  TRABAJO=$(mktemp -d)
  trap 'rm -rf "$TRABAJO"' EXIT
  curl -fsSL "https://codeload.github.com/$REPO_GITHUB/tar.gz/$SHA" | tar -xz -C "$TRABAJO"
  SERVICIO=$(find "$TRABAJO" -maxdepth 5 -type d -path '*/Entregables/M5/project/servicio' | head -n1)
  [[ -n "$SERVICIO" && -f "$SERVICIO/Dockerfile" ]] || { echo "ERROR: no encontré servicio/Dockerfile en el commit $SHA"; exit 1; }
  docker build -q -t "$IMAGEN" "$SERVICIO"
  docker push -q "$IMAGEN"
  echo "imagen subida: $IMAGEN (commit $SHA)"
else
  [[ "$YA_EXISTE" == si ]] || { echo "ERROR: el tag $TAG no existe en ECR"; exit 1; }
  docker pull -q "$IMAGEN"
fi

ANTERIOR=$(docker inspect digitdeck --format '{{.Config.Image}}' 2>/dev/null || echo ninguna)
HF_TOKEN=$(aws ssm get-parameter --name /digitdeck/hf_token --with-decryption --region "$REGION" --query Parameter.Value --output text)
WANDB_API_KEY=$(aws ssm get-parameter --name /digitdeck/wandb_api_key --with-decryption --region "$REGION" --query Parameter.Value --output text)
mkdir -p /data/digitdeck/indices
docker rm -f digitdeck >/dev/null 2>&1 || true
docker run -d \
  --name digitdeck \
  --restart unless-stopped \
  --gpus all \
  -p 8000:8000 \
  -v /data/digitdeck/indices:/app/indices \
  -e HF_TOKEN="$HF_TOKEN" \
  -e WANDB_API_KEY="$WANDB_API_KEY" \
  -e WANDB_PROJECT="digitdeck-m5" \
  -e APP_PORT="8000" \
  --log-driver=awslogs \
  --log-opt awslogs-region="$REGION" \
  --log-opt awslogs-group=/digitdeck/app \
  --log-opt awslogs-create-group=true \
  "$IMAGEN" >/dev/null
echo "contenedor reiniciado: antes $ANTERIOR, ahora $IMAGEN"
EOF
)

B64=$(printf '%s\n' "$REMOTO" | base64 | tr -d '\n')
ID=$(aws_ ssm send-command --instance-ids "$INSTANCIA" --document-name AWS-RunShellScript \
  --comment "redesplegar ${TAG}" --timeout-seconds 1800 \
  --parameters "{\"commands\":[\"echo $B64 | base64 -d > /tmp/redesplegar.sh && bash /tmp/redesplegar.sh; S=\$?; rm -f /tmp/redesplegar.sh; exit \$S\"],\"executionTimeout\":[\"1800\"]}" \
  --query Command.CommandId --output text)
echo "send-command $ID enviado; la instancia construye y reinicia (puede tardar varios minutos)…"

while :; do
  sleep 10
  E=$(aws_ ssm get-command-invocation --command-id "$ID" --instance-id "$INSTANCIA" --query Status --output text 2>/dev/null || echo Pending)
  case "$E" in Pending|InProgress|Delayed|Cancelling) continue ;; esac
  break
done
aws_ ssm get-command-invocation --command-id "$ID" --instance-id "$INSTANCIA" --query '[StandardOutputContent,StandardErrorContent]' --output text
[[ "$E" == "Success" ]] || { echo "send-command terminó en «$E»: el contenedor anterior puede haber quedado detenido; vuelve con --tag <tag-anterior>" >&2; exit 1; }

echo "esperando a que GET /salud responda ok (carga de los cuatro modelos)…"
for _ in $(seq 1 60); do
  if curl -fsS -m 10 "$URL_SALUD" 2>/dev/null | grep -q '"ok":true'; then
    echo "listo: $(curl -fsS -m 10 "$URL_SALUD")"
    exit 0
  fi
  sleep 10
done
echo "GET /salud no respondió ok en 10 minutos; revisa los logs en CloudWatch (/digitdeck/app)" >&2
exit 1
