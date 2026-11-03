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

- [x] Subir el encoder ajustado de M1 al HF Hub (`../../docs/PLAN.md` lote 2.1 — cerrado).
- [x] Construir el índice del catálogo (`../../docs/PLAN.md` lote 2.4 — cerrado, local todavía).
- [ ] Construir y subir la imagen `digitdeck/app` a ECR (`servicio/Dockerfile`, lote 3.1).
- [ ] Activar la etiqueta de costo `Project` en Billing → Cost allocation tags, para que el
      presupuesto de `budget.tf` vea el gasto real (tarda hasta 24h).
- [ ] Decidir el dominio (hoy la URL es la IP elástica sola, `http://<ip>:8000`).

## Paso manual después del primer `apply`

El índice del catálogo (`servicio/indices/`, construido localmente en el Lote 2.4) no viaja en la
imagen Docker (`servicio/.dockerignore`) ni lo reconstruye `user_data.sh.tpl` automáticamente —
necesita los parquet de ESCI (~1,1 GB) y tarda varios minutos, no es para el arranque automático de
cada instancia. Primer deploy, por SSM (`terraform output ssm_session_command`):

```bash
# subir servicio/indices/ generado en local a /data/digitdeck/indices/ de la instancia
# (scp/rsync por SSM, o reconstruirlo ahí mismo con construir_indice.py si los parquet también se suben)
```

Mientras esa carpeta esté vacía, `GET /salud` responde `indice_listo: false`.

## Redesplegar un cambio de código

[`redesplegar.sh`](redesplegar.sh) repite en un comando lo que se hizo a mano el 2026-11-02
(`../../docs/ARCHITECTURE.md` §9, ADR-11 y riesgo 11). Por `ssm send-command`, la instancia baja el
commit desde GitHub, construye la imagen, la sube a ECR con un **tag nuevo** y reinicia el
contenedor con los mismos flags que `user_data.sh.tpl`. Después espera a que `GET /salud` responda
`ok`, lo que tarda unos minutos mientras se cargan los cuatro modelos.

```bash
# el commit tiene que estar en GitHub; el tag no puede existir (los tags de ECR son inmutables)
bash redesplegar.sh "$(git rev-parse HEAD)" 2026-11-02-frontend-ventanal
# volver a una imagen que ya está en ECR
bash redesplegar.sh --tag 2026-11-02-frontend
```

Usa el perfil `digitdeck` (o el de `AWS_PROFILE`). En AWS CloudShell, con la consola abierta en la
cuenta del proyecto, se corre con `AWS_PROFILE= bash redesplegar.sh …`. Si la construcción falla, el
contenedor anterior sigue corriendo: solo se reemplaza cuando la imagen nueva ya está en ECR.

## Por qué VPC por defecto y sin SSH

Es una sola instancia pública sin backend privado: no hay NAT Gateway que pagar ni subredes
privadas que mantener, a diferencia de 4U_project (`campus-locator-dev-vpc`). El acceso a la
máquina es por **SSM Session Manager** (`terraform output ssm_session_command`), no por SSH:
ningún puerto 22 abierto a internet.
