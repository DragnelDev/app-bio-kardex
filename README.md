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
cd backend
cp .env.example .env           # cambia SECRET_KEY
uv sync
uv run python manage.py makemigrations accounts branches   # las migraciones aun no se generaron
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver

# 3. Frontend
cd ../frontend
cp .env.example .env
npm install
npm run dev                    # http://localhost:5173

# Tests del backend
cd ../backend && uv run pytest
```

Crea el primer usuario administrador con `createsuperuser`, luego ponle `rol=admin`
y asigna sucursales desde `/admin/`.
