# BioKardex

Sistema integral de farmacia: Django + DRF (backend) y Vue 3 + Tailwind (frontend).

## Modulos

| Fase | Contenido                                                                                                                       |
| ---- | ------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Auth JWT, roles (admin, regente, cajero, almacenero), sucursales, tema claro/oscuro                                             |
| 2    | Catalogo: principios activos, productos con imagen, presentaciones con precio por nivel, precio por sucursal                    |
| 3    | Inventario: lotes con vencimiento, FEFO transaccional, Kardex inalterable, bajas, ajustes, bloqueos, traspasos entre sucursales |
| 4    | Caja: apertura con fondo inicial, arqueo de cierre (efectivo y QR por separado)                                                 |
| 5    | POS: venta fraccionada, pagos mixtos, vuelto, comprobante QR, recetas, devoluciones, anulaciones, recibo imprimible             |
| 6    | Reportes (regente/admin): ventas, stock valorizado a costo y libro de controlados, con exportacion a CSV                        |
| 7    | Administracion (admin): usuarios, sucursales y cajas desde la app; cambio de contrasena propio                                  |

## Puesta en marcha

```bash
# 1. Base de datos local
docker compose up -d db

# 2. Backend
cd backend-bio-kardex
cp .env.example .env            # cambia SECRET_KEY y DEV_ADMIN_PASSWORD
uv sync                         # o: pip install -r requirements.txt
uv run python manage.py makemigrations catalog inventory cash payments sales
uv run python manage.py migrate
uv run python manage.py create_dev_admin
uv run python manage.py runserver

# 3. Frontend
cd ../frontend-bio-kardex
cp .env.example .env
npm install
npm run dev                     # http://localhost:5173

# Tests
cd ../backend-bio-kardex && uv run pytest
cd ../frontend-bio-kardex && npm run test:unit -- --run && npm run type-check
```

Las migraciones de `accounts` y `branches` ya existen; las demas apps se generan con el
`makemigrations` de arriba. El trigger que protege el Kardex en PostgreSQL se instala
solo, despues de cada `migrate`.

## Primeros pasos en la app

1. Entra a la app con el superusuario y abre **Administracion**: crea la primera **sucursal**,
   luego los **usuarios** (rol y sucursales donde operan) y las **cajas** de cada sucursal.
   El administrador ve todas las sucursales. Usuarios y sucursales no se borran, se desactivan.
2. En la app: **Catalogo** -> crea productos y sus presentaciones (caja, blister, unidad)
   con factor y precio (con IVA incluido).
3. **Inventario -> Ingreso de mercaderia** para cargar lotes con vencimiento.
4. **Caja** -> crea una caja (regente/admin) y abre un turno con el fondo inicial.
5. **Punto de venta** (atajos: F2 buscar, F4 cobrar, Enter con codigo de barras).

## Reglas de negocio importantes

- El stock se guarda siempre en **unidades base** (entero). Caja y blister se convierten con el factor.
- **FEFO**: cada venta descuenta del lote que vence primero, en una transaccion con
  `select_for_update`. Los lotes vencidos o bloqueados nunca se venden.
- **Kardex inalterable**: Django bloquea `save/update/delete` y un trigger de PostgreSQL
  rechaza `UPDATE`/`DELETE`. Las correcciones son movimientos compensatorios.
- **Pagos**: la suma de pagos debe igualar el total; el vuelto solo existe en efectivo.
- Descuentos, anulaciones y devoluciones: solo regente o administrador. Anular solo con el
  turno de la venta abierto; despues se usa una devolucion.
- Productos controlados exigen N° de receta, medico y documento del cliente.
- Precios con IVA 13% incluido. El comprobante es un **recibo interno**; los campos para la
  factura del SIN (CUF, N° de factura) ya existen para una fase posterior.

## API (resumen)

`/api/auth/*` (login, refresh, me, cambiar-clave, usuarios), `/api/sucursales/`, `/api/productos/`, `/api/presentaciones/`,
`/api/precios-sucursal/`, `/api/inventario/{stock,alertas,resumen,ingresos,bajas,ajustes,bloqueos,kardex,traspasos}/`,
`/api/cajas/`, `/api/turnos/` (+ `actual`, `cerrar`), `/api/pos/buscar/`,
`/api/ventas/` (+ `anular`, `devolucion`, `receta`), `/api/pagos/<id>/comprobante/`,
`/api/clientes/`, `/api/reportes/{ventas,valorizado,controlados}/` (agrega `?formato=csv`). Documentacion interactiva en `/api/docs/`.
