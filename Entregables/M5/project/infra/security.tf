# Sin puerto 22 abierto a propósito: el acceso a la instancia es por SSM Session Manager
# (permiso en iam.tf), no por SSH. Menos superficie expuesta en una cuenta que ya comparte
# presupuesto y región con otros dos proyectos.

resource "aws_security_group" "app" {
  name        = "${var.project_name}-ec2"
  description = "Servicio de Digitdeck: solo el puerto de la app, nada de SSH"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "API del sistema (POST /preguntar, GET /salud)"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Salida libre: descarga de modelos del HF Hub, pull de ECR, SSM, W&B"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "digitdeck"
  }
}
