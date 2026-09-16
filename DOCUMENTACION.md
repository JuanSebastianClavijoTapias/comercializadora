# Documentación del Proyecto — FrutaSystem (Comercializadora)

## 1. Descripción General

**FrutaSystem** es un sistema de gestión para una comercializadora de frutas. Permite registrar y controlar:

- **Viajes** de compra de fruta a proveedores, con pesadas, clasificación y pagos.
- **Entradas de inventario** manuales (compras directas de fruta procesada).
- **Inventario semanal** con reseteo automático cada lunes.
- **Ventas** en efectivo y a crédito, con control de saldos y abonos.
- **Gastos diarios** categorizados, incluyendo nómina y pagos a proveedores.
- **Reportes** diarios, de cartera y deuda con proveedores.
- **Dashboard** con métricas del día, gráficos y KPIs de inventario.

**Stack tecnológico:** Django 4.2 LTS · PostgreSQL · Bootstrap 5.3 · Chart.js 4.4 · Gunicorn · Whitenoise

---

## 2. Requisitos e Instalación

### Requisitos del sistema

- **Python** 3.10 o superior
- **PostgreSQL** 14+ (o SQLite para desarrollo local)
- **pip** y **virtualenv** (recomendado)

### Dependencias (requirements.txt)

| Librería | Versión | Propósito |
|---|---|---|
| Django | 4.2.30 | Framework web (LTS) |
| gunicorn | 25.3.0 | Servidor WSGI para producción |
| psycopg2-binary | 2.9.12 | Driver PostgreSQL |
| python-dotenv | 1.2.2 | Carga de variables de entorno desde `.env` |
| pillow | 12.2.0 | Procesamiento de imágenes |
| whitenoise | 6.12.0 | Servicio de archivos estáticos en producción |
| asgiref | 3.11.1 | Dependencia ASGI de Django |
| packaging | 26.2 | Utilidad de versionado |
| sqlparse | 0.5.5 | Parseo de SQL (dependencia de Django) |

### Pasos de instalación

```bash
# 1. Clonar / copiar el proyecto
cd comercializadora

# 2. Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno (.env)
# Editar .env con las credenciales de PostgreSQL:
#   DB_NAME=comercializadora_db
#   DB_USER=tu_usuario
#   DB_PASSWORD=tu_password
#   DB_HOST=localhost
#   DB_PORT=5432

# 5. Aplicar migraciones
python manage.py migrate

# 6. (Opcional) Cargar datos semilla
python manage.py loaddata initial_data.json

# 7. Crear superusuario
python manage.py createsuperuser

# 8. Ejecutar servidor de desarrollo
python manage.py runserver 0.0.0.0:9000
```

### Credenciales por defecto (initial_data.json)

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin1234` | Superusuario / Staff |

**Importante:** Cambiar la contraseña en producción inmediatamente después del primer login.

### Configuración de producción

1. Cambiar `SECRET_KEY` en `fruta_system/settings.py`
2. Establecer `DEBUG = False`
3. Restringir `ALLOWED_HOSTS` a los dominios reales
4. Ejecutar `python manage.py collectstatic` (los estáticos se sirven via Whitenoise)
5. Usar Gunicorn + Nginx como servidores de aplicación y proxy inverso

> **IMPORTANTE — estáticos en producción:**
> WhiteNoise (ya instalado y en `MIDDLEWARE`) es la ÚNICA fuente de verdad para `/static/`.
> **NO agregar** un bloque `location /static/ { root ... }` en nginx: usa `root` (no `alias`) y
> busca los archivos en `.../static/` pero `collectstatic` los deja en `.../staticfiles/`, por lo que
> nginx responde 404 y toda la app queda sin estilos (el login aparenta bien porque usa CDN).
> Los bloques `location /static/` y `/location media/` solo funcionan con `alias <ruta_real>/` (slash final).
> Tras cada deploy: `collectstatic --noinput` + `systemctl restart gunicorn` (refresca el caché de WhiteNoise).

---

## 3. Estructura de Carpetas

```
comercializadora/
├── .env                          Variables de entorno (credenciales PostgreSQL)
├── .env.example                  Plantilla de .env
├── .gitignore                    Exclusiones de git
├── db.sqlite3                    BD SQLite legacy (no usada en producción)
├── initial_data.json             Fixture de datos semilla (opcional)
├── manage.py                     Punto de entrada de Django
├── requirements.txt              Dependencias Python
├── temp_js.txt                   Borrador JS no integrado
│
├── fruta_system/                 Paquete de configuración del proyecto
│   ├── __init__.py
│   ├── asgi.py                   Entrada ASGI
│   ├── settings.py               Configuración principal
│   ├── urls.py                   URLs raíz (admin, login, include core)
│   └── wsgi.py                   Entrada WSGI
│
├── core/                         Aplicación principal de negocio
│   ├── __init__.py
│   ├── admin.py                  Registro de modelos en admin
│   ├── apps.py                   Configuración de la app
│   ├── forms.py                  Formularios (ModelForms)
│   ├── models.py                 Modelos + Señales (signals)
│   ├── urls.py                   URLs de todo el negocio
│   ├── views.py                  Vistas (helpers + 47 vistas)
│   ├── tests.py                  Tests unitarios
│   ├── patch.ps1                 Script PowerShell de mantenimiento
│   ├── patch2.ps1                Script PowerShell de mantenimiento
│   ├── replace.py                Script Python de mantenimiento
│   │
│   ├── management/
│   │   └── commands/
│   │       └── reset_weekly_inventory.py   Comando de reset semanal
│   │
│   ├── migrations/               22 migraciones (0001 → 0021)
│   │
│   ├── templatetags/
│   │   └── cop_filters.py        Filtro `cop` (formato moneda colombiana)
│   │
│   └── templates/core/
│       ├── base.html             Layout maestro (sidebar, topbar, price-cop JS)
│       ├── login.html            Página de login
│       ├── dashboard.html        Dashboard principal
│       │
│       ├── catalogo/             CRUD de catálogos
│       │   ├── cliente_list.html
│       │   ├── producto_clasificaciones.html
│       │   ├── producto_list.html
│       │   └── proveedor_list.html
│       │
│       ├── gastos/               Gestión de gastos diarios
│       │   ├── categoria_gasto_list.html
│       │   ├── gasto_delete_modal.html
│       │   ├── gasto_detail.html
│       │   ├── gasto_detail_modal.html
│       │   ├── gasto_edit_modal.html
│       │   └── gasto_list.html
│       │
│       ├── genericos/            Plantillas reutilizables
│       │   ├── confirm_delete.html
│       │   └── form_generic.html
│       │
│       ├── inventario/           Entradas e inventario semanal
│       │   ├── entrada_inventario_detail.html
│       │   ├── entrada_inventario_list.html
│       │   ├── entrada_inventario_nueva.html
│       │   └── inventario_weekly_summary.html
│       │
│       ├── reportes/             Reportes
│       │   ├── reporte_cartera.html
│       │   ├── reporte_diario.html
│       │   └── reporte_proveedor.html
│       │
│       └── ventas/               Ventas efectivo y crédito
│           ├── venta_credito_detail.html
│           ├── venta_credito_list.html
│           ├── venta_efectivo_create.html
│           ├── venta_efectivo_detail.html
│           └── venta_efectivo_list.html
│
└── venv/                         Entorno virtual (excluido de git)
```

---

## 4. Configuración del Proyecto (`fruta_system/`)

### `settings.py` — Configuración principal

| Directiva | Valor | Notas |
|---|---|---|
| `SECRET_KEY` | hardcoded | **Inseguro en producción — cambiar.** |
| `DEBUG` | `True` | **Cambiar a `False` en producción.** |
| `ALLOWED_HOSTS` | `['*']` | **Restringir en producción.** |
| `INSTALLED_APPS` | `django.contrib.*` + `core` | Solo 1 app de negocio. |
| `MIDDLEWARE` | 6 middleware estándar de Django | No hay middleware personalizado. |
| `DATABASES` | PostgreSQL via `.env` | `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`. |
| `LANGUAGE_CODE` | `es-co` | Español Colombia. |
| `TIME_ZONE` | `America/Bogota` | UTC-5. |
| `LOGIN_URL` | `/login/` | Redirige aquí si no autenticado. |
| `LOGIN_REDIRECT_URL` | `/` | Dashboard. |
| `LOGOUT_REDIRECT_URL` | `/login/` | |
| `SESSION_COOKIE_AGE` | `1209600` | 2 semanas. |
| `STATIC_URL` | `static/` | |
| `STATIC_ROOT` | `BASE_DIR / 'staticfiles'` | Para `collectstatic`. |
| `TEMPLATES[0]['builtins']` | `['core.templatetags.cop_filters']` | Filtro `cop` disponible globalmente. |

### `urls.py` (raíz)

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('', include('core.urls')),
]
```

