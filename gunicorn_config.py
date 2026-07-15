"""Configuración recomendada de Gunicorn para producción."""

import multiprocessing

# Escuchar en localhost:8000 (Nginx va delante)
bind = '127.0.0.1:8000'

# Workers = (2 × CPUs) + 1  →  un buen punto de partida
workers = multiprocessing.cpu_count() * 2 + 1

# Cada worker recicla después de N peticiones (previene memory leaks)
max_requests = 1000
max_requests_jitter = 200

# Timeouts generosos para reportes pesados
timeout = 120
graceful_timeout = 30

# Log a stdout (capturado por systemd / supervisor)
accesslog = '-'
errorlog = '-'
loglevel = 'warning'

# Nombre del proceso (aparece en `ps aux` como "fruta-system")
proc_name = 'fruta-system'

# Env vars necesarias (ya cargadas por python-dotenv en settings.py)
# raw_env = ['DEBUG=False']
