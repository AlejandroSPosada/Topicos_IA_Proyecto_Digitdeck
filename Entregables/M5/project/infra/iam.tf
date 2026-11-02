# Rol que asume la instancia EC2 (no credenciales de usuario dentro de la máquina).

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "digitdeck-dev-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

# Acceso por SSM Session Manager en vez de SSH (security.tf no abre el puerto 22).
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Logs y métricas a CloudWatch (criterio "logging estructurado" de la rúbrica de M5).
resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "ec2_inline" {
  statement {
    sid    = "PullDeECR"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  statement {
    # Originalmente solo pull (la instancia iba a bajar una imagen ya construida en local).
    # Confirmado el 2026-11-02: el push local a ECR se trababa en esta red (capa de 7,4 GB sin
    # avanzar incluso tras reiniciar Docker Desktop y WSL2 por completo), así que la instancia
    # también construye y sube su propia imagen — necesita permisos de push, no solo de pull.
    sid    = "PullYPushDelRepoDeDigitdeck"
    effect = "Allow"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  statement {
    sid    = "LeerSecretosDeSSM"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/digitdeck/*",
    ]
  }

  statement {
    sid       = "DescifrarLosSecureString"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alias/aws/ssm"]
  }
}

resource "aws_iam_role_policy" "ec2_inline" {
  name   = "digitdeck-dev-ec2-inline"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_inline.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "digitdeck-dev-ec2"
  role = aws_iam_role.ec2.name
}
