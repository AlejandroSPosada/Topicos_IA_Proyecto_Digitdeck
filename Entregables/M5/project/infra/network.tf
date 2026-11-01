# Se reutiliza la VPC por defecto de la cuenta (vpc-091423326c0dfe406, confirmado el
# 2026-11-01): es una sola instancia pública, sin backend privado que necesite NAT Gateway.
# 4U_project sí construyó una VPC propia con subredes privadas porque tiene un backend, un
# worker y RDS; aquí no aplica ese costo ni esa complejidad.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

data "aws_subnet" "chosen" {
  id = data.aws_subnets.default.ids[0]
}
