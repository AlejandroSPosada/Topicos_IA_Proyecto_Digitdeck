# Bootstrap — se corre una sola vez

Crea lo que `../infra/` necesita antes de poder existir: el bucket de estado remoto, la
tabla de candado de DynamoDB, y un usuario IAM dedicado (`digitdeck-terraform`) para que el
Terraform de la infraestructura deje de usar las llaves root de la cuenta.

**Por qué el estado de este stack es local y no se sube a S3:** este stack es el que *crea*
el bucket de S3 que usan los demás. No se commitea (`.gitignore` ya lo excluye):
`terraform.tfstate` queda con la contraseña/ARNs de recursos reales de la cuenta
648617469176, compartida con 4U_project y TrendAnalyzer.

## Pasos

1. Desde WSL (`wsl -u root -d Ubuntu-26.04`), dentro de esta carpeta:

   ```bash
   terraform init
   terraform apply
   ```

   Usa el perfil `default` de AWS CLI (ya configurado, apunta a la cuenta 648617469176). Pide
   confirmación con `yes` antes de crear nada — revisa el plan primero.

2. Con el `terraform output` de este paso, confirma el nombre del bucket
   (`digitdeck-tfstate-648617469176`) y de la tabla (`digitdeck-tfstate-lock`).

3. **Paso manual, a propósito fuera de Terraform:** en la consola de AWS, IAM → Users →
   `digitdeck-terraform` → Security credentials → Create access key. Guarda el `Access key ID`
   y el `Secret access key` — no se vuelven a mostrar.

4. Configura un perfil nuevo en `~/.aws/credentials` (en WSL) con esas llaves:

   ```ini
   [digitdeck]
   aws_access_key_id = ...
   aws_secret_access_key = ...
   ```

   y en `~/.aws/config`:

   ```ini
   [profile digitdeck]
   region = us-east-1
   output = json
   ```

5. De aquí en adelante, todo el Terraform de `../infra/` usa el perfil `digitdeck`, no
   `default` ni `campus-admin`. Verificar con `aws sts get-caller-identity --profile digitdeck`
   que el ARN sea el del usuario IAM, no `:root`.

## Por qué no se creó la access key con Terraform

`aws_iam_access_key` la dejaría en texto plano dentro del `terraform.tfstate` de este stack.
Como ese estado es local (paso anterior), terminaría siendo un archivo con una credencial viva
en el disco de quien lo corrió. Crearla a mano en la consola cuesta un paso extra y evita eso.
