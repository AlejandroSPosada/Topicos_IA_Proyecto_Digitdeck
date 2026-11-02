FROM pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime

WORKDIR /app

COPY requirements.txt .
# torch/torchvision ya vienen en la imagen base, compilados contra CUDA 12.8 (M1/README.md
# "Entorno de la corrida"). Si se instalaran de nuevo desde requirements.txt sin el índice de
# CUDA, pip bajaría la rueda CPU-only de PyPI y pisaría la de GPU en silencio.
# --break-system-packages: la imagen base protege el Python del sistema (PEP 668); en un
# contenedor de un solo propósito no hay "sistema" que proteger.
RUN grep -v -E '^torch(vision)?(==|$)' requirements.txt > requirements-docker.txt \
    && pip install --no-cache-dir --break-system-packages -r requirements-docker.txt

COPY . .

# indices/ y datos/esci/ no viajan en la imagen (ver .dockerignore): el índice del catálogo se
# construye una vez en el host y se monta como volumen (ARCHITECTURE.md §9, riesgo 5) — hornearlo
# aquí obligaría a reconstruir toda la imagen cada vez que cambie el código, no el catálogo.

ENV APP_PORT=8000
EXPOSE 8000

CMD ["python", "app.py"]
