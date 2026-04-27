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