---

## 5. App `core/` — Archivos Python

### 5.1 `models.py` (497 líneas)

**Constantes:**
- `MEDIO_PAGO_CHOICES` = efectivo, transferencia, cheque
- `PESO_CANASTILLA_NEGRA = 1.6 kg`, `PESO_CANASTILLA_COLOR = 2.2 kg`
- `PESO_CANASTILLA_NEGRA_ENTRADA = 1.6 kg`, `PESO_CANASTILLA_COLOR_ENTRADA = 2.2 kg`

**Modelos maestros:**

| Modelo | Campos clave | Meta |
|---|---|---|
| `Proveedor` | nombre (Char 200), telefono (Char 20), direccion (Text), activo (Bool) | ordering `['nombre']` |
| `Cliente` | nombre, telefono, direccion, activo | ordering `['nombre']` |
| `Producto` | nombre (Char 100), tiene_descuento_gobierno (Bool), porcentaje_descuento (Decimal 5,2), activo | ordering `['nombre']` |
| `Clasificacion` | producto (FK→Producto, CASCADE, `related_name='clasificaciones'`), nombre (Char 100), orden (Int), activo (Bool), **stock_kg** (Decimal 10,2) | ordering `['producto','orden']` |
| `CategoriaGasto` | nombre (Char 100) | ordering `['nombre']` |

**Modelos de viajes/compras:**

| Modelo | Campos / Properties / Relaciones |
|---|---|
| `Viaje` | proveedor (FK→Proveedor), producto (FK→Producto), fecha (Date), observaciones (Text), kg_podridos (Decimal), precio_total_acordado (Decimal), created_at. **Properties:** `kg_bruto`, `neto_a_pagar` (con descuento gobierno), `total_valor`, `total_pagado`, `saldo_pendiente` |
| `PesadaViaje` | viaje (FK→Viaje, CASCADE, `related_name='pesadas'`), **clasificacion (FK→Clasificacion, SET_NULL, null/blank)**, num_canastillas_negras, num_canastillas_colores, kg_bruto. **Properties:** `peso_canastillas`, `kg_neto` |
| `LoteClasificacion` | viaje (FK→Viaje, CASCADE, `related_name='lotes'`), clasificacion (FK→Clasificacion, CASCADE), kg_neto. **Calculado automáticamente por señales desde PesadaViaje.** |
| `PagoProveedor` | viaje (FK→Viaje, CASCADE, `related_name='pagos_proveedor'`), monto (Decimal 12,2), medio_pago, fecha, observaciones |

**Modelos de gastos:**

| Modelo | Campos y Relaciones |
|---|---|
| `Gasto` | categoria (FK→CategoriaGasto, SET_NULL, null/blank), descripcion (Char 300), monto (Decimal 12,2), fecha (Date), pago_proveedor (**OneToOne**→PagoProveedor, CASCADE, null/blank, `related_name='gasto_generado'`) |

**Modelo de inventario semanal:**

| Modelo | Campos | Properties |
|---|---|---|
| `WeeklyInventory` | week_start (Date, unique), initial_inventory_kg (Decimal 12,2), created_at, updated_at | `total_inventory_kg` = initial + entradas de la semana + viajes de la semana |

**Modelos de ventas en efectivo:**

| Modelo | Campos y Relaciones |
|---|---|
| `VentaEfectivo` | fecha, producto (FK→Producto, SET_NULL), kg_vendido (Decimal), total_dia (Decimal), cliente (FK→Cliente, CASCADE, null), descripcion, observaciones. **Property:** `total` |
| `DetalleVentaEfectivo` | venta (FK→VentaEfectivo, CASCADE, `related_name='detalles'`), producto, kg_vendido, precio_por_kg. **Property:** `total` |

**Modelos de ventas a crédito:**

| Modelo | Campos y Relaciones |
|---|---|
| `VentaCredito` | cliente (FK→Cliente, CASCADE, `related_name='ventas'`), producto (FK→Producto, CASCADE), fecha, fecha_vencimiento, observaciones. **Properties:** `total`, `total_pagado`, `saldo_pendiente` |
| `DetalleVentaCredito` | venta (FK, CASCADE, `related_name='detalles'`), clasificacion (FK→Clasificacion, CASCADE), kg_vendido, precio_por_kg. **Property:** `total` |
| `PagoVentaCredito` | venta (FK, CASCADE, `related_name='pagos'`), monto, medio_pago, fecha, observaciones |

