# M5/project — despliegue con Terraform

Dos stacks, en orden:

1. **[`bootstrap/`](bootstrap/README.md)** — se corre una sola vez, con las llaves root que ya
   hay en WSL (`aws configure list-profiles`: `default`, `campus-admin`). Crea el bucket de
   estado remoto, la tabla de candado de DynamoDB, y un usuario IAM dedicado
   (`digitdeck-terraform`) para que el resto del Terraform deje de usar llaves root.
2. **[`infra/`](infra/README.md)** — el servicio desplegado: EC2 con GPU (`g5.xlarge`), ECR,
   IAM de la instancia, secretos en SSM, y un presupuesto propio de AWS. Usa el perfil
   `digitdeck` que sale del paso 1, con estado remoto en el bucket que crea el paso 1.

## Lo que ya se investigó en la cuenta (2026-11-01, cuenta 648617469176)

| Qué | Resultado |
|---|---|
| Perfiles de AWS en WSL | `default` y `campus-admin`, ambos llaves **root** de la cuenta — de ahí el paso de bootstrap |
| Presupuesto existente | `campus-locator-mensual`, 100 USD/mes, **compartido** con 4U_project y TrendAnalyzer |
| Instancias EC2 activas | ninguna |
| VPCs | la por defecto, y `campus-locator-dev-vpc` (de 4U_project, no se toca) |
| Cuota GPU (G/VT, us-east-1) | 8 vCPU — alcanza para una `g5.xlarge` (4 vCPU) o `g5.2xlarge`/`g4dn.2xlarge` (8 vCPU) |
| Cuota GPU (familia P) | 0 — no disponible sin pedir aumento, no se necesita para este plan |
| Precio `g5.xlarge` on-demand | 1,01 USD/h (API de precios de AWS, us-east-1, Linux) — confirmado, no estimado |
| ECR / S3 / IAM existentes | todos con prefijo `campus-locator-*` o `ta-*`; nada de Digitdeck todavía |
| Docker en esta WSL | no disponible (Docker Desktop está en Windows, falta activar la integración con Ubuntu-26.04, o instalar Docker directo en la distro) |

## Qué no está hecho todavía

Este Terraform **no se ha aplicado**. Antes de `bootstrap/` y `infra/`, sigue pendiente el
empaquetado del servicio ([`../docs/PLAN.md`](../docs/PLAN.md) Fase 2): hoy el sistema vive en
4 notebooks (`../M1/ENTREGABLE.ipynb`, `../M3/ENTREGABLE.ipynb`, `../M4/pipeline/ENTREGABLE.ipynb`),
no en código servible. `infra/` ya está listo para recibir la imagen en cuanto exista.

## Decisiones tomadas con el equipo (2026-11-01)

- Presupuesto propio para Digitdeck (no compartir el de 100 USD sin verlo por separado).
- Credenciales: usuario IAM dedicado, no las llaves root que ya había.
- Instancia: `g5.xlarge` (24 GB VRAM, cubre el sistema completo con margen), no `g4dn.2xlarge`.

---

*SI4006 · Universidad EAFIT · Equipo Digitdeck.*
