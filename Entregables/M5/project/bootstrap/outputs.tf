output "tfstate_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}

output "tfstate_lock_table" {
  value = aws_dynamodb_table.tfstate_lock.name
}

output "terraform_iam_user" {
  value = aws_iam_user.terraform.name
}

output "siguiente_paso" {
  value = "Crea la access key de ${aws_iam_user.terraform.name} en la consola de IAM (no por Terraform) y configúrala como perfil 'digitdeck' en ~/.aws/credentials antes de correr infra/."
}
