# FrutaSystem - Sistema de Gestión de Frutas

## Requisitos
- Python 3.10+
- pip

## Instalación

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Aplicar migraciones
python manage.py migrate

# 3. Cargar datos iniciales (productos y clasificaciones)
python manage.py loaddata initial_data.json  # si aplica

# 4. Crear superusuario
python manage.py createsuperuser

# 5. Iniciar el servidor
python manage.py runserver
```

## Acceso
- URL: http://localhost:8000
- Usuario por defecto: **admin**
- Contraseña por defecto: **admin1234**
- **¡Cambiar la contraseña al primer uso!**

## Módulos
- **Dashboard**: Resumen del día
- **Ventas Efectivo**: Registro de caja del día
- **Ventas Crédito**: Ventas con seguimiento de cobros
- **Viajes / Entradas**: Registro de compras a proveedores con clasificaciones y canastillas
- **Gastos**: Gastos diarios por categoría
- **Inventario**: Liquidación semanal de inventario
- **Reportes**: Diario, cartera de clientes, deudas a proveedores
- **Maestros**: Clientes, Proveedores, Productos, Clasificaciones, Categorías

## Notas de Producción
Para despliegue en producción:
1. Cambiar `SECRET_KEY` en settings.py
2. Establecer `DEBUG = False`
3. Configurar `ALLOWED_HOSTS` con el dominio real
4. Usar PostgreSQL en lugar de SQLite
5. Configurar `STATIC_ROOT` y ejecutar `collectstatic`
6. Usar Gunicorn + Nginx
