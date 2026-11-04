# BioKardex

Sistema integral de farmacia: Django + DRF (backend) y Vue 3 + Tailwind + PrimeVue (frontend).

## Fase 1 (fundaciones)

Backend: Django 5, JWT, usuarios con rol (admin, regente, cajero, almacenero), sucursales, permisos.
Frontend: tema claro/oscuro, login, layout, selector de sucursal.

## Puesta en marcha

```bash
# 1. Base de datos local
docker compose up -d db        # o usa tu PostgreSQL local con los datos de backend/.env.example

# 2. Backend
cd backend-bio-kardex
cp .env.example .env           # cambia SECRET_KEY
uv sync
uv run python manage.py migrate
uv run python manage.py create_dev_admin
uv run python manage.py runserver

# 3. Frontend
cd ../frontend-bio-kardex
cp .env.example .env
npm install
npm run dev                    # http://localhost:5173

# Tests del backend
cd ../backend-bio-kardex && uv run pytest
```

Antes de ejecutar `create_dev_admin`, configura `DEV_ADMIN_PASSWORD` en
`backend-bio-kardex/.env`. El comando solo funciona con `DEBUG=True`, crea un
superusuario con el rol de administrador y no modifica las credenciales de un
superusuario existente. No uses estas credenciales de desarrollo en producción.
