# AMI oficial de AWS con el driver NVIDIA, CUDA y Docker ya configurados para --gpus all.
# El nombre cambió con el tiempo (antes "Deep Learning AMI GPU PyTorch ... (Ubuntu 22.04)"; hoy
# "Deep Learning OSS Nvidia Driver AMI GPU PyTorch ... (Ubuntu 24.04)", confirmado el 2026-11-02
# con `aws ec2 describe-images`). El filtro de arquitectura es explícito porque el mismo prefijo
# de nombre también existe en variantes ARM64 (g5.xlarge es x86_64).
data "aws_ami" "deep_learning" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning OSS Nvidia Driver AMI GPU PyTorch * (Ubuntu 24.04)*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# Los dos secretos que el contenedor necesita en arranque. SecureString, no texto plano:
# Parameter Store estándar es gratis (a diferencia de Secrets Manager, ~0,40 USD/secreto/mes).
resource "aws_ssm_parameter" "hf_token" {
  name  = "/digitdeck/hf_token"
  type  = "SecureString"
  value = var.hf_token
  tags  = { Project = "digitdeck" }
}

resource "aws_ssm_parameter" "wandb_api_key" {
  name  = "/digitdeck/wandb_api_key"
  type  = "SecureString"
  value = var.wandb_api_key
  tags  = { Project = "digitdeck" }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.deep_learning.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnet.chosen.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size_gb
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    aws_region         = var.aws_region
    account_id         = data.aws_caller_identity.current.account_id
    ecr_repository_url = aws_ecr_repository.app.repository_url
    image_tag          = var.image_tag
    app_port           = var.app_port
  })

  # El HF token y el de W&B se leen en cada arranque vía SSM (user_data), así que si
  # cambian solo hace falta reiniciar la instancia, no recrearla.
  user_data_replace_on_change = true

  tags = {
    Name    = "${var.project_name}-app"
    Project = "digitdeck"
  }

  depends_on = [
    aws_ssm_parameter.hf_token,
    aws_ssm_parameter.wandb_api_key,
  ]
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = {
    Name    = "${var.project_name}-app"
    Project = "digitdeck"
  }
}
