variable "aws_region" {
  description = "Región de AWS para el estado remoto"
  type        = string
  default     = "us-east-1"
}

variable "bootstrap_aws_profile" {
  description = "Perfil de AWS CLI con el que se corre este bootstrap (las llaves root que ya hay en WSL: default o campus-admin). Solo se usa esta vez."
  type        = string
  default     = "default"
}
