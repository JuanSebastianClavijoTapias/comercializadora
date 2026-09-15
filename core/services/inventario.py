"""Lógica de inventario semanal y stock valorizado.

Concentra el mecanismo de reset de lunes, el historial semanal agregado y el
cálculo de stock valorizado, para que las vistas no carguen consultas de negocio.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Subquery, OuterRef
from django.urls import reverse

from ..models import (
    CategoriaGasto, Clasificacion, EntradaInventario, Gasto, LoteClasificacion,
    PagoVentaCredito, PesadaEntrada, ResumenDiario, VentaCredito, VentaEfectivo,
    Viaje, WeeklyInventory,
)

__all__ = [
    'NOMINA_CATEGORY_NAME',
    'get_week_monday',
    'get_week_summary_url',
    'parse_week_start',
    'get_nomina_category',
    'get_or_create_weekly_inventory_for_monday',
    'get_or_create_weekly_inventory',
    'get_week_inventory_data',
    'get_current_week_inventory_data',
    'get_weekly_history',
    'week_has_data',
    'stock_valorizado',
]

NOMINA_CATEGORY_NAME = 'Nómina'


def get_week_monday(fecha):
    """Retorna el lunes de la semana de la fecha dada."""
    return fecha - timedelta(days=fecha.weekday())


def get_week_summary_url(week_start):
    return f"{reverse('entrada_inventario_list')}?week={week_start.isoformat()}"


def parse_week_start(raw_value):
    if not raw_value:
        return get_week_monday(date.today())
    try:
        return get_week_monday(date.fromisoformat(raw_value))
    except ValueError:
        return get_week_monday(date.today())


def get_nomina_category():
    categoria, _ = CategoriaGasto.objects.get_or_create(nombre=NOMINA_CATEGORY_NAME)
    return categoria


def get_or_create_weekly_inventory_for_monday(lunes):
    # Si ya existe, devuélvelo sin tocar
    try:
        weekly = WeeklyInventory.objects.get(week_start=lunes)
        return weekly, False
    except WeeklyInventory.DoesNotExist:
        pass
    # Al crear uno nuevo, tomar como inventario inicial la suma actual de stock
    stock_inicial = Clasificacion.objects.aggregate(
        total=Sum('stock_kg')
    )['total'] or Decimal('0')
    weekly = WeeklyInventory.objects.create(
        week_start=lunes,
        initial_inventory_kg=stock_inicial,
    )
    return weekly, True


def get_or_create_weekly_inventory(fecha):
    """Obtiene o crea el registro de inventario para la semana de la fecha dada."""
    return get_or_create_weekly_inventory_for_monday(get_week_monday(fecha))


def get_week_inventory_data(fecha):
    lunes = get_week_monday(fecha)
    domingo = lunes + timedelta(days=6)
    weekly = WeeklyInventory.objects.filter(week_start=lunes).first()

    if weekly:
        initial_inventory_kg = weekly.initial_inventory_kg
        total_inventory_kg = weekly.total_inventory_kg
    else:
        initial_inventory_kg = Decimal('0')
        pesadas = PesadaEntrada.objects.filter(entrada__fecha__range=[lunes, domingo])
        entradas_kg = sum(p.kg_neto for p in pesadas) or Decimal('0')
        lotes = LoteClasificacion.objects.filter(viaje__fecha__range=[lunes, domingo])
        viajes_kg = sum(l.kg_neto for l in lotes) or Decimal('0')
        total_inventory_kg = entradas_kg + viajes_kg
    return {
        'week_monday': lunes,
        'week_sunday': domingo,
        'initial_inventory_kg': initial_inventory_kg,
        'total_inventory_kg': total_inventory_kg,
        'weekly_record': weekly,
    }


def get_current_week_inventory_data():
    """Obtiene los datos de inventario inicial y total para la semana actual
    Lógica de reset de lunes:
    - Cada lunes, el inventario inicial = total de inventario del domingo anterior
    - El total de inventario = inicial + compras de esta semana

    Primera vez:
    - Si no existe semana anterior, usa el stock actual como inicial
    """
    return get_week_inventory_data(date.today())


def get_weekly_history():
    """
    Historial semanal: datos agregados de todas las semanas con datos.
    En vez de ejecutar 6 queries por semana (N+1), hace 6 queries
    para TODO el rango y agrupa en Python por get_week_monday().
    """
    week_starts = set(WeeklyInventory.objects.values_list('week_start', flat=True))
    for model in (Gasto, VentaEfectivo, VentaCredito, PagoVentaCredito, Viaje, EntradaInventario):
        week_starts.update(model.objects.dates('fecha', 'week'))

    if not week_starts:
        return []

    mondays = sorted({get_week_monday(week) for week in week_starts})
    mondays_set = set(mondays)

    if not mondays:
        return []

    min_date = mondays[0]
    max_date = mondays[-1] + timedelta(days=6)

    weekly_records = {
        r.week_start: r
        for r in WeeklyInventory.objects.filter(week_start__in=mondays_set)
    }

    # ---- 1 consulta por modelo (6 total), agrupada en dicts ----

    gastos_by_week = defaultdict(lambda: {'total': Decimal('0'), 'nomina': Decimal('0')})
    for g in Gasto.objects.filter(
        fecha__range=[min_date, max_date]
    ).select_related('categoria'):
        wm = get_week_monday(g.fecha)
        if wm in mondays_set:
            gastos_by_week[wm]['total'] += g.monto
            cat = getattr(g.categoria, 'nombre', None)
            if cat and cat.lower() == NOMINA_CATEGORY_NAME.lower():
                gastos_by_week[wm]['nomina'] += g.monto

    viajes_by_week = defaultdict(lambda: {'total': Decimal('0'), 'count': 0, 'list': []})
    for v in Viaje.objects.filter(
        fecha__range=[min_date, max_date]
    ).select_related('proveedor', 'producto'):
        wm = get_week_monday(v.fecha)
        if wm in mondays_set:
            viajes_by_week[wm]['total'] += v.precio_total_acordado
            viajes_by_week[wm]['count'] += 1
            viajes_by_week[wm]['list'].append(v)

    vef_by_week = defaultdict(lambda: {'total': Decimal('0'), 'count': 0})
    for v in VentaEfectivo.objects.filter(fecha__range=[min_date, max_date]):
        wm = get_week_monday(v.fecha)
        if wm in mondays_set:
            vef_by_week[wm]['total'] += v.total
            vef_by_week[wm]['count'] += 1

    vcr_by_week = defaultdict(lambda: {'total': Decimal('0'), 'count': 0})
    for v in VentaCredito.objects.filter(
        fecha__range=[min_date, max_date]
    ).prefetch_related('detalles'):
        wm = get_week_monday(v.fecha)
        if wm in mondays_set:
            vcr_by_week[wm]['total'] += v.total
            vcr_by_week[wm]['count'] += 1

    entradas_kg_by_week = defaultdict(Decimal)
    for p in PesadaEntrada.objects.filter(
        entrada__fecha__range=[min_date, max_date]
    ).select_related('entrada'):
        wm = get_week_monday(p.entrada.fecha)
        if wm in mondays_set:
            entradas_kg_by_week[wm] += p.kg_neto

    lotes_kg_by_week = defaultdict(Decimal)
    for l in LoteClasificacion.objects.filter(
        viaje__fecha__range=[min_date, max_date]
    ).select_related('viaje'):
        wm = get_week_monday(l.viaje.fecha)
        if wm in mondays_set:
            lotes_kg_by_week[wm] += l.kg_neto

    # ---- Ensamblar history list ----
    history = []
    for week_start in reversed(mondays):
        week_end = week_start + timedelta(days=6)
        record = weekly_records.get(week_start)

        gbw = gastos_by_week[week_start]
        vbbw = viajes_by_week[week_start]
        vefbw = vef_by_week[week_start]
        vcrbw = vcr_by_week[week_start]

        e_kg = entradas_kg_by_week.get(week_start, Decimal('0'))
        v_kg = lotes_kg_by_week.get(week_start, Decimal('0'))
        total_ventas = vefbw['total'] + vcrbw['total']
        total_inv_kg = (record.total_inventory_kg
                        if record else (e_kg + v_kg))

        history.append({
            'week_start': week_start,
            'week_end': week_end,
            'record': record,
            'initial_inventory_kg': (record.initial_inventory_kg
                                     if record else Decimal('0')),
            'total_inventory_kg': total_inv_kg,
            'nomina_total': gbw['nomina'],
            'gastos_total': gbw['total'],
            'viajes_total': vbbw['total'],
            'viajes_count': vbbw['count'],
            'viajes_list': vbbw['list'],
            'entradas_kg': e_kg,
            'viajes_kg': v_kg,
            'total_ventas': total_ventas,
            'ventas_ef_count': vefbw['count'],
            'ventas_cr_count': vcrbw['count'],
            'balance': total_ventas - gbw['total'],
        })

    return history


def week_has_data(lunes):
    """Devuelve True si existe algún registro con fecha en esa semana."""
    domingo = lunes + timedelta(days=6)
    rango = [lunes, domingo]
    return (
        EntradaInventario.objects.filter(fecha__range=rango).exists() or
        VentaEfectivo.objects.filter(fecha__range=rango).exists() or
        VentaCredito.objects.filter(fecha__range=rango).exists() or
        Gasto.objects.filter(fecha__range=rango).exists() or
        WeeklyInventory.objects.filter(week_start=lunes).exists()
    )


def stock_valorizado():
    """Devuelve las clasificaciones con stock > 0 y su último precio de compra."""
    latest_precio = EntradaInventario.objects.filter(
        clasificacion=OuterRef('pk')
    ).order_by('-fecha', '-id').values('precio_por_kg')[:1]
    items = list(
        Clasificacion.objects
        .filter(stock_kg__gt=0)
        .select_related('producto')
        .annotate(ultimo_precio=Subquery(latest_precio))
        .order_by('producto__nombre', 'orden')
    )
    for c in items:
        precio = c.ultimo_precio or Decimal('0')
        c.valor_stock = c.stock_kg * precio
    total_valor = sum(c.valor_stock for c in items)
    total_kg = sum(c.stock_kg for c in items)
    return {'items': items, 'total': total_valor, 'total_kg': total_kg}
