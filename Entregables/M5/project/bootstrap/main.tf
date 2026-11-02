terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Sin backend remoto a propósito: este stack crea el bucket que usará infra/
  # como backend, así que su propio estado tiene que quedarse local.
}

provider "aws" {
  region  = var.aws_region
  profile = var.bootstrap_aws_profile
}

data "aws_caller_identity" "current" {}

# --- Estado remoto para infra/ ---

resource "aws_s3_bucket" "tfstate" {
  bucket = "digitdeck-tfstate-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tfstate_lock" {
  name         = "digitdeck-tfstate-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

# --- IAM dedicado para el Terraform de infra/ (no usa las llaves root) ---

resource "aws_iam_user" "terraform" {
  name = "digitdeck-terraform"
}

# A propósito NO se crea aws_iam_access_key aquí: esa llave quedaría en texto
# plano dentro de este tfstate local. Se genera a mano en la consola de AWS
# (IAM > Users > digitdeck-terraform > Security credentials), una sola vez.
# Ver bootstrap/README.md paso 3.

resource "aws_iam_policy" "terraform" {
  name        = "digitdeck-terraform-policy"
  description = "Permisos para que Terraform despliegue Entregables/M5/project/infra"
  policy      = data.aws_iam_policy_document.terraform.json
}

resource "aws_iam_user_policy_attachment" "terraform" {
  user       = aws_iam_user.terraform.name
  policy_arn = aws_iam_policy.terraform.arn
}

data "aws_iam_policy_document" "terraform" {
  # EC2, ECR, Budgets y Service Quotas no tienen permisos a nivel de recurso
  # para las acciones de creación, así que quedan en "*"; el resto se acota
  # a nombres que empiecen por "digitdeck" o al bucket/tabla de este stack.
  statement {
    sid    = "ComputeYRegistro"
    effect = "Allow"
    actions = [
      "ec2:*",
      "ecr:*",
      "budgets:*",
      "servicequotas:Get*",
      "servicequotas:List*",
      "ce:GetCostAndUsage",
      "sts:GetCallerIdentity",
      "pricing:GetProducts",
      # ssm:DescribeParameters no admite acotarse por ARN de parámetro (AWS la exige a nivel de
      # cuenta, confirmado el 2026-11-02 al aplicar infra/: AccessDeniedException sobre "ssm:*").
      "ssm:DescribeParameters",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "IAMParaElRolDeLaInstancia"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:PassRole",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:CreateInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:GetInstanceProfile",
      "iam:TagRole",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/digitdeck-*",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/digitdeck-*",
    ]
  }

  statement {
    sid    = "ParametrosDeSecretos"
    effect = "Allow"
    actions = [
      "ssm:PutParameter",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:DeleteParameter",
      "ssm:AddTagsToResource",
      "ssm:ListTagsForResource",
    ]
    resources = [
      "arn:aws:ssm:*:${data.aws_caller_identity.current.account_id}:parameter/digitdeck/*",
    ]
  }

  statement {
    sid    = "EstadoRemoto"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.tfstate.arn,
      "${aws_s3_bucket.tfstate.arn}/*",
    ]
  }

  statement {
    sid    = "CandadoDelEstado"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [aws_dynamodb_table.tfstate_lock.arn]
  }

  # Faltaba por completo: digitdeck-terraform podía desplegar la instancia pero no entrar a
  # ella. Confirmado el 2026-11-02 con AccessDeniedException en ssm:DescribeInstanceInformation.
  # send-command en vez de start-session porque no hay terminal interactiva persistente desde
  # donde se opera esto.
  statement {
    sid    = "SesionesYComandosSSM"
    effect = "Allow"
    actions = [
      "ssm:DescribeInstanceInformation",
      "ssm:SendCommand",
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
      "ssm:StartSession",
      "ssm:TerminateSession",
      "ssm:ResumeSession",
      "ssm:DescribeSessions",
      "ssm:GetConnectionStatus",
    ]
    resources = ["*"]
  }
}
