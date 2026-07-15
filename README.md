# FrutaSystem - Sistema de Gestión de Frutas

## Requisitos
- Python 3.10+
- PostgreSQL 14+
- pip

## Instalación (desarrollo local)

```bash
# 1. Clonar / copiar el proyecto
cd comercializadora

# 2. Entorno virtual + dependencias
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Copiar y editar .env
cp .env.example .env
# Editar .env: DEBUG=True, ALLOWED_HOSTS=localhost,..., DB_NAME, DB_USER, DB_PASSWORD

# 4. Generar SECRET_KEY (reemplaza la de .env)
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 5. Migraciones + datos semilla
python manage.py migrate
python manage.py loaddata initial_data.json  # opcional: clasificaciones y proveedor de demo

# 6. Superusuario
python manage.py createsuperuser

# 7. Arrancar
python manage.py runserver 0.0.0.0:9000
```

## Acceso
- URL: http://localhost:9000
- Admin: http://localhost:9000/admin/
- Usuario demo (si cargaste initial_data.json): **admin** / **admin1234**

---

## Despliegue en producción

### 1. Configurar `.env`

```env
DEBUG=False
SECRET_KEY=<genera una clave de 50+ caracteres>
ALLOWED_HOSTS=tudominio.com,www.tudominio.com
CSRF_TRUSTED_ORIGINS=https://tudominio.com,https://www.tudominio.com
ADMIN_URL=panel-g3st10n/              # cambiá esto por una URL difícil de adivinar
BEHIND_PROXY=True                     # si Nginx/Caddy termina HTTPS
SECURE_SSL_REDIRECT=False             # True si Django debe redirigir HTTP→HTTPS

DB_NAME=comercializadora
DB_USER=postgres
DB_PASSWORD=<contraseña_segura>
DB_HOST=localhost
DB_PORT=5432
CONN_MAX_AGE=300                      # mantener conexiones vivas 5 min
DB_USE_SSL=False                      # True si PostgreSQL usa SSL

AXES_FAILURE_LIMIT=5
AXES_COOLOFF_TIME=1
```

### 2. Archivos estáticos

```bash
python manage.py collectstatic --noinput
```

Los estáticos los sirve **Whitenoise** (sin necesidad de Nginx para esto).

### 3. Arrancar con Gunicorn

```bash
gunicorn fruta_system.wsgi:application \
    -c gunicorn_config.py \
    --daemon
```

El archivo `gunicorn_config.py` ya tiene workers, timeouts y logging configurados.

### 4. Nginx (proxy inverso)

```nginx
server {
    listen 443 ssl;
    server_name tudominio.com;

    ssl_certificate     /etc/ssl/certs/tudominio.pem;
    ssl_certificate_key /etc/ssl/private/tudominio.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /ruta/al/proyecto/staticfiles/;
    }
}

# Redirigir HTTP → HTTPS
server {
    listen 80;
    server_name tudominio.com;
    return 301 https://$host$request_uri;
}
```

### 5. Verificar seguridad

```bash
python manage.py check --deploy   # 0 warnings = OK
```

### 6. Seguridad adicional lista

| Protección | ¿Activa? | Cómo |
|---|---|---|
| Rate-limit en login | Sí | django-axes: 5 intentos → bloqueo 1h |
| Password policies | Sí | 8+ chars, no comunes, no solo números |
| Cookies solo HTTPS | Sí | `SECURE`, `HttpOnly`, `SameSite=Lax` |
| HSTS (1 año) | Sí | `SECURE_HSTS_SECONDS=31536000` |
| CSRF con HTTPS | Sí | `CSRF_TRUSTED_ORIGINS` obligatorio |
| Admin URL oculta | Sí | `ADMIN_URL` configurable en .env |
| Clickjacking | Sí | `X-Frame-Options: DENY` |
| Content-Type sniffing | Sí | `X-Content-Type-Options: nosniff` |
| Conexiones DB persistentes | Sí | `CONN_MAX_AGE=300` |
| Logs de seguridad | Sí | `logs/fruta.log` rota cada 5 MB |

### 7. Comandos útiles

```bash
# Reset de inventario semanal (los lunes)
python manage.py reset_weekly_inventory --date 2026-07-14

# Ver intentos de login bloqueados
python manage.py shell -c "from axes.models import AccessAttempt; print(AccessAttempt.objects.count())"
```
