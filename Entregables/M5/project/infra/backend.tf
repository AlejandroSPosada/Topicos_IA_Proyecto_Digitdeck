terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "digitdeck-tfstate-648617469176"
    key            = "m5/infra.tfstate"
    region         = "us-east-1"
    dynamodb_table = "digitdeck-tfstate-lock"
    encrypt        = true
    profile        = "digitdeck"
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

data "aws_caller_identity" "current" {}
