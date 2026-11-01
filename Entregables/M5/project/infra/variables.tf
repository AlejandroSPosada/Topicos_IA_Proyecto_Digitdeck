variable "aws_region" {
  description = "Región de AWS"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Perfil de AWS CLI — el usuario IAM dedicado creado en bootstrap/, no las llaves root"
  type        = string
  default     = "digitdeck"
}

variable "project_name" {
  description = "Prefijo para nombrar todos los recursos de este stack"
  type        = string
  default     = "digitdeck-dev"
}

variable "instance_type" {
  description = "Tipo de instancia EC2 con GPU. g5.xlarge = A10G, 24 GB VRAM, ~1,01 USD/h on-demand (us-east-1, confirmado con la API de precios el 2026-11-01)"
  type        = string
  default     = "g5.xlarge"
}

variable "root_volume_size_gb" {
  description = "Tamaño del volumen raíz (gp3). Los 4 modelos en fp16 pesan ~14 GB; el resto es SO, CUDA, imagen Docker e índice del catálogo"
  type        = number
  default     = 150
}

variable "app_port" {
  description = "Puerto donde escucha el servicio FastAPI (POST /preguntar, GET /salud)"
  type        = number
  default     = 8000
}

variable "image_tag" {
  description = "Tag de la imagen en ECR que se despliega"
  type        = string
  default     = "latest"
}

variable "hf_token" {
  description = "Token de Hugging Face con acceso de lectura al repo privado del encoder de M1 (digitdeck/e5-small-finetuned-esci). Se guarda en SSM Parameter Store, nunca en el estado en texto plano ni en el código"
  type        = string
  sensitive   = true
}

variable "wandb_api_key" {
  description = "API key de Weights & Biases para que el servicio registre cada pregunta en el proyecto digitdeck-m5"
  type        = string
  sensitive   = true
}

variable "budget_limit_usd" {
  description = "Tope mensual del presupuesto propio de Digitdeck (independiente del compartido de 100 USD/mes de 4U_project/TrendAnalyzer)"
  type        = number
  default     = 40
}

variable "budget_alert_email" {
  description = "A quién le llega la alerta de presupuesto (80% real, 100% proyectado). Sin default a propósito: no se versiona un correo del equipo en el código"
  type        = string
}
