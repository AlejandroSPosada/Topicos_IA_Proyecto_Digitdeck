# Mismo patrón que campus-locator/backend y campus-locator/embedding (4U_project): un
# repositorio por servicio, tags inmutables, escaneo de vulnerabilidades al hacer push.

resource "aws_ecr_repository" "app" {
  name                 = "digitdeck/app"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Project = "digitdeck"
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Conservar solo las 5 imágenes más recientes"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = { type = "expire" }
      }
    ]
  })
}