**Modelos de entradas de inventario:**

| Modelo | Campos y Relaciones |
|---|---|
| `EntradaInventario` | fecha, proveedor (FK→Proveedor), clasificacion (FK→Clasificacion), precio_por_kg (Decimal), observaciones, created_at. **Properties:** `kg` (suma kg_neto de pesadas), `total` (kg × precio) |
| `PesadaEntrada` | entrada (FK, CASCADE, `related_name='pesadas'`), num_canastillas_negras, num_canastillas_colores, kg_bruto. **Properties:** `peso_canastillas`, `kg_neto` |

**Modelo de desechos:**

| Modelo | Campos |
|---|---|
| `DesechoInventario` | fecha, clasificacion (FK→Clasificacion, CASCADE), kg (Decimal), observaciones, created_at |

### 5.2 `views.py` (1739 líneas)

**Funciones auxiliares de inventario semanal (líneas 15-153):**
- `get_week_monday(fecha)` — retorna el lunes de la semana
- `parse_week_start(raw_value)` — parsea parámetro `?week=YYYY-MM-DD`
- `get_nomina_category()` — obtiene/crea CategoriaGasto "Nómina"
- `get_or_create_weekly_inventory_for_monday(lunes)` — obtiene o crea registro WeeklyInventory
- `get_week_inventory_data(fecha)` — datos de inventario para una semana
- `get_current_week_inventory_data()` — datos de inventario de la semana actual
- `get_weekly_history()` — historial agregado de todas las semanas con datos
- `_week_has_data(lunes)` — True si existen registros en esa semana
- `_get_stock_valorizado()` — stock actual con valorización al último precio de compra

**Vistas (todas con `@login_required`):**

#### Catálogo / Maestros

| Vista | URL (name) | Descripción |
|---|---|---|
| `proveedor_list` | `/proveedores/` (`proveedor_list`) | Lista proveedores con búsqueda `q`, conteos activos/inactivos |
| `proveedor_create` | `/proveedores/nuevo/` (`proveedor_create`) | Crear proveedor |
| `proveedor_edit` | `/proveedores/<pk>/editar/` (`proveedor_edit`) | Editar proveedor |
| `proveedor_delete` | `/proveedores/<pk>/eliminar/` (`proveedor_delete`) | Eliminar proveedor |
| `cliente_list` | `/clientes/` (`cliente_list`) | Lista clientes con búsqueda |
| `cliente_create` | `/clientes/nuevo/` (`cliente_create`) | Crear cliente |
| `cliente_edit` | `/clientes/<pk>/editar/` (`cliente_edit`) | Editar cliente |
| `cliente_delete` | `/clientes/<pk>/eliminar/` (`cliente_delete`) | Eliminar cliente |
| `producto_list` | `/productos/` (`producto_list`) | Lista productos con conteos |
| `producto_create` | `/productos/nuevo/` (`producto_create`) | Crear producto + **6 clasificaciones por defecto** |
| `producto_edit` | `/productos/<pk>/editar/` (`producto_edit`) | Editar producto |
| `producto_delete` | `/productos/<pk>/eliminar/` (`producto_delete`) | Eliminar producto |
| `producto_clasificaciones` | `/productos/<pk>/clasificaciones/` (`producto_clasificaciones`) | Gestionar clasificaciones del producto |
| `producto_stock_update` | `/productos/<pk>/stock/` (`producto_stock_update`) | Actualización masiva de stock por clasificación |
| `clasificacion_edit` | `/clasificaciones/<pk>/editar/` (`clasificacion_edit`) | Editar clasificación |
| `categoria_gasto_list` | `/categorias-gasto/` (`categoria_gasto_list`) | Listar/crear categorías de gasto |
| `categoria_gasto_edit` | `/categorias-gasto/<pk>/editar/` (`categoria_gasto_edit`) | Editar categoría |
| `categoria_gasto_delete` | `/categorias-gasto/<pk>/eliminar/` (`categoria_gasto_delete`) | Eliminar categoría |

#### Viajes

| Vista | URL (name) | Descripción |
|---|---|---|
| `viaje_list` | `/viajes/` (`viaje_list`) | Lista viajes con totales |
| `viaje_create` | `/viajes/nuevo/` (`viaje_create`) | Crear viaje (datos básicos) |
| `viaje_detail` | `/viajes/<pk>/` (`viaje_detail`) | Detalle completo: pesadas, desglose, pagos |
| `viaje_detalles_edit` | `/viajes/<pk>/detalles/` (`viaje_detalles_edit`) | Editar kg_podridos |
| `viaje_precio_update` | `/viajes/<pk>/precio/` (`viaje_precio_update`) | Actualizar precio total acordado |
| `viaje_delete` | `/viajes/<pk>/eliminar/` (`viaje_delete`) | Eliminar viaje |
| `viaje_pago_add` | `/viajes/<pk>/pago/` (`viaje_pago_add`) | Registrar pago a proveedor + **genera Gasto automático** |
| `pesada_add` | `/viajes/<pk>/pesada/` (`pesada_add`) | Agregar una o múltiples pesadas al viaje |
| `pesada_delete` | `/pesadas/<pk>/eliminar/` (`pesada_delete`) | Eliminar pesada |
| `lote_delete` | `/lotes/<pk>/eliminar/` (`lote_delete`) | Eliminar lote de clasificación |
| `pago_proveedor_delete` | `/pagos-proveedor/<pk>/eliminar/` (`pago_proveedor_delete`) | Eliminar pago (+ su Gasto vinculado) |

#### Gastos

| Vista | URL (name) | Descripción |
|---|---|---|
| `gasto_list` | `/gastos/` (`gasto_list`) | Lista gastos del día + formulario + estadísticas |
| `gasto_detail` | `/gastos/<pk>/` (`gasto_detail`) | Detalle (soporta modal) |
| `gasto_edit` | `/gastos/<pk>/editar/` (`gasto_edit`) | Editar (modal retorna HTTP 204) |
| `gasto_delete` | `/gastos/<pk>/eliminar/` (`gasto_delete`) | Eliminar (modal o página) |

#### Ventas Efectivo

| Vista | URL (name) | Descripción |
|---|---|---|
| `venta_efectivo_list` | `/ventas/efectivo/` (`venta_efectivo_list`) | Lista ventas del día |
| `venta_efectivo_create` | `/ventas/efectivo/nueva/` (`venta_efectivo_create`) | Crear venta efectivo |
| `venta_efectivo_edit` | `/ventas/efectivo/<pk>/editar/` (`venta_efectivo_edit`) | Editar venta |
| `venta_efectivo_detail` | `/ventas/efectivo/<pk>/` (`venta_efectivo_detail`) | Detalle + finalizar con cambio |
| `venta_efectivo_delete` | `/ventas/efectivo/<pk>/eliminar/` (`venta_efectivo_delete`) | Eliminar venta |
| `detalle_venta_efectivo_delete` | `/ventas/efectivo/detalle/<pk>/eliminar/` | Eliminar detalle |

