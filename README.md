# SICE-TAC — Proyecto

Resumen

- Proyecto que automatiza consultas en el sistema SICE-TAC. Contiene un backend en Python (Flask + Playwright) que procesa archivos Excel y un frontend en React (Vite) que consume el backend.

Estructura

- `backend/` — API Flask, `procesador.py` y Dockerfile.
- `frontend/` — Vite + React app.

Flujo recomendado de despliegue

1. Desplegar el `backend` primero (obtendrás una URL pública HTTPS).
2. En Netlify (u otro host del frontend) configurar la variable de entorno `VITE_BACKEND_URL` con la URL del backend.
3. Construir y desplegar el `frontend`.

Todos los derechos reservados © 2026 Lizarazo.
 
Despliegue público
- Backend en producción: https://autosice-app.onrender.com
- Frontend en producción: https://autosice.netlify.app/