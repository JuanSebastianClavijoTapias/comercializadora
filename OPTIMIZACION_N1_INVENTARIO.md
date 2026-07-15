# Optimización del N+1 en `get_weekly_history`

## 1. El problema

Cuando entrabas a **Inventario Semanal**, se ejecutaban **~80 consultas SQL**.

### ¿Por qué?

La función `get_weekly_history()` (archivo `core/views.py`) construía el historial de
semanas haciendo un **bucle** con 6 consultas **por cada semana**:

```python
# Antes del fix — patrón N+1
for week_start in todas_las_semanas:          # ej: 10 semanas
    Gasto.objects.filter(fecha__range=...)      # consulta 1
    Viaje.objects.filter(fecha__range=...)       # consulta 2
    VentaEfectivo.objects.filter(fecha...)       # consulta 3
    VentaCredito.objects.filter(fecha...)        # consulta 4
    PesadaEntrada.objects.filter(entrada...)     # consulta 5
    LoteClasificacion.objects.filter(viaje...)   # consulta 6
# Resultado: 6 × 10 = 60 consultas SOLO en esta función
```

Cada semana nueva de historial añadía **+6 consultas**.

### Consecuencia

- Con **10 semanas** de historial: ~60 consultas → 60 ms
- Con **50 semanas**: ~300 consultas → 300 ms
- Con **100 semanas**: ~600 consultas → 1 segundo

El sistema **se iba a volver más lento solo** con el tiempo,
sin que nadie tocara el código.

### ¿Por qué es malo aunque hoy ande rápido?

1. **Cada consulta tiene overhead**: Django ↔ PostgreSQL se comunican por red.
   Aunque cada consulta tarde 0.7ms, el ida-y-vuelta suma tiempo muerto.
2. **Escala linealmente con los datos**: cada semana añade +6 queries.
3. **Concurrencia**: si 3 usuarios entran a inventario a la vez,
   se multiplican las queries → contención en la base de datos.

---

## 2. La solución

En vez de preguntar "por cada semana", se pregunta **una sola vez**
con `filter(fecha__range=[min_date, max_date])` para todo el rango,
y se agrupan los resultados en Python por semana usando `get_week_monday(fecha)`.

### Después del fix

```python
# Después — 6 consultas en total, sin importar cuántas semanas haya
min_date = mondays[0]                    # fecha más antigua
max_date = mondays[-1] + 6 días          # fecha más reciente

# Una consulta por modelo, agrupada en Python
for g in Gasto.objects.filter(
    fecha__range=[min_date, max_date]     # ← 1 consulta para TODAS las semanas
).select_related('categoria'):
    semana = get_week_monday(g.fecha)
    datos_por_semana[semana]['gastos'] += g.monto

# ... lo mismo para Viaje, VentaEfectivo, VentaCredito,
#     PesadaEntrada, LoteClasificacion
```

### Resultado

| Métrica | Antes | Después |
|---|---|---|
| Queries por semana | 6 | 0 (consultas únicas agrupadas) |
| Queries totales (10 semanas) | ~68 | ~21 |
| Queries totales (50 semanas) | ~309 | ~21 |
| Queries totales (100 semanas) | ~609 | ~21 |
| Escala con el historial | Sí (lineal) | **No** (constante) |

Las ~21 queries restantes son:
- 7 de metadatos (`dates()` para encontrar qué semanas tienen datos)
- 6 de modelos (las consultas agrupadas)
- ~8 de infraestructura (axes, ORM, sesiones)

Este número **no crece** con más semanas de historial.

---

## 3. Optimización adicional

En la vista principal (`inventario_weekly_summary`) se cacheó el queryset
de `gastos_semana` evaluándolo una sola vez con `list()`, evitando que
los filtros `.filter()` y `.exclude()` re-evaluaran la consulta 3-4 veces.

```python
# Antes: cada filter()/exclude()/count() re-evaluaba el queryset
gastos_semana = Gasto.objects.filter(...)         # qs sin evaluar
nominas = gastos_semana.filter(...)                # → re-evalúa
operativos = gastos_semana.exclude(...)            # → re-evalúa
num_gastos = operativos.count()                    # → re-evalúa

# Después: una sola consulta, filtrado en Python
_gastos_list = list(Gasto.objects.filter(...))     # → evalúa 1 vez
nominas = [g for g in _gastos_list if es_nomina(g)]       # Python
operativos = [g for g in _gastos_list if not es_nomina(g)] # Python
num_gastos = len(operativos)                                # Python
```

### Queries ahorradas

| Lugar | Antes | Después |
|---|---|---|
| `gastos_semana.filter()` | 1 query | 0 (filtro en Python) |
| `gastos_semana.exclude()` | 1 query | 0 (filtro en Python) |
| `.count()` × 2 | 2 queries | 0 (usamos `len()`) |
| Template loop | 1 query | 0 (ya está en `list()`) |

---

## 4. Cómo verificar

Con `django-debug-toolbar` activo (solo en `DEBUG=True`), al entrar a
Inventario Semanal verás el panel SQL a la derecha con el conteo de
queries y el tiempo de cada una.

O desde la shell de Django:

```python
from core.views import get_weekly_history
from django.db import connection

connection.queries_log.clear()
result = get_weekly_history()
print(f'{len(result)} semanas en {len(connection.queries)} queries')
```

---

## 5. Regla general para evitar N+1 en Django

Siempre que veas esto en tu código:

```python
for item in lista:
    Modelo.objects.filter(campo=item.algo)  # ← dentro de un for
```

Es una **alarma de N+1**. La solución siempre es la misma:
1. Junta todos los IDs/datos que necesitas
2. Haz **una sola consulta** con `filter(campo__in=[...])`
3. Agrupa los resultados en Python con un `dict` o `defaultdict`

O si los datos están en la BD:
1. Usa `select_related()` para FKs
2. Usa `prefetch_related()` para reverse FKs
3. Usa `annotate()` con `Sum()` para agregaciones

---

*Fix implementado el 2026-07-14. Archivos modificados:
`core/views.py` (funciones `get_weekly_history` e `inventario_weekly_summary`).*