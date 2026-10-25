# 📋 TaskFlow — imagen autocontenida (Flask + SQLite, cero frameworks)
#   Build:  docker build -t taskflow .
#   Run:    docker run -d -p 5000:5000 taskflow
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TASKFLOW_DB=/data/tasks.db

# Usuario no-root
RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Primero las dependencias (caching de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Después el código (ver .dockerignore: sin .git, sin tasks.db, sin pyc)
COPY . .

# La BD vive en un volumen: los datos sobreviven a la recreación del contenedor
RUN mkdir -p /data && chown appuser:appuser /data
VOLUME ["/data"]
USER appuser

EXPOSE 5000

# flask run (sin --debug): un solo proceso, escucha en todas las interfaces
# (necesario para que el puerto mapeado desde el host funcione)
CMD ["flask", "--app", "app.py", "run", "--host", "0.0.0.0", "--port", "5000"]
