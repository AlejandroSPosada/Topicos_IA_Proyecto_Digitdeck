# Infra — el servicio desplegado

Requiere que `../bootstrap/` ya se haya corrido (bucket de estado, tabla de candado, y el
perfil de AWS `digitdeck` configurado — ver `bootstrap/README.md`).

Crea: una instancia EC2 `g5.xlarge` (A10G, 24 GB VRAM) con Docker y el driver NVIDIA ya
listos, su IP elástica, un repositorio ECR (`digitdeck/app`), el rol IAM de la instancia
(acceso por SSM, sin SSH abierto), los dos secretos en SSM Parameter Store, y un presupuesto
de AWS propio de 40 USD/mes (ajustable) con alerta por correo.

## Qué falta antes de poder aplicar esto

La imagen que corre la instancia (`digitdeck/app:latest` en ECR) todavía no existe: hay que
construirla y subirla primero. Eso es la Fase 2 (servicio) y la Fase 3 (imagen + despliegue) de
[`../../docs/PLAN.md`](../../docs/PLAN.md) §1, que **no están hechas todavía** — ver
pendientes abajo.

## Pasos

1. `cp terraform.tfvars.example terraform.tfvars` y llenarlo (token de HF, API key de W&B,
   correo del equipo para la alerta de presupuesto). **No se commitea** (`.gitignore`).
2. Desde WSL, con el perfil `digitdeck` ya configurado:

   ```bash
   terraform init
   terraform plan
   ```

   Revisar el plan — son recursos reales, con costo real, en una cuenta que comparte
   presupuesto con otros dos proyectos.

3. `terraform apply` — pide confirmación explícita (`yes`) antes de crear nada.
4. `terraform output url` da la URL pública. `terraform output health_check_url` el health
   check.
5. Para apagar sin perder el disco (el índice del catálogo, los modelos ya descargados):

   ```bash
   aws ec2 stop-instances --instance-ids $(terraform output -raw instance_id) --profile digitdeck
   ```

   y para volver a encenderla, `start-instances` con el mismo id. El volumen gp3 persiste
   apagado (sigue cobrando almacenamiento, no cómputo: con 150 GB son
   ~12 USD/mes incluso apagada — mucho menos que la 1,01 USD/hora encendida).
6. `terraform destroy` solo si el equipo decide no volver a usar la demo — se pierde el disco
   con el índice ya construido y los modelos ya descargados, y habría que rehacer el build.

## Pendiente antes del primer `apply`

- [ ] Construir y subir la imagen `digitdeck/app` a ECR (servicio FastAPI que envuelve M1+M3+M4
      — todavía no existe, ver `../../docs/PLAN.md` Fase 2 y 3).
- [ ] Subir el encoder ajustado de M1 al HF Hub (`../../docs/PLAN.md` lote 2.1).
- [ ] Activar la etiqueta de costo `Project` en Billing → Cost allocation tags, para que el
      presupuesto de `budget.tf` vea el gasto real (tarda hasta 24h).
- [ ] Decidir el dominio (hoy la URL es la IP elástica sola, `http://<ip>:8000`).

## Por qué VPC por defecto y sin SSH

Es una sola instancia pública sin backend privado: no hay NAT Gateway que pagar ni subredes
privadas que mantener, a diferencia de 4U_project (`campus-locator-dev-vpc`). El acceso a la
máquina es por **SSM Session Manager** (`terraform output ssm_session_command`), no por SSH:
ningún puerto 22 abierto a internet.
