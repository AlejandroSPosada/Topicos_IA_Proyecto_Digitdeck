# Presupuesto propio de Digitdeck, aparte del compartido de 100 USD/mes
# "campus-locator-mensual" (4U_project + TrendAnalyzer). Filtra por la etiqueta Project=digitdeck
# que llevan todos los recursos de este stack.
#
# Nota: para que el filtro por etiqueta funcione hay que activarla como "cost allocation tag"
# en Billing > Cost allocation tags (un clic, tarda hasta 24h en empezar a reflejar costos).
# Mientras tanto el presupuesto existe pero puede mostrar 0 USD de gasto real.

resource "aws_budgets_budget" "digitdeck" {
  name         = "digitdeck-mensual"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$digitdeck"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
