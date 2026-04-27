# SICE-TAC — Backend

Descripción

- Servicio Flask que procesa archivos Excel usando Playwright y devuelve un archivo Excel procesado junto con cabeceras de estado.

Requisitos

- Python 3.9+
- Docker (opcional para producción)

Dependencias

- Se listan en `requirements.txt` (Flask, flask-cors, pandas, openpyxl, playwright, gunicorn, ...).

Instalación local (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install
```

Ejecutar en desarrollo
```powershell
setx FLASK_APP app
setx FLASK_ENV development
flask run --port 5000
```

Ejecutar en producción (gunicorn)
```powershell
gunicorn app:app --bind 0.0.0.0:8000
```

Docker (recomendado para despliegue porque incluye navegadores necesarios para Playwright)
```powershell
docker build -t sicetac-backend .
docker run -p 8000:8000 sicetac-backend
```

API principal

- `POST /procesar` — multipart form con campo `file` (archivo Excel). Devuelve el archivo procesado como attachment y añade cabeceras:
  - `X-Rows-Processed`
  - `X-Rows-Errors`
  - `X-Processing-Status`

  Despliegue
  - Backend en producción: https://autosice-app.onrender.com

Es buena práctica documentar la URL pública en este README para pruebas y para indicar el entorno desplegado. No incluyas credenciales ni secretos en el repositorio.

Modo rápido de procesamiento (opcional)
- Puedes habilitar un modo de procesamiento más rápido estableciendo la variable de entorno `FAST_PROCESSING=1` en el entorno donde corre el backend.
- Cuando está activado, el procesador bloquea la carga de recursos pesados (imágenes, fuentes, hojas de estilo y algunos rastreadores) y reduce esperas internas para acelerar la iteración por filas. Úsalo con precaución: puede cambiar tiempos de espera y comportamiento si el sitio objetivo carga recursos de forma atípica.

Checkpoint / reducción de I/O
- Para acelerar el procesamiento reducimos la frecuencia con la que el script escribe el Excel de salida a disco. Esto evita una operación de I/O costosa tras cada fila.
- Por defecto, si `FAST_PROCESSING=1`, el script hará un "checkpoint" cada 10 filas (escribirá el Excel cada 10 filas). Si `FAST_PROCESSING` no está activado, el comportamiento por defecto es guardar después de cada fila (manteniendo la robustez anterior).
- Puedes controlar la frecuencia con la variable `CHECKPOINT_EVERY`. Ejemplos:
  - `FAST_PROCESSING=1` (usa checkpoints cada 10 filas por defecto)
  - `FAST_PROCESSING=1 CHECKPOINT_EVERY=5` (checkpoint cada 5 filas)
  - `CHECKPOINT_EVERY=1` (si quieres forzar escritura por fila)

Ejemplo (Render env var): `FAST_PROCESSING=1`