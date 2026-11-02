# Se reutiliza la VPC por defecto de la cuenta (vpc-091423326c0dfe406, confirmado el
# 2026-11-01): es una sola instancia pública, sin backend privado que necesite NAT Gateway.
# 4U_project sí construyó una VPC propia con subredes privadas porque tiene un backend, un
# worker y RDS; aquí no aplica ese costo ni esa complejidad.

data "aws_vpc" "default" {
  default = true
}

# No toda zona de disponibilidad ofrece el tipo de instancia elegido (confirmado el 2026-11-02:
# us-east-1e no tiene g5.xlarge, aunque sí estaba entre las subredes por defecto). Se cruza contra
# las zonas que sí lo ofrecen en vez de tomar la primera subred al azar.
data "aws_ec2_instance_type_offerings" "gpu" {
  filter {
    name   = "instance-type"
    values = [var.instance_type]
  }
  location_type = "availability-zone"
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

  filter {
    name   = "availability-zone"
    values = data.aws_ec2_instance_type_offerings.gpu.locations
  }
}

data "aws_subnet" "chosen" {
  id = data.aws_subnets.default.ids[0]
}
