output "url" {
  description = "URL pública del servicio"
  value       = "http://${aws_eip.app.public_ip}:${var.app_port}"
}

output "health_check_url" {
  value = "http://${aws_eip.app.public_ip}:${var.app_port}/salud"
}

output "instance_id" {
  value = aws_instance.app.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ssm_session_command" {
  description = "Cómo entrar a la instancia sin SSH"
  value       = "aws ssm start-session --target ${aws_instance.app.id} --profile ${var.aws_profile} --region ${var.aws_region}"
}