#### Ventas Crédito

| Vista | URL (name) | Descripción |
|---|---|---|
| `venta_credito_list` | `/ventas/credito/` (`venta_credito_list`) | Lista ventas crédito |
| `venta_credito_create` | `/ventas/credito/nueva/` (`venta_credito_create`) | Crear venta crédito |
| `venta_credito_detail` | `/ventas/credito/<pk>/` (`venta_credito_detail`) | Detalle + AJAX para agregar detalles |
| `venta_credito_add_detalle_ajax` | `/ventas/credito/<pk>/detalle-ajax/` (`venta_credito_add_detalle_ajax`) | POST AJAX: agrega DetalleVentaCredito |
| `venta_credito_delete` | `/ventas/credito/<pk>/eliminar/` (`venta_credito_delete`) | Eliminar venta |
| `venta_credito_pago_add` | `/ventas/credito/<pk>/pago/` (`venta_credito_pago_add`) | Registrar abono |
| `detalle_venta_delete` | `/detalles-venta/<pk>/eliminar/` (`detalle_venta_delete`) | Eliminar detalle crédito |
| `pago_venta_delete` | `/pagos-venta/<pk>/eliminar/` (`pago_venta_delete`) | Eliminar pago crédito |

#### Reportes

| Vista | URL (name) | Descripción |
|---|---|---|
| `reporte_diario` | `/reportes/diario/` (`reporte_diario`) | Reporte del día + historial 30 días |
| `reporte_cartera` | `/reportes/cartera/` (`reporte_cartera`) | Cartera: créditos con saldo pendiente |
| `reporte_proveedor` | `/reportes/proveedores/` (`reporte_proveedor`) | Deudas: viajes con saldo pendiente |

#### Inventario

| Vista | URL (name) | Descripción |
|---|---|---|
| `inventario_weekly_summary` | (interna) | Vista principal del resumen semanal |
| `entrada_inventario_list` | `/inventario/entradas/` (`entrada_inventario_list`) | Delegado a `inventario_weekly_summary` |
| `entrada_inventario_create` | `/inventario/entradas/nueva/` (`entrada_inventario_create`) | Crear entrada + nómina + desecho |
| `entrada_inventario_detail` | `/inventario/entradas/<pk>/` (`entrada_inventario_detail`) | Detalle de entrada |
| `entrada_inventario_edit` | `/inventario/entradas/<pk>/editar/` (`entrada_inventario_edit`) | Editar entrada |
| `entrada_inventario_delete` | `/inventario/entradas/<pk>/eliminar/` (`entrada_inventario_delete`) | Eliminar entrada |
| `pesada_entrada_add` | `/inventario/entradas/<pk>/pesada/` (`pesada_entrada_add`) | Agregar pesadas a entrada |
| `pesada_entrada_delete` | `/inventario/pesadas-entrada/<pk>/eliminar/` (`pesada_entrada_delete`) | Eliminar pesada de entrada |
| `weekly_inventory_edit` | `/inventario/semanal/<pk>/editar/` (`weekly_inventory_edit`) | Editar registro WeeklyInventory |
| `weekly_inventory_delete` | `/inventario/semanal/<pk>/eliminar/` (`weekly_inventory_delete`) | Eliminar registro semanal |
| `nomina_edit` | `/inventario/semanal/nominas/<pk>/editar/` (`nomina_edit`) | Editar nómina |
| `nomina_delete` | `/inventario/semanal/nominas/<pk>/eliminar/` (`nomina_delete`) | Eliminar nómina |

**Dashboard:**

| Vista | URL (name) | Descripción |
|---|---|---|
| `dashboard` | `/` (`dashboard`) | Dashboard principal con KPIs, gráficos y métricas |

### 5.3 `forms.py` (270 líneas)

**Mixin `COPInputNormalizationMixin`:** En `__init__`, elimina puntos (separadores de miles colombianos) de los campos listados en `cop_fields` antes de la validación.

**Formularios (todos `ModelForm`):**

| Formulario | Modelo | Campos destacados | Mixin COP |
|---|---|---|---|
| `ProveedorForm` | Proveedor | nombre, telefono, direccion, activo | — |
| `ClienteForm` | Cliente | nombre, telefono, direccion, activo | — |
| `ProductoForm` | Producto | nombre, tiene_descuento_gobierno, porcentaje_descuento, activo | — |
| `ClasificacionForm` | Clasificacion | nombre, orden, stock_kg, activo | — |
| `CategoriaGastoForm` | CategoriaGasto | nombre | — |
| `ViajeForm` | Viaje | proveedor, producto, fecha, observaciones | — |
| `ViajeDetallesForm` | Viaje | kg_podridos | — |
| `PesadaViajeForm` | PesadaViaje | num_canastillas_negras, num_canastillas_colores, kg_bruto, clasificacion | — |
| `LoteClasificacionForm` | LoteClasificacion | clasificacion, kg_neto | — |
| `PagoProveedorForm` | PagoProveedor | monto (widget `price-cop`), medio_pago, fecha, observaciones | ✓ (monto) |
| `GastoForm` | Gasto | descripcion, monto (`price-cop`), fecha | ✓ (monto) |
| `NominaForm` | Gasto | descripcion, monto (`price-cop`), fecha | ✓ (monto) |
| `WeeklyInventoryForm` | WeeklyInventory | week_start, initial_inventory_kg | — |
| `DesechoForm` | DesechoInventario | fecha, clasificacion (queryset activas), kg, observaciones | — |
| `EntradaInventarioForm` | EntradaInventario | fecha, proveedor, clasificacion, precio_por_kg (`price-cop`), observaciones | ✓ (precio_por_kg) |
| `PesadaEntradaForm` | PesadaEntrada | num_canastillas_negras, num_canastillas_colores, kg_bruto | — |
| `VentaEfectivoForm` | VentaEfectivo | fecha, producto, kg_vendido (`price-cop`), total_dia (`price-cop`) | ✓ (total_dia, kg_vendido) |
| `DetalleVentaEfectivoForm` | DetalleVentaEfectivo | producto, kg_vendido, precio_por_kg (`price-cop`) | ✓ (precio_por_kg) |
| `DetalleVentaCreditoForm` | DetalleVentaCredito | cliente, clasificacion, kg_vendido, precio_por_kg (`price-cop`) | ✓ (precio_por_kg) |
| `PagoVentaCreditoForm` | PagoVentaCredito | monto, medio_pago, fecha, observaciones | ✓ (monto) |

