# SICE-TAC — Frontend

Descripción

- Aplicación React + Vite que proporciona la interfaz de usuario para subir archivos Excel y descargar el resultado procesado.

Requisitos

- Node.js 16+ (recomendado 18+)

Instalación y desarrollo
```bash
npm install
npm run dev
```

Variables de entorno

- Antes de construir para producción debes definir la URL del backend en tiempo de build:
  - `VITE_BACKEND_URL=https://mi-backend.onrender.com`

Build y despliegue (Netlify recomendado):

1. En el panel de Netlify añade la variable de entorno `VITE_BACKEND_URL` con la URL pública de tu backend.
2. Build command: `npm run build`
3. Publish directory: `dist`

Probar build localmente
```bash
VITE_BACKEND_URL="https://mi-backend.onrender.com" npm run build
npx serve -s dist -l 5000
```

Notas
- Vite inserta variables `VITE_` en tiempo de build; asegurarse de configurarlas en Netlify/host antes del deploy.
- Si cambias el backend, reconstruye el frontend para que la variable quede bakeada en el bundle.