### 5.4 `urls.py` — Rutas de la app (81 líneas)

47 patrones de URL + 1 redirect permanente (`/inventario/semanal/` → `entrada_inventario_list`). Todas las vistas están protegidas con `@login_required`. Los nombres de URL siguen la convención `snake_case` y están agrupados por módulo.

### 5.5 `admin.py` — Panel de administración

Registra: `Proveedor`, `Cliente`, `Producto`, `Clasificacion`, `CategoriaGasto`, `Viaje`, `Gasto`, `WeeklyInventory`, `VentaCredito`, `VentaEfectivo`, `DetalleVentaEfectivo`.

No registra: `PesadaViaje`, `LoteClasificacion`, `PagoProveedor`, `PesadaEntrada`, `EntradaInventario`, `DesechoInventario`, `DetalleVentaCredito`, `PagoVentaCredito`.

### 5.6 `apps.py`

```python
class CoreConfig(AppConfig):
    name = 'core'
```

### 5.7 `tests.py`

Clase `WeeklySummaryTests(TestCase)` con 2 tests:
- `test_weekly_summary_post_creates_payroll_expense` — verifica que POST a `inventario_weekly_summary` crea un Gasto de categoría "Nómina"
- `test_weekly_inventory_edit_updates_selected_week` — verifica actualización de `initial_inventory_kg`

**Nota:** El primer test referencia `reverse('inventario_weekly_summary')`, un nombre de URL que **no existe** en `urls.py` (solo existe `entrada_inventario_list`). Por tanto, ese test probablemente falla.

### 5.8 `management/commands/reset_weekly_inventory.py`

Comando `python manage.py reset_weekly_inventory [--date YYYY-MM-DD]`:
- Calcula el lunes de la semana especificada (o actual)
- Obtiene/crea el `WeeklyInventory` de esa semana
- Copia el `total_inventory_kg` de la semana anterior como `initial_inventory_kg` de la nueva semana (reset de lunes)

---

## 6. Plantillas (`templates/`)

### 6.1 `base.html` — Layout maestro (1018 líneas)

- **CDN externos:** Bootstrap 5.3.0, Bootstrap Icons 1.11.0, Choices.js 10.2.0, Chart.js 4.4.0, Google Fonts (Poppins, Inter)
- **CSS:** variables de paleta naranja, estilos de sidebar (260px), topbar, stat-cards, modales
- **Layout:** sidebar izquierda + topbar superior + content-area principal
- **Sidebar con secciones:** Principal (Dashboard), Ventas (Efectivo, Crédito, Viajes/Entradas, Inventario), Gastos (Gastos Diarios), Reportes & Datos, Catálogo
- **Resaltado de enlace activo** según `request.resolver_match.url_name` o `request.path`
- **Bloques:** `{% block title %}`, `{% block extra_css %}`, `{% block page_title %}`, `{% block content %}`, `{% block extra_js %}`
- **Mensajes Django** renderizados como alerts Bootstrap
- **JS sidebar móvil:** toggle con hamburger + overlay
- **JS `price-cop` (líneas 951-1015):** Formateo de moneda colombiana con separador de miles (`.`):
  - `formatCOP(val)` — convierte dígitos a formato `1.500.000`
  - `parseCOP(val)` — remueve puntos para obtener valor numérico
  - `initPriceCOP(input)` — aplica formato en eventos `input` y `paste`, mantiene posición del cursor
  - `MutationObserver` — inicializa inputs `.price-cop` añadidos dinámicamente (formsets, AJAX)
  - Handler `submit` en fase capture — **limpia puntos** de todos los inputs `.price-cop` antes de enviar cualquier formulario

### 6.2 `login.html` (143 líneas)

Página independiente (no extiende base.html). Tarjeta centrada con logo, formulario usuario/contraseña con toggle mostrar/ocultar, estilos naranja.

### 6.3 `dashboard.html` (736 líneas)

- Alerta de nómina (días 10/20/30 del mes)
- 6 tarjetas KPI "Lo que llevas hoy" (Efectivo, Cobros, Crédito, Por Cobrar, Gastos, Balance)
- 4 tarjetas de inventario de mandarina (Inicial, Compras, Vendido, Desechos en kg/toneladas)
- Gráfico Chart.js de línea "Ventas vs Gastos (7 días)" con toggles efectivo/crédito/total
- Gráfico doughnut "Distribución de Ingresos"
- Tablas: últimas 10 ventas, últimos viajes, créditos pendientes
- Accesos rápidos
- Modal "Cuentas por Cobrar" con abono rápido inline
- Modales de detalle de inventario (inicial, compras, vendido, desechos)

### 6.4 `viajes/`

- **`viaje_list.html`** (172 líneas): 4 tarjetas estadísticas + tabla de viajes con badges de saldo/saldado y botones ver/eliminar. Filtros (inputs sin form — no funcionales).
- **`viaje_detail.html`** (498 líneas): Cabecera con 4 stat-cards. Columna izquierda: tabla de pesadas + formulario multi-fila con JS de clonación/numeración de filas. Card "Resumen por Clasificación" (solo lectura). Columna derecha: desglose visual del kg neto (bruto − negras − colores − podrido), pagos al proveedor con precio acordado editable y formulario de pago. JS: formateador de moneda para precio acordado y monto de pago.

### 6.5 `inventario/`

- **`entrada_inventario_nueva.html`** (440 líneas): Formulario fecha/proveedor + tabla multi-fila de pesadas con JS de cálculo de kg neto (1.6/2.2 kg por canastilla), agrupación por clasificación, formateo COP. Secciones: Registrar Nómina y Registrar Desecho (formularios en la misma página con `form_type`). JS complejo para clonación de filas y recálculo en vivo.
- **`entrada_inventario_detail.html`** (258 líneas): 4 stat-cards + tabla de pesadas + formulario de nuevas pesadas + card "Precio y Total" editable.
- **`entrada_inventario_list.html`** (130 líneas): 3 tarjetas + tabla de entradas. **Nota:** referencia variables `entradas`, `total_kg`, `total_valor` que no están en el contexto de `inventario_weekly_summary` (la vista delegada).
- **`inventario_weekly_summary.html`** (1135 líneas): La plantilla más grande del proyecto. Toolbar de navegación por semanas, alerta de rango semanal y días de nómina, 10 tarjetas-KPI clicables que abren modales (Gastos, Nóminas, Ventas Efectivo, Cobros Crédito, Ventas Crédito, Total Ventas, Desechos, Inventario Inicial, Inventario Total, Compras/Viajes), tabla "Historial de Semanas" con botones ver/editar/eliminar, modales de detalle por categoría y por semana del historial con stock valorizado.

### 6.6 `ventas/`

- **`venta_efectivo_list.html`** (104 líneas): 2 tarjetas + tabla de ventas del día.
- **`venta_efectivo_create.html`** (76 líneas): Formulario con botón "Hoy" para fecha, campos producto, kg_vendido, total_dia.
- **`venta_efectivo_detail.html`** (119 líneas): Card resumen + card "Registrar Pago" con cálculo de cambio en vivo (JS).
- **`venta_credito_list.html`** (180 líneas): Panel de filtros, 3 tarjetas (Total, Cobrado, Por Cobrar), tabla con estado.
- **`venta_credito_detail.html`** (518 líneas): Card resumen + formulario AJAX para agregar productos con campo **cliente** + info de stock + tabla de productos + control de pagos con historial. `venta_credito_create` crea la venta vacía (fecha de hoy, sin cliente) y redirige aquí; el cliente se asigna al agregar el primer producto. JS extenso con `clasificacionesData`, fetch al endpoint `detalle-ajax`, actualización dinámica sin recarga.

### 6.7 `gastos/`

- **`gasto_list.html`** (372 líneas): 3 tarjetas estadísticas + formulario de registro + tabla con modales AJAX (detalle, editar, eliminar). JS: fetch con soporte modal (`?modal=1`), submit por fetch, recarga en HTTP 204.
- **`gasto_detail.html`** / **`gasto_detail_modal.html`** / **`gasto_edit_modal.html`** / **`gasto_delete_modal.html`**: Fragmentos de modal para operaciones AJAX.
- **`categoria_gasto_list.html`**: CRUD de categorías.

### 6.8 `catalogo/`

- **`cliente_list.html`** / **`proveedor_list.html`**: 3 tarjetas estadísticas + filtro + tabla con acciones.
- **`producto_list.html`**: Similar + columna de descuento gobierno + enlace a clasificaciones.
- **`producto_clasificaciones.html`** (101 líneas): Formulario colapsable de nueva clasificación + tabla con edición inline de stock (badge verde/amarillo/rojo según cantidad) + alerta informativa sobre canastillas.

### 6.9 `genericos/`

- **`form_generic.html`** (153 líneas): Formulario genérico para CRUD con JS de previsualización de total (kg × precio), botón "Hoy" para fechas, y muestra de stock al seleccionar clasificación.
- **`confirm_delete.html`** (32 líneas): Confirmación de borrado genérica con soporte de `back_href`, `back_url` o `history.back()`.

### 6.10 `reportes/`

- **`reporte_diario.html`** (335 líneas): Selector de fecha + 5 tarjetas + tablas de detalle + historial 30 días con balance.
- **`reporte_cartera.html`** (36 líneas): Total cartera + tabla de créditos pendientes.
- **`reporte_proveedor.html`** (38 líneas): Total deuda + tabla de viajes con saldo.

---

## 7. Filtros / Templatetags

Archivo: `core/templatetags/cop_filters.py`

```python
@register.filter
def cop(value):
    """Formatea un número con separador de miles colombiano (punto).
    Ej: 1500000 → 1.500.000"""
    n = int(round(float(value)))
    return f"{n:,}".replace(",", ".")
```

Registrado como **builtin** en `settings.TEMPLATES[0]['builtins']`, disponible en todas las plantillas sin `{% load %}`. Se usa extensivamente: `${{ venta.total|cop }}`.

---

## 8. Modelo de Datos Relacional

### Relaciones principales (FK / OneToOne)

| Origen | Campo | Destino | on_delete | related_name |
|---|---|---|---|---|
| Clasificacion | producto | Producto | CASCADE | clasificaciones |
| Viaje | proveedor | Proveedor | CASCADE | viajes |
| Viaje | producto | Producto | CASCADE | viajes |
| PesadaViaje | viaje | Viaje | CASCADE | pesadas |
| PesadaViaje | clasificacion | Clasificacion | **SET_NULL** (null/blank) | pesadas |
| LoteClasificacion | viaje | Viaje | CASCADE | lotes |
| LoteClasificacion | clasificacion | Clasificacion | CASCADE | — |
| PagoProveedor | viaje | Viaje | CASCADE | pagos_proveedor |
| Gasto | categoria | CategoriaGasto | **SET_NULL** (null/blank) | — |
| Gasto | pago_proveedor | PagoProveedor | CASCADE (OneToOne) | gasto_generado |
| EntradaInventario | proveedor | Proveedor | CASCADE | entradas_inventario |
| EntradaInventario | clasificacion | Clasificacion | CASCADE | entradas_inventario |
| PesadaEntrada | entrada | EntradaInventario | CASCADE | pesadas |
| DesechoInventario | clasificacion | Clasificacion | CASCADE | desechos |
| VentaEfectivo | producto | Producto | **SET_NULL** (null/blank) | ventas_efectivo |
| VentaEfectivo | cliente | Cliente | CASCADE (null/blank) | ventas_efectivo |
| DetalleVentaEfectivo | venta | VentaEfectivo | CASCADE | detalles |
| DetalleVentaEfectivo | producto | Producto | CASCADE | — |
| VentaCredito | cliente | Cliente | CASCADE | ventas |
| VentaCredito | producto | Producto | CASCADE (null/blank) | ventas_credito |
| DetalleVentaCredito | venta | VentaCredito | CASCADE | detalles |
| DetalleVentaCredito | clasificacion | Clasificacion | CASCADE | — |
| PagoVentaCredito | venta | VentaCredito | CASCADE | pagos |

`WeeklyInventory` es independiente (sin FKs; se relaciona por fecha).

**Centro del sistema:** `Clasificacion.stock_kg` es el campo de stock sincronizado automáticamente por **señales** desde `LoteClasificacion`, `PesadaEntrada`, `DetalleVentaCredito` y `DesechoInventario`.

---

## 9. Señales (Signals)

Todas definidas en `core/models.py` (líneas 271-493). 14 receptores `@receiver` + 1 función helper. Efecto neto sobre `Clasificacion.stock_kg`:

### LoteClasificacion (3 señales)

| Receptor | Evento | Efecto |
|---|---|---|
| `captura_anterior_lote` | `pre_save` | Guarda `_old_kg_neto` para calcular diff |
| `actualiza_stock_lote_save` | `post_save` | `stock_kg += diff` (**suma**) |
| `actualiza_stock_lote_delete` | `post_delete` | `stock_kg -= kg_neto` |

### PesadaViaje (2 señales + helper)

| Receptor | Evento | Efecto |
|---|---|---|
| `sincronizar_lote_on_pesada_save` | `post_save` | Dispara `recalcular_lotes_viaje(viaje)` |
| `sincronizar_lote_on_pesada_delete` | `post_delete` | Dispara `recalcular_lotes_viaje(viaje)` |

**`recalcular_lotes_viaje(viaje)`:** Agrupa pesadas (excluyendo las sin clasificación) por `clasificacion_id` sumando `kg_neto`; hace upsert de `LoteClasificacion` y elimina lotes huérfanos. Los signals de `LoteClasificacion` actualizan el stock en cascada.

### DetalleVentaCredito (3 señales)

| Receptor | Evento | Efecto |
|---|---|---|
| `captura_anterior_venta_credito` | `pre_save` | Guarda `_old_kg_vendido` |
| `actualiza_stock_venta_credito_save` | `post_save` | `stock_kg -= kg_vendido` (**resta**) |
| `actualiza_stock_venta_credito_delete` | `post_delete` | `stock_kg += kg_vendido` (devuelve) |

### PesadaEntrada (3 señales)

| Receptor | Evento | Efecto |
|---|---|---|
| `captura_anterior_pesada_entrada` | `pre_save` | Guarda `_old_kg_neto` |
| `actualiza_stock_pesada_entrada_save` | `post_save` | `stock_kg += diff` (**suma**, vía `entrada.clasificacion`) |
| `actualiza_stock_pesada_entrada_delete` | `post_delete` | `stock_kg -= kg_neto` (usa `update()` directo) |

### DesechoInventario (3 señales)

| Receptor | Evento | Efecto |
|---|---|---|
| `captura_anterior_desecho` | `pre_save` | Guarda `_old_kg` |
| `actualiza_stock_desecho_save` | `post_save` | `stock_kg -= diff` (**resta**) |
| `actualiza_stock_desecho_delete` | `post_delete` | `stock_kg += kg` (devuelve) |

**Resumen del flujo de stock:**
- **Entradas (+):** `LoteClasificacion` (viajes), `PesadaEntrada` (entradas de inventario)
- **Salidas (−):** `DetalleVentaCredito` (ventas crédito), `DesechoInventario` (desechos)
- Las `PesadaViaje` no tocan stock directamente; lo hacen a través de `LoteClasificacion`

---

## 10. Flujos de Negocio Principales

### 10.1 Registro de Viajes y Pesadas

1. **`viaje_create`** — Registra un `Viaje` con datos básicos (proveedor, producto, fecha).
2. **`viaje_detail` → agregar pesadas** — Se agregan `PesadaViaje` (una o múltiples filas) indicando canastillas negras (1.6 kg c/u), de color (2.2 kg c/u), clasificación y kg bruto.
3. **Cálculo de kg neto:** `kg_neto = kg_bruto − (negras × 1.6 + colores × 2.2)`
4. **Señal `post_save` de `PesadaViaje`** → `recalcular_lotes_viaje()` agrupa por clasificación y crea/actualiza/elimina `LoteClasificacion`.
5. **Señales de `LoteClasificacion`** → **suman** `kg_neto` al `stock_kg` de la clasificación.
6. **Precio y pagos:** El precio total acordado se edita en el detalle; los pagos al proveedor (`viaje_pago_add`) crean `PagoProveedor` y **automáticamente un `Gasto`** vinculado (OneToOne) con categoría "Pagos a Proveedores".

### 10.2 Entradas de Inventario

1. **`entrada_inventario_create`** — Recibe múltiples filas de pesadas agrupadas por clasificación dentro de una transacción atómica.
2. Por cada grupo de clasificación se crea un `EntradaInventario` (con `precio_por_kg`) y sus `PesadaEntrada`.
3. **Señales de `PesadaEntrada`** → **suman** `kg_neto` al `stock_kg` (vía `entrada.clasificacion`).
4. La misma vista maneja `form_type='nomina'` y `form_type='desecho'` en la misma página.

### 10.3 Ventas en Efectivo

1. **`venta_efectivo_create`** — Registra `VentaEfectivo` con producto, kg_vendido, total_dia.
2. **`venta_efectivo_detail`** — Permite "finalizar venta" calculando cambio según monto pagado.
3. No descuenta stock automáticamente (gestionado vía `DetalleVentaEfectivo` en admin).

### 10.4 Ventas a Crédito

1. **`venta_credito_create`** — Crea la venta sin detalles.
2. **`venta_credito_detail`** — Agrega `DetalleVentaCredito` vía **AJAX** (`venta_credito_add_detalle_ajax`), indicando clasificación, kg y precio/kg.
3. **Señales de `DetalleVentaCredito`** → **restan** `kg_vendido` del `stock_kg` de la clasificación (con diff en edición).
4. Se registran `PagoVentaCredito` (abonos). `saldo_pendiente = total − total_pagado`.

### 10.5 Gastos y Pagos a Proveedores

1. **`gasto_list`** — Registra gastos diarios (categoría opcional, descripción, monto, fecha). Edición/eliminación por modales AJAX.
2. **Al pagar proveedor** (`viaje_pago_add`) — Transacción atómica: crea `PagoProveedor` + `Gasto` vinculado (OneToOne, CASCADE). Borrar el pago borra el gasto.

### 10.6 Nómina

- La nómina es un `Gasto` con `CategoriaGasto.nombre == 'Nómina'` (constante `NOMINA_CATEGORY_NAME`).
- Se registra desde el formulario de entrada de inventario, el resumen semanal, o directamente.
- Días de nómina: 10, 20 y 30 de cada mes.

### 10.7 Inventario Semanal

- `WeeklyInventory` por semana (lunes) con `initial_inventory_kg`.
- `total_inventory_kg = initial + entradas (PesadaEntrada) + viajes (LoteClasificacion)`.
- **Comando `reset_weekly_inventory`** — Copia el total de la semana anterior como inicial de la nueva (reset de lunes).
- El dashboard y el resumen semanal muestran métricas de inventario en tiempo real.

### 10.8 Dashboard

- Agrega métricas del día: efectivo, crédito, abonos, gastos, balance.
- Cuentas por cobrar, viajes recientes, últimas ventas.
- Métricas de inventario de mandarina: inicial, compras, vendido, desechos (kg y toneladas).
- Gráficos Chart.js: ventas vs gastos (7 días) y distribución de ingresos.
- Acceso al inventario semanal actual.

---

## 11. Dependencias Completas

| Librería | Versión | Propósito |
|---|---|---|
| Django | 4.2.30 | Framework web (LTS 4.2) |
| gunicorn | 25.3.0 | Servidor WSGI producción |
| psycopg2-binary | 2.9.12 | Driver PostgreSQL |
| python-dotenv | 1.2.2 | Carga de `.env` |
| pillow | 12.2.0 | Procesamiento imágenes (ImageField) |
| whitenoise | 6.12.0 | Servicio de estáticos en producción |
| asgiref | 3.11.1 | Dependencia ASGI |
| packaging | 26.2 | Utilidad de versiones |
| sqlparse | 0.5.5 | Parseo SQL (dependencia Django) |

**CDN externos (sin versión fija, cargados en base.html):**
- Bootstrap 5.3.0 (CSS + JS)
- Bootstrap Icons 1.11.0
- Choices.js 10.2.0 (CSS + JS)
- Chart.js 4.4.0
- Google Fonts (Poppins, Inter)

---

## 12. Archivos de Mantenimiento / No Usados

### `core/patch.ps1` y `core/patch2.ps1`
Scripts PowerShell con rutas Windows hardcodeadas (`C:\Users\samue\Downloads\...`). Buscan e inyectan bloques HTML en `viaje_detail.html`. Son de desarrollo/migración de plantilla, **no son parte del runtime**. `patch2.ps1` define un bloque "Distribuir Neto en Clasificaciones" que no está integrado en la versión actual del template.

### `core/replace.py`
Equivalente Python de `patch2.ps1`. Misma lógica de reemplazo de HTML con rutas Windows. No integrado.

### `temp_js.txt`
Fragmento de JavaScript suelto con la función `calcularTotales()` para el bloque "Distribuir Neto en Clasificaciones" del `patch2.ps1`. Suma kg y dinero por fila, valida contra `netoPagable`, deshabilita botón si se excede. Es un **borrador**, no incluido en ninguna plantilla activa.

### `initial_data.json` (171 líneas)
Fixture de Django (`python manage.py loaddata initial_data.json`) con datos semilla:
- 2 usuarios (`admin` / `admin1234` y `admin1`)
- 4 productos ("pepe", "Mandarina Primera", "Mandarina", "Limón")
- 6 clasificaciones del producto "pepe"
- 1 categoría de gasto ("Pagos a Proveedores")
- 1 proveedor ("sill") y 1 cliente ("sebas")

---

## 13. Requisitos a Cumplir / Mejoras Pendientes

### Seguridad (Crítico)

| Problema | Ubicación | Recomendación |
|---|---|---|
| `SECRET_KEY` hardcodeado | `fruta_system/settings.py:6` | Usar variable de entorno (`os.environ.get('SECRET_KEY')`) |
| `DEBUG = True` | `fruta_system/settings.py:7` | Establecer `DEBUG = os.environ.get('DEBUG', 'False') == 'True'` |
| `ALLOWED_HOSTS = ['*']` | `fruta_system/settings.py:8` | Restringir a dominios reales de producción |
| Sin `PASSWORD_VALIDATORS` | No configurados | Activar validadores de contraseña de Django |
| Sin `CSRF_TRUSTED_ORIGINS` | No configurado | Añadir para producción con HTTPS |
| Sin `SECURE_SSL_REDIRECT` / `SECURE_HSTS_*` | No configurados | Activar en producción con HTTPS |

### Base de Datos

| Problema | Recomendación |
|---|---|
| `db.sqlite3` incluido en el repo | Eliminar del repo (ya está en `.gitignore` pero el archivo existe) |
| No hay backups configurados | Implementar `django-dbbackup` o backups automáticos de PostgreSQL |

### Testing

| Problema | Recomendación |
|---|---|
| Solo 2 tests | Ampliar cobertura: modelos, señales, vistas POST con datos reales |
| `test_weekly_summary_post_creates_payroll_expense` falla | La URL `inventario_weekly_summary` no existe; corregir a `entrada_inventario_list` |
| Sin tests de frontend | Añadir tests con Selenium o al menos `Client` para flujos clave |

### Código

| Problema | Ubicación | Recomendación |
|---|---|---|
| `views.py` tiene 1739 líneas | Todo en un archivo | Separar por módulo: `views_viajes.py`, `views_ventas.py`, etc. |
| Señales en `models.py` | `core/models.py:271-493` | Mover a `core/signals.py` (mejor práctica Django) |
| `entrada_inventario_list.html` referencia variables inexistentes | Template | La vista delegada a `inventario_weekly_summary` no pasa `entradas`, `total_kg`, `total_valor` |
| Filtros no funcionales en `viaje_list.html` | Template | Los inputs de filtro no están dentro de un `<form>` |
| Scripts con rutas Windows hardcodeadas | `patch.ps1`, `patch2.ps1`, `replace.py` | Eliminar o actualizar con rutas relativas al proyecto |
| `temp_js.txt` suelto | Raíz del proyecto | Integrar en el template correspondiente o eliminar |

### UX / Funcionalidad

| Problema | Recomendación |
|---|---|
| Pesadas sin clasificación obligatoria | Añadir `required` al SELECT y validación backend en `pesada_add` (ya identificado) |
| Viaje `precio_total_acordado` = 0 por defecto | Mostrar advertencia si no se ha configurado antes de permitir cerrar el viaje |
| No hay paginación en tablas largas | Añadir `django.core.paginator` o datatables JS |

### Infraestructura

| Problema | Recomendación |
|---|---|
| Sin logging configurado | Añadir configuración `LOGGING` en `settings.py` |
| Sin email backend | Configurar SMTP para notificaciones (reseteo de contraseña, alertas) |
| Sin cache | Configurar `CACHES` (Redis/Memcached) para queries frecuentes del dashboard |
| Estáticos desde CDN (dependencia externa) | Considerar servir localmente con `collectstatic` para entornos sin internet |
| Sin `robots.txt` ni `sitemap` | No necesario para app interna, pero si se expone públicamente sí |

### Documentación

| Tarea | Estado |
|---|---|
| `README.md` | Existe pero es básico |
| `DOCUMENTACION.md` | **Este archivo** |
| Docstrings en vistas | Inexistentes — añadir |
| Diagrama de arquitectura | No existe — recomendable |

---

## 14. Comandos de Gestión Personalizados

| Comando | Descripción |
|---|---|
| `python manage.py reset_weekly_inventory [--date YYYY-MM-DD]` | Copia el inventario total de la semana anterior como inventario inicial de la semana actual (reset de lunes). Sin `--date`, usa la fecha actual. |

---

*Documentación generada el 2026-07-03. Última actualización del código: migración 0021_pesadaviaje_clasificacion (2026-06-27).*
