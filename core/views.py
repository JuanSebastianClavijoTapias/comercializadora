from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, F, Count, Value, DecimalField, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from .models import *
from .forms import *

# ---- FUNCIONES AUXILIARES DE INVENTARIO SEMANAL ----

NOMINA_CATEGORY_NAME = 'Nómina'

def get_week_monday(fecha):
    """Retorna el lunes de la semana de la fecha dada"""
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
    """Obtiene o crea el registro de inventario para la semana de la fecha dada"""
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


# ---- Helpers para eliminar N+1 en reportes y dashboard ----
# Cada helper anota _total y _total_pagado con Subquery; las @property de los
# modelos los leen desde __dict__ y evitan disparar queries adicionales por fila.

def _ventas_credito_with_totals(qs=None):
    """VentaCredito con _total (suma detalles) y _total_pagado (suma pagos) anotados."""
    if qs is None:
        qs = VentaCredito.objects.all()
    total_sq = (
        DetalleVentaCredito.objects
        .filter(venta=OuterRef('pk'))
        .values('venta')
        .annotate(t=Sum(F('kg_vendido') * F('precio_por_kg'), output_field=DecimalField()))
        .values('t')
    )
    pagado_sq = (
        PagoVentaCredito.objects
        .filter(venta=OuterRef('pk'))
        .values('venta')
        .annotate(t=Sum('monto', output_field=DecimalField()))
        .values('t')
    )
    return qs.annotate(
        _total=Coalesce(Subquery(total_sq, output_field=DecimalField()),
                        Value(0, output_field=DecimalField())),
        _total_pagado=Coalesce(Subquery(pagado_sq, output_field=DecimalField()),
                               Value(0, output_field=DecimalField())),
    )


def _viajes_with_totals(qs=None):
    """Viaje con _total_pagado (suma pagos a proveedor) anotado.
    total_valor es solo el campo precio_total_acordado, no requiere anotación."""
    if qs is None:
        qs = Viaje.objects.all()
    pagado_sq = (
        PagoProveedor.objects
        .filter(viaje=OuterRef('pk'))
        .values('viaje')
        .annotate(t=Sum('monto', output_field=DecimalField()))
        .values('t')
    )
    return qs.annotate(
        _total_pagado=Coalesce(Subquery(pagado_sq, output_field=DecimalField()),
                               Value(0, output_field=DecimalField())),
    )

    

def get_weekly_history():
    """
    Historial semanal: datos agregados de todas las semanas con datos.
    En vez de ejecutar 6 queries por semana (N+1), hace 6 queries
    para TODO el rango y agrupa en Python por get_week_monday().
    """
    from collections import defaultdict

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

# ---- DASHBOARD ----
@login_required
def dashboard(request):
    hoy = date.today()
    ventas_efectivo_hoy = VentaEfectivo.objects.filter(fecha=hoy)
    ventas_credito_hoy = VentaCredito.objects.filter(fecha=hoy)
    gastos_hoy = Gasto.objects.filter(fecha=hoy)
    abonos_hoy = PagoVentaCredito.objects.filter(fecha=hoy)
    
    total_ventas_efectivo = sum(v.total for v in ventas_efectivo_hoy)
    total_abonos = sum(a.monto for a in abonos_hoy)
    
    total_efectivo = total_ventas_efectivo + total_abonos
    
    # Credito del dia - Saldo pendiente
    saldo_credito_hoy = sum(v.saldo_pendiente for v in ventas_credito_hoy)
    total_credito_hoy = sum(v.total for v in ventas_credito_hoy)
    
    total_gastos = sum(g.monto for g in gastos_hoy)
    balance_hoy = total_efectivo - total_gastos
    
    # Cuanto hay que cobrar en total historico
    ventas_por_cobrar = [v for v in _ventas_credito_with_totals(
        VentaCredito.objects.select_related('cliente').order_by('-fecha', '-id')
    ) if v.saldo_pendiente > 0]
    total_por_cobrar = sum(v.saldo_pendiente for v in ventas_por_cobrar)
    
    viajes_recientes = Viaje.objects.all().order_by('-id')[:5]
    ventas_pendientes_top = ventas_por_cobrar[:5]
    
    # 10 Últimas ventas del día (mezclando efectivo y crédito)
    ultimas_ventas = []
    for ve in ventas_efectivo_hoy:
        # Solo incluir si tiene detalles
        if ve.detalles.exists():
            productos = ', '.join([d.producto.nombre for d in ve.detalles.all()])
            ultimas_ventas.append({
                'tipo': 'Efectivo',
                'cliente': str(ve.cliente) if ve.cliente else 'General',
                'producto': productos,
                'monto': ve.total,
                'id': ve.id
            })
    for vc in ventas_credito_hoy:
        ultimas_ventas.append({
            'tipo': 'Crédito',
            'cliente': str(vc.cliente) if vc.cliente else 'General',
            'producto': str(vc.producto) if vc.producto else 'Varios',
            'monto': vc.total,
            'id': vc.id
        })
    
    # Ordenar por ID descendente (las más recientes arriba)
    ultimas_ventas.sort(key=lambda x: x['id'], reverse=True)
    ultimas_ventas_hoy_top = ultimas_ventas[:10]
    
    # Datos para gráfico: Últimos 7 días
    import json
    ventas_efectivo_7dias = []
    ventas_credito_7dias = []
    ventas_totales_7dias = []
    gastos_7dias = []
    labels_dias = []
    
    for i in range(6, -1, -1):  # 6 días atrás hasta hoy
        fecha_dia = hoy - timedelta(days=i)
        
        # Ventas efectivo
        ventas_ef_dia = VentaEfectivo.objects.filter(fecha=fecha_dia)
        total_ventas_ef_dia = sum(v.total for v in ventas_ef_dia)
        
        # Ventas crédito
        ventas_cr_dia = VentaCredito.objects.filter(fecha=fecha_dia)
        total_ventas_cr_dia = sum(v.total for v in ventas_cr_dia)
        
        # Total ventas
        total_ventas_dia = total_ventas_ef_dia + total_ventas_cr_dia
        
        # Gastos del día
        gastos_dia = Gasto.objects.filter(fecha=fecha_dia)
        total_gastos_dia = sum(g.monto for g in gastos_dia)
        
        ventas_efectivo_7dias.append(int(total_ventas_ef_dia))
        ventas_credito_7dias.append(int(total_ventas_cr_dia))
        ventas_totales_7dias.append(int(total_ventas_dia))
        gastos_7dias.append(int(total_gastos_dia))
        labels_dias.append(fecha_dia.strftime('%a'))  # Lunes, Martes, etc
    
    ventas_gastos_data = {
        'labels': labels_dias,
        'ventas_efectivo': ventas_efectivo_7dias,
        'ventas_credito': ventas_credito_7dias,
        'ventas_totales': ventas_totales_7dias,
        'gastos': gastos_7dias
    }
    
    # ---- MÉTRICAS DE INVENTARIO (TODOS LOS PRODUCTOS) ----
    
    # 1. INVENTARIO INICIAL: Stock total de todas las clasificaciones con stock > 0
    clasificaciones_todas = Clasificacion.objects.filter(stock_kg__gt=0).select_related('producto').order_by('producto__nombre', 'orden')
    inventario_inicial_kg = sum(c.stock_kg for c in clasificaciones_todas)
    inventario_inicial_toneladas = inventario_inicial_kg / 1000 if inventario_inicial_kg > 0 else Decimal('0')
    
    # Detalles de clasificaciones para modal
    detalles_inventario_inicial = []
    for clasificacion in clasificaciones_todas:
        detalles_inventario_inicial.append({
            'producto': clasificacion.producto.nombre,
            'nombre': clasificacion.nombre,
            'stock_kg': clasificacion.stock_kg,
            'stock_toneladas': clasificacion.stock_kg / 1000
        })
    
    # 2. COMPRAS DEL DÍA: Suma de kg_neto de lotes clasificados de viajes de hoy (todos los productos)
    lotes_hoy = LoteClasificacion.objects.filter(
        viaje__fecha=hoy,
    ).select_related('clasificacion__producto', 'viaje__proveedor')
    compras_hoy_kg = sum(lote.kg_neto for lote in lotes_hoy)
    compras_hoy_toneladas = compras_hoy_kg / 1000 if compras_hoy_kg > 0 else Decimal('0')
    
    # Detalles de compras para modal
    detalles_compras = []
    for lote in lotes_hoy:
        detalles_compras.append({
            'proveedor': lote.viaje.proveedor.nombre if lote.viaje.proveedor else 'N/A',
            'producto': lote.clasificacion.producto.nombre,
            'clasificacion': lote.clasificacion.nombre,
            'kg_neto': lote.kg_neto,
            'fecha': lote.viaje.fecha
        })
    
    # 3. VENDIDO: Suma de kg_vendido de todas las ventas de hoy (todos los productos)
    # 3a. Ventas en efectivo del día
    detalles_efectivo_todos = [d for v in ventas_efectivo_hoy for d in v.detalles.all()]
    kg_vendido_efectivo = sum(d.kg_vendido for d in detalles_efectivo_todos)
    
    # 3b. Ventas a crédito del día
    detalles_credito_hoy = DetalleVentaCredito.objects.filter(venta__fecha=hoy).select_related('clasificacion__producto', 'venta__cliente')
    kg_vendido_credito = sum(d.kg_vendido for d in detalles_credito_hoy)
    
    # Total vendido en kg y toneladas
    total_kg_vendido = kg_vendido_efectivo + kg_vendido_credito
    vendido_toneladas = total_kg_vendido / 1000 if total_kg_vendido > 0 else Decimal('0')
    
    # Detalles de ventas para modal
    detalles_ventas = []
    for detalle in detalles_efectivo_todos:
        detalles_ventas.append({
            'tipo': 'Efectivo',
            'cliente': detalle.venta.cliente.nombre if detalle.venta.cliente else 'General',
            'producto': detalle.producto.nombre if detalle.producto else 'N/A',
            'kg_vendido': detalle.kg_vendido,
            'monto': detalle.total
        })
    for detalle in detalles_credito_hoy:
        detalles_ventas.append({
            'tipo': 'Crédito',
            'cliente': detalle.venta.cliente.nombre,
            'clasificacion': detalle.clasificacion.nombre,
            'kg_vendido': detalle.kg_vendido,
            'monto': detalle.total
        })
    
    # 4. DESECHOS: kg_podridos de pesadas (legado) + DesechoInventario
    viajes_hoy = Viaje.objects.filter(fecha=hoy).select_related('proveedor', 'producto')
    desechos_kg_legado = sum(v.total_kg_podridos for v in viajes_hoy)
    desechos_inv_hoy = DesechoInventario.objects.filter(fecha=hoy).select_related('clasificacion__producto')
    desechos_kg_inv = sum(d.kg for d in desechos_inv_hoy)
    desechos_kg = desechos_kg_legado + desechos_kg_inv
    desechos_toneladas = desechos_kg / 1000 if desechos_kg > 0 else Decimal('0')

    # Detalles de desechos para modal
    detalles_desechos = []
    for pesada in PesadaViaje.objects.filter(
        viaje__in=viajes_hoy, kg_podridos__gt=0
    ).select_related('viaje__proveedor', 'viaje__producto', 'clasificacion'):
        detalles_desechos.append({
            'proveedor': pesada.viaje.proveedor.nombre if pesada.viaje.proveedor else 'N/A',
            'producto': pesada.viaje.producto.nombre if pesada.viaje.producto else 'N/A',
            'clasificacion': pesada.clasificacion.nombre if pesada.clasificacion else 'Sin clasificación',
            'kg_podridos': pesada.kg_podridos,
            'fecha': pesada.viaje.fecha,
            'observaciones': pesada.viaje.observaciones
        })
    for d in desechos_inv_hoy:
        detalles_desechos.append({
            'proveedor': '—',
            'producto': d.clasificacion.producto.nombre if d.clasificacion else 'N/A',
            'clasificacion': d.clasificacion.nombre if d.clasificacion else 'Sin clasificación',
            'kg_podridos': d.kg,
            'fecha': d.fecha,
            'observaciones': d.observaciones or '',
        })
    
    pago_form = PagoVentaCreditoForm()
    
    # Obtener datos de inventario semanal
    weekly_inv = get_current_week_inventory_data()
    
    ctx = {
        'hoy': hoy,
        'total_efectivo': total_efectivo,
        'total_ventas_efectivo': total_ventas_efectivo,
        'total_abonos': total_abonos,
        'total_credito_hoy': total_credito_hoy,
        'saldo_credito_hoy': saldo_credito_hoy,
        'total_gastos': total_gastos,
        'balance_hoy': balance_hoy,
        'total_por_cobrar': total_por_cobrar,
        'ventas_por_cobrar': ventas_por_cobrar, 
        'viajes_recientes': viajes_recientes,
        'ventas_pendientes': ventas_pendientes_top,
        'ultimas_ventas_hoy': ultimas_ventas_hoy_top,
        'num_ventas_efectivo': ventas_efectivo_hoy.count(),
        'num_abonos': abonos_hoy.count(),
        'num_ventas_credito': ventas_credito_hoy.count(),
        'pago_form': pago_form,
        'ventas_gastos_data': json.dumps(ventas_gastos_data),
        # Métricas de inventario
        'inventario_inicial_kg': inventario_inicial_kg,
        'inventario_inicial_toneladas': inventario_inicial_toneladas,
        'compras_hoy_kg': compras_hoy_kg,
        'vendido_kg': total_kg_vendido,
        'desechos_kg': desechos_kg,
        # Detalles para modales
        'detalles_inventario_inicial': detalles_inventario_inicial,
        'detalles_compras': detalles_compras,
        'detalles_ventas': detalles_ventas,
        'detalles_desechos': detalles_desechos,
        # Nómina
        'tiene_nomina_hoy': hoy.day in [10, 20, 30],
        # Inventario Semanal
        'weekly_initial_inventory_kg': weekly_inv['initial_inventory_kg'],
        'weekly_total_inventory_kg': weekly_inv['total_inventory_kg'],
        'week_monday': weekly_inv['week_monday'],
        'week_sunday': weekly_inv['week_sunday'],
    }
    return render(request, 'core/dashboard.html', ctx)

# ---- PROVEEDORES ----
@login_required
def proveedor_list(request):
    q = request.GET.get('q', '')
    proveedores = Proveedor.objects.filter(nombre__icontains=q) if q else Proveedor.objects.all()
    num_proveedores = proveedores.count()
    num_activos = proveedores.filter(activo=True).count()
    num_inactivos = proveedores.filter(activo=False).count()
    return render(request, 'core/catalogo/proveedor_list.html', {
        'proveedores': proveedores, 'q': q,
        'num_proveedores': num_proveedores, 'num_activos': num_activos, 'num_inactivos': num_inactivos
    })

@login_required
def proveedor_create(request):
    form = ProveedorForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Proveedor creado exitosamente.')
        return redirect('proveedor_list')
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': 'Nuevo Proveedor', 'back_url': 'proveedor_list'})

@login_required
def proveedor_edit(request, pk):
    obj = get_object_or_404(Proveedor, pk=pk)
    form = ProveedorForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Proveedor actualizado.')
        return redirect('proveedor_list')
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'proveedor_list'})

@login_required
def proveedor_delete(request, pk):
    obj = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Proveedor eliminado.')
        return redirect('proveedor_list')
    return render(request, 'core/genericos/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Proveedor', 'back_url': 'proveedor_list'})

# ---- CLIENTES ----
@login_required
def cliente_list(request):
    q = request.GET.get('q', '')
    clientes = Cliente.objects.filter(nombre__icontains=q) if q else Cliente.objects.all()
    num_clientes = clientes.count()
    num_activos = clientes.filter(activo=True).count()
    num_inactivos = clientes.filter(activo=False).count()
    return render(request, 'core/catalogo/cliente_list.html', {
        'clientes': clientes, 'q': q,
        'num_clientes': num_clientes, 'num_activos': num_activos, 'num_inactivos': num_inactivos
    })

@login_required
def cliente_create(request):
    form = ClienteForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cliente creado exitosamente.')
        return redirect('cliente_list')
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': 'Nuevo Cliente', 'back_url': 'cliente_list'})

@login_required
def cliente_edit(request, pk):
    obj = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cliente actualizado.')
        return redirect('cliente_list')
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'cliente_list'})

@login_required
def cliente_delete(request, pk):
    obj = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Cliente eliminado.')
        return redirect('cliente_list')
    return render(request, 'core/genericos/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Cliente', 'back_url': 'cliente_list'})

# ---- PRODUCTOS ----
@login_required
def producto_list(request):
    productos = Producto.objects.all()
    num_productos = productos.count()
    num_activos = productos.filter(activo=True).count()
    num_descuento = productos.filter(tiene_descuento_gobierno=True).count()
    return render(request, 'core/catalogo/producto_list.html', {
        'productos': productos,
        'num_productos': num_productos, 'num_activos': num_activos, 'num_descuento': num_descuento
    })

@login_required
def producto_create(request):
    form = ProductoForm(request.POST or None)
    if form.is_valid():
        prod = form.save()
        for i in range(1, 7):
            Clasificacion.objects.create(producto=prod, nombre=f'Clasificación {i}', orden=i)
        messages.success(request, 'Producto creado con 6 clasificaciones por defecto.')
        return redirect('producto_clasificaciones', pk=prod.pk)
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': 'Nuevo Producto', 'back_url': 'producto_list'})

@login_required
def producto_edit(request, pk):
    obj = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Producto actualizado.')
        return redirect('producto_list')
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'producto_list'})

@login_required
def producto_delete(request, pk):
    obj = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Producto eliminado.')
        return redirect('producto_list')
    return render(request, 'core/genericos/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Producto', 'back_url': 'producto_list'})

@login_required
def producto_clasificaciones(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    clasificaciones = producto.clasificaciones.all()
    form = ClasificacionForm(request.POST or None)
    if form.is_valid():
        clas = form.save(commit=False)
        clas.producto = producto
        clas.save()
        messages.success(request, 'Clasificación creada.')
        return redirect('producto_clasificaciones', pk=pk)
    return render(request, 'core/catalogo/producto_clasificaciones.html',
        {'producto': producto, 'clasificaciones': clasificaciones, 'form': form})

@login_required
def producto_stock_update(request, pk):
    """Actualiza el stock_kg de todas las clasificaciones de un producto de forma masiva."""
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        clasificaciones = producto.clasificaciones.all()
        actualizadas = 0
        for clas in clasificaciones:
            key = f'stock_{clas.pk}'
            if key in request.POST:
                val = request.POST[key].strip()
                try:
                    clas.stock_kg = Decimal(val) if val else Decimal('0')
                    clas.save(update_fields=['stock_kg'])
                    actualizadas += 1
                except Exception:
                    pass
        messages.success(request, f'Stock actualizado para {actualizadas} clasificación(es).')
    return redirect('producto_clasificaciones', pk=pk)

@login_required
def clasificacion_edit(request, pk):
    obj = get_object_or_404(Clasificacion, pk=pk)
    form = ClasificacionForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Clasificación actualizada.')
        return redirect('producto_clasificaciones', pk=obj.producto.pk)
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': f'Editar Clasificación', 'back_url': None, 'back_pk': obj.producto.pk})

# ---- CATEGORIAS GASTO ----
@login_required
def categoria_gasto_list(request):
    categorias = CategoriaGasto.objects.all()
    form = CategoriaGastoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Categoría creada.')
        return redirect('categoria_gasto_list')
    return render(request, 'core/gastos/categoria_gasto_list.html', {'categorias': categorias, 'form': form})

@login_required
def categoria_gasto_edit(request, pk):
    obj = get_object_or_404(CategoriaGasto, pk=pk)
    form = CategoriaGastoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Categoría actualizada.')
        return redirect('categoria_gasto_list')
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'categoria_gasto_list'})

@login_required
def categoria_gasto_delete(request, pk):
    obj = get_object_or_404(CategoriaGasto, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Categoría eliminada.')
        return redirect('categoria_gasto_list')
    return render(request, 'core/genericos/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Categoría', 'back_url': 'categoria_gasto_list'})

# ---- VIAJES ----
@login_required
def viaje_list(request):
    viajes = Viaje.objects.select_related('proveedor', 'producto').all()
    num_viajes = len(viajes)
    total_kg = sum(v.total_kg_neto for v in viajes)
    total_costo = sum(v.total_valor for v in viajes)
    saldo_pendiente = sum(v.saldo_pendiente for v in viajes)
    return render(request, 'core/viajes/viaje_list.html', {
        'viajes': viajes,
        'num_viajes': num_viajes, 'total_kg': total_kg,
        'total_costo': total_costo, 'saldo_pendiente': saldo_pendiente
    })

@login_required
def viaje_create(request):
    form = ViajeForm(request.POST or None)
    if form.is_valid():
        viaje = form.save(commit=False)
        selected = form.cleaned_data['productos']
        if selected:
            viaje.producto = selected[0]
        viaje.save()
        viaje.productos.set(form.cleaned_data['productos'])
        messages.success(request, 'Viaje registrado. Ahora ingrese las pesadas del viaje.')
        return redirect('viaje_detail', pk=viaje.pk)
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': 'Registrar Nuevo Viaje', 'back_url': 'viaje_list'})

@login_required
def viaje_detail(request, pk):
    from decimal import Decimal, InvalidOperation
    viaje = get_object_or_404(Viaje, pk=pk)
    lotes = viaje.lotes.select_related('clasificacion').all()
    pesadas = viaje.pesadas.select_related('clasificacion__producto').all()

    # Clasificaciones de todos los productos seleccionados en el viaje
    productos_ids = list(viaje.productos.values_list('pk', flat=True))
    if viaje.producto_id and viaje.producto_id not in productos_ids:
        productos_ids.append(viaje.producto_id)
    clasificaciones = Clasificacion.objects.filter(
        producto_id__in=productos_ids, activo=True
    ).select_related('producto').order_by('producto__nombre', 'orden', 'nombre')

    # Nombre de todos los productos del viaje para mostrar en el resumen
    nombres = [p.nombre for p in viaje.productos.all()]
    if viaje.producto_id and viaje.producto.nombre not in nombres:
        nombres.insert(0, viaje.producto.nombre)
    viaje.nombres_productos = ', '.join(nombres)

    # Desglose de kg_neto por clasificacion (calculado desde las pesadas)
    kg_por_clasificacion = {}
    negras_por_clasificacion = {}
    colores_por_clasificacion = {}
    total_neto_clasificado = Decimal('0')
    for p in pesadas:
        if p.clasificacion_id is not None:
            if p.kg_neto is not None:
                kg_por_clasificacion[p.clasificacion_id] = (
                    kg_por_clasificacion.get(p.clasificacion_id, Decimal('0')) + p.kg_neto
                )
                total_neto_clasificado += p.kg_neto
            negras_por_clasificacion[p.clasificacion_id] = (
                negras_por_clasificacion.get(p.clasificacion_id, 0) + (p.num_canastillas_negras or 0)
            )
            colores_por_clasificacion[p.clasificacion_id] = (
                colores_por_clasificacion.get(p.clasificacion_id, 0) + (p.num_canastillas_colores or 0)
            )

    pagos = viaje.pagos_proveedor.all()
    pago_form = PagoProveedorForm()
    pesada_form = PesadaViajeForm()

    if request.method == 'POST' and request.POST.get('form_type') == 'desecho_viaje':
        # Borrar desechos previos de este viaje y crear los nuevos
        DesechoInventario.objects.filter(viaje=viaje).delete()
        guardados = 0
        for c in clasificaciones:
            kg = (request.POST.get(f'kg_desecho_{c.id}', '') or '').strip()
            if kg:
                try:
                    kg_val = Decimal(kg)
                    if kg_val > 0:
                        DesechoInventario.objects.create(
                            fecha=viaje.fecha,
                            clasificacion=c,
                            viaje=viaje,
                            kg=kg_val,
                        )
                        guardados += 1
                except InvalidOperation:
                    pass
        if guardados:
            messages.success(request, f'{guardados} desecho{"s" if guardados > 1 else ""} registrado{"s" if guardados > 1 else ""}.')
        else:
            messages.success(request, 'Desechos eliminados.')
        return redirect('viaje_detail', pk=pk)

    total_kg_neto = sum(lote.kg_neto for lote in lotes)

    # Cálculos de desglose de peso desde pesadas
    kg_bruto_total = viaje.kg_bruto
    peso_can_negras = sum((Decimal(str(p.num_canastillas_negras)) * Decimal('1.6') for p in pesadas), Decimal('0'))
    peso_can_colores = sum((Decimal(str(p.num_canastillas_colores)) * Decimal('2.2') for p in pesadas), Decimal('0'))
    cant_neg = sum(p.num_canastillas_negras for p in pesadas)
    cant_col = sum(p.num_canastillas_colores for p in pesadas)
    peso_total_canastillas = peso_can_negras + peso_can_colores

    # kg podrido: legado (PesadaViaje.kg_podridos) + DesechoInventario vinculado a este viaje
    desechos_viaje = DesechoInventario.objects.filter(viaje=viaje)
    desechos_extra_kg = desechos_viaje.aggregate(t=Sum('kg'))['t'] or Decimal('0')
    desecho_por_clasificacion = {}
    for d in desechos_viaje:
        cid = d.clasificacion_id
        desecho_por_clasificacion[cid] = desecho_por_clasificacion.get(cid, Decimal('0')) + d.kg

    kg_podrido = (viaje.total_kg_podridos or Decimal('0')) + desechos_extra_kg
    neto_final = max(kg_bruto_total - peso_total_canastillas - kg_podrido, Decimal('0'))

    # Adjuntar desecho por clasificación a cada pesada para el template
    for p in pesadas:
        p.desecho_kg = desecho_por_clasificacion.get(p.clasificacion_id, Decimal('0'))

    # Desglose por clasificación (kg_neto - desecho)
    desglose_clasificaciones = []
    for c in clasificaciones:
        kg = kg_por_clasificacion.get(c.id, Decimal('0'))
        if kg > 0:
            d_kg = desecho_por_clasificacion.get(c.id, Decimal('0'))
            desglose_clasificaciones.append({
                'clasificacion': c,
                'kg_neto': kg,
                'desecho_kg': d_kg,
                'kg_neto_final': kg - d_kg,
                'can_negras': negras_por_clasificacion.get(c.id, 0),
                'can_colores': colores_por_clasificacion.get(c.id, 0),
                'kg_can_negras': negras_por_clasificacion.get(c.id, 0) * Decimal('1.6'),
                'kg_can_colores': colores_por_clasificacion.get(c.id, 0) * Decimal('2.2'),
            })

    ctx = {
        'viaje': viaje,
        'pesadas': pesadas,
        'pesada_form': pesada_form,
        'clasificaciones': clasificaciones,
        'desglose_clasificaciones': desglose_clasificaciones,
        'total_neto_clasificado': float(total_neto_clasificado),
        'pagos': pagos,
        'pago_form': pago_form,
        'lotes': lotes,
        'total_kg_neto': total_kg_neto,
        # Desglose de cálculos
        'kg_bruto_total': float(kg_bruto_total),
        'kg_podrido': float(kg_podrido),
        'cant_neg': cant_neg,
        'cant_col': cant_col,
        'peso_can_negras': float(peso_can_negras),
        'peso_can_colores': float(peso_can_colores),
        'peso_total_canastillas': float(peso_total_canastillas),
        'neto_final': float(neto_final),
    }
    return render(request, 'core/viajes/viaje_detail.html', ctx)

@login_required
def pesada_add(request, pk):
    """Agrega una o varias pesadas (remesas de canastillas) al viaje."""
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == 'POST':
        # Detectar si vienen filas múltiples (campo kg_bruto_0 existe) o formulario simple
        if 'kg_bruto_0' in request.POST:
            guardadas = 0
            i = 0
            while f'kg_bruto_{i}' in request.POST:
                kg_bruto_val = request.POST.get(f'kg_bruto_{i}', '').strip()
                if kg_bruto_val:
                    clasif_id = request.POST.get(f'clasificacion_{i}', '').strip()
                    data = {
                        'num_canastillas_negras': request.POST.get(f'num_canastillas_negras_{i}', '') or '0',
                        'num_canastillas_colores': request.POST.get(f'num_canastillas_colores_{i}', '') or '0',
                        'kg_bruto': kg_bruto_val,
                        'clasificacion': clasif_id or None,
                    }
                    form = PesadaViajeForm(data)
                    if form.is_valid():
                        pesada = form.save(commit=False)
                        pesada.viaje = viaje
                        pesada.save()
                        guardadas += 1
                i += 1
            if guardadas:
                messages.success(request, f'{guardadas} pesada{"s" if guardadas > 1 else ""} registrada{"s" if guardadas > 1 else ""} correctamente.')
            else:
                messages.warning(request, 'No se ingresó ningún Kg Bruto válido.')
        else:
            form = PesadaViajeForm(request.POST)
            if form.is_valid():
                pesada = form.save(commit=False)
                pesada.viaje = viaje
                pesada.save()
                partes = []
                if pesada.num_canastillas_negras: partes.append(f'{pesada.num_canastillas_negras} negras')
                if pesada.num_canastillas_colores: partes.append(f'{pesada.num_canastillas_colores} colores')
                messages.success(request, f'Pesada registrada: {", ".join(partes) or "0 canastillas"} — {pesada.kg_bruto} kg bruto.')
            else:
                messages.error(request, 'Error al registrar la pesada. Verifique los datos.')
    return redirect('viaje_detail', pk=pk)


@login_required
def pesada_delete(request, pk):
    """Elimina una pesada."""
    pesada = get_object_or_404(PesadaViaje, pk=pk)
    viaje_pk = pesada.viaje_id
    pesada.delete()
    messages.success(request, 'Pesada eliminada.')
    return redirect('viaje_detail', pk=viaje_pk)


@login_required
def pesada_edit(request, pk):
    """Editar una pesada existente."""
    pesada = get_object_or_404(PesadaViaje, pk=pk)
    form = PesadaViajeForm(request.POST or None, instance=pesada)
    if form.is_valid():
        form.save()
        messages.success(request, 'Pesada actualizada.')
        return redirect('viaje_detail', pk=pesada.viaje_id)
    return render(request, 'core/genericos/form_generic.html', {
        'form': form,
        'titulo': f'Editar Pesada — {pesada.viaje.producto.nombre}',
        'back_url': 'viaje_detail',
        'back_url_args': [pesada.viaje_id],
    })


@login_required
def viaje_pago_add(request, pk):
    """
    Registra un pago al proveedor y automáticamente crea un gasto correspondiente.
    Usa transacciones para garantizar atomicidad: si falla el gasto, el pago no se registra.
    El gasto y el pago se vinculan con OneToOneField para sincronizar eliminaciones.
    """
    viaje = get_object_or_404(Viaje, pk=pk)
    form = PagoProveedorForm(request.POST)
    
    if form.is_valid():
        try:
            with transaction.atomic():
                # Crear el pago
                pago = form.save(commit=False)
                pago.viaje = viaje
                pago.save()
                
                # Obtener o crear la categoría "Pagos a Proveedores"
                try:
                    categoria_pagos = CategoriaGasto.objects.get(nombre='Pagos a Proveedores')
                except CategoriaGasto.DoesNotExist:
                    categoria_pagos = CategoriaGasto.objects.create(nombre='Pagos a Proveedores')
                
                # Crear automáticamente el gasto correspondiente
                descripcion = f'Pago a {viaje.proveedor.nombre} - {viaje.producto.nombre}'
                
                gasto = Gasto.objects.create(
                    categoria=categoria_pagos,
                    descripcion=descripcion,
                    monto=pago.monto,
                    fecha=pago.fecha,
                    pago_proveedor=pago
                )
                
                messages.success(
                    request, 
                    f'Pago de ${pago.monto:,.2f} registrado correctamente. Gasto automático creado.'
                )
                
        except Exception as e:
            messages.error(
                request, 
                f'Error al registrar el pago: {str(e)}. Intente nuevamente.'
            )
    else:
        messages.error(request, 'Datos de pago inválidos. Verifique los campos.')
    
    return redirect('viaje_detail', pk=pk)

@login_required
def viaje_delete(request, pk):
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == 'POST':
        viaje.delete()
        messages.success(request, 'Viaje eliminado satisfactoriamente.')
        return redirect('viaje_list')
    return render(request, 'core/genericos/confirm_delete.html', {'obj': viaje, 'tipo': 'Viaje', 'cancel_url': 'viaje_list'})

@login_required
def viaje_precio_update(request, pk):
    """Actualiza solo el precio total acordado del viaje desde el detalle."""
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == 'POST':
        val = request.POST.get('precio_total_acordado', '').strip()
        # Limpiar separadores de miles y normalizar separador decimal
        val = val.replace('.', '').replace(',', '.')  # Elimina puntos (miles), reemplaza coma por punto
        try:
            if val:
                precio = Decimal(val)
                if precio >= 0:
                    viaje.precio_total_acordado = precio
                    viaje.save(update_fields=['precio_total_acordado'])
                    messages.success(request, 'Precio acordado actualizado.')
                else:
                    messages.error(request, 'El precio no puede ser negativo.')
            else:
                messages.error(request, 'Por favor ingrese un valor.')
        except (ValueError, InvalidOperation):
            messages.error(request, 'Valor inválido para el precio acordado.')
    return redirect('viaje_detail', pk=pk)

@login_required
def lote_delete(request, pk):
    lote = get_object_or_404(LoteClasificacion, pk=pk)
    viaje_pk = lote.viaje.pk
    lote.delete()
    messages.success(request, 'Lote eliminado.')
    return redirect('viaje_detail', pk=viaje_pk)

@login_required
def pago_proveedor_delete(request, pk):
    """
    Elimina un pago al proveedor.
    Si hay un gasto vinculado, también se elimina automáticamente (por la relación OneToOneField).
    """
    pago = get_object_or_404(PagoProveedor, pk=pk)
    viaje_pk = pago.viaje.pk
    
    try:
        with transaction.atomic():
            # Verificar si hay un gasto vinculado
            tiene_gasto = hasattr(pago, 'gasto_generado') and pago.gasto_generado
            
            # Eliminar el pago (el gasto se elimina automáticamente por CASCADE)
            pago.delete()
            
            if tiene_gasto:
                messages.success(
                    request, 
                    'Pago y su gasto asociado eliminados correctamente.'
                )
            else:
                messages.success(request, 'Pago eliminado correctamente.')
                
    except Exception as e:
        messages.error(request, f'Error al eliminar el pago: {str(e)}')
    
    return redirect('viaje_detail', pk=viaje_pk)

# ---- GASTOS ----
@login_required
def gasto_list(request):
    fecha = request.GET.get('fecha', str(date.today()))
    gastos = Gasto.objects.filter(fecha=fecha)
    total = sum(g.monto for g in gastos)
    num_gastos = len(gastos)
    gasto_promedio = (total / num_gastos) if num_gastos > 0 else 0
    gasto_maximo = max((g.monto for g in gastos), default=0)

    form = GastoForm(request.POST or None, initial={'fecha': fecha})
    if form.is_valid():
        form.save()
        messages.success(request, 'Gasto registrado.')
        return redirect(f'/gastos/?fecha={fecha}')
    return render(request, 'core/gastos/gasto_list.html', {
        'gastos': gastos, 'total': total, 'form': form, 'fecha': fecha,
        'num_gastos': num_gastos, 'gasto_promedio': gasto_promedio, 'gasto_maximo': gasto_maximo
    })

@login_required
def gasto_edit(request, pk):
    obj = get_object_or_404(Gasto, pk=pk)
    form = GastoForm(request.POST or None, instance=obj)
    is_modal = request.GET.get('modal')
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Gasto actualizado.')
            if is_modal:
                return HttpResponse(status=204)
            return redirect('gasto_list')
    if is_modal:
        return render(request, 'core/gastos/gasto_edit_modal.html', {'form': form, 'gasto': obj})
    return render(request, 'core/genericos/form_generic.html', {'form': form, 'titulo': 'Editar Gasto', 'back_url': 'gasto_list'})

@login_required
def gasto_delete(request, pk):
    obj = get_object_or_404(Gasto, pk=pk)
    is_modal = request.GET.get('modal')
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Gasto eliminado.')
        if is_modal:
            return HttpResponse(status=204)
        return redirect('gasto_list')
    if is_modal:
        return render(request, 'core/gastos/gasto_delete_modal.html', {'gasto': obj, 'pk': pk})
    return render(request, 'core/genericos/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Gasto', 'back_url': 'gasto_list'})

@login_required
def gasto_detail(request, pk):
    gasto = get_object_or_404(Gasto.objects.select_related('categoria', 'pago_proveedor__viaje'), pk=pk)
    template = 'core/gastos/gasto_detail_modal.html' if request.GET.get('modal') else 'core/gastos/gasto_detail.html'
    return render(request, template, {'gasto': gasto})

@login_required
def weekly_inventory_edit(request, pk):
    weekly = get_object_or_404(WeeklyInventory, pk=pk)
    form = WeeklyInventoryForm(request.POST or None, instance=weekly)
    back_href = get_week_summary_url(weekly.week_start)

    if form.is_valid():
        form.save()
        messages.success(request, 'Inventario semanal actualizado.')
        return redirect(back_href)

    return render(request, 'core/genericos/form_generic.html', {
        'form': form,
        'titulo': f'Editar inventario semanal {weekly.week_start.strftime("%d/%m/%Y")}',
        'back_href': back_href,
    })

@login_required
def weekly_inventory_delete(request, pk):
    weekly = get_object_or_404(WeeklyInventory, pk=pk)
    back_href = get_week_summary_url(weekly.week_start)

    if request.method == 'POST':
        weekly.delete()
        messages.success(request, 'Semana eliminada del historial.')
        return redirect(reverse('entrada_inventario_list'))

    return render(request, 'core/genericos/confirm_delete.html', {
        'obj': weekly,
        'titulo': f'Eliminar semana {weekly.week_start.strftime("%d/%m/%Y")}',
        'back_href': back_href,
    })

@login_required
def nomina_edit(request, pk):
    nomina = get_object_or_404(
        Gasto.objects.select_related('categoria'),
        pk=pk,
        categoria__nombre__iexact=NOMINA_CATEGORY_NAME,
    )
    form = NominaForm(request.POST or None, instance=nomina)
    back_href = get_week_summary_url(get_week_monday(nomina.fecha))

    if form.is_valid():
        nomina = form.save(commit=False)
        nomina.categoria = get_nomina_category()
        nomina.save()
        messages.success(request, 'Nómina actualizada.')
        return redirect(get_week_summary_url(get_week_monday(nomina.fecha)))

    return render(request, 'core/genericos/form_generic.html', {
        'form': form,
        'titulo': 'Editar nómina',
        'back_href': back_href,
    })

@login_required
def nomina_delete(request, pk):
    nomina = get_object_or_404(
        Gasto.objects.select_related('categoria'),
        pk=pk,
        categoria__nombre__iexact=NOMINA_CATEGORY_NAME,
    )
    back_href = get_week_summary_url(get_week_monday(nomina.fecha))

    if request.method == 'POST':
        nomina.delete()
        messages.success(request, 'Nómina eliminada.')
        return redirect(back_href)

    return render(request, 'core/genericos/confirm_delete.html', {
        'obj': nomina,
        'titulo': 'Eliminar nómina',
        'back_href': back_href,
    })

# ---- VENTAS EFECTIVO ----
def _normalizar_precio_cop(valor):
    """Convierte un precio con formato colombiano (2.500) a Decimal (2500)."""
    if not valor:
        return ''
    return str(valor).replace('.', '').replace(',', '.').strip()


@login_required
def venta_efectivo_create(request):
    if request.method == 'POST':
        form = VentaEfectivoForm(request.POST)
        if form.is_valid():
            venta = form.save()
            messages.success(request, f'Venta registrada: {venta.producto} - {venta.kg_vendido} kg - ${venta.total}')
            return redirect('venta_efectivo_list')
    else:
        form = VentaEfectivoForm(initial={'fecha': date.today()})
    return render(request, 'core/ventas/venta_efectivo_create.html', {
        'form': form,
        'titulo': 'Nueva Venta en Efectivo',
    })

@login_required
def venta_efectivo_edit(request, pk):
    obj = get_object_or_404(VentaEfectivo, pk=pk)
    if request.method == 'POST':
        form = VentaEfectivoForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Venta actualizada.')
            return redirect('venta_efectivo_list')
    else:
        form = VentaEfectivoForm(instance=obj)
    return render(request, 'core/genericos/form_generic.html', {
        'form': form,
        'titulo': 'Editar Venta en Efectivo',
        'back_url': 'venta_efectivo_list',
    })

@login_required
def venta_efectivo_detail(request, pk):
    venta = get_object_or_404(VentaEfectivo.objects.select_related('producto'), pk=pk)
    if request.method == 'POST' and 'finalizar_venta' in request.POST:
        medio_pago = request.POST.get('medio_pago', 'efectivo')
        monto_pagado_str = request.POST.get('monto_pagado', '')
        monto_pagado = None
        if monto_pagado_str:
            monto_pagado_str = str(monto_pagado_str).replace(',', '.').replace('.', '', monto_pagado_str.count('.') - 1) if monto_pagado_str.count('.') > 1 else str(monto_pagado_str).replace('.', '')
            try:
                monto_pagado = float(monto_pagado_str)
            except (ValueError, TypeError):
                monto_pagado = None
        if not monto_pagado or monto_pagado <= 0:
            messages.error(request, 'Ingrese un monto pagado valido (debe ser mayor a 0).')
            return redirect('venta_efectivo_detail', pk=venta.pk)
        total_venta = float(venta.total)
        if monto_pagado >= total_venta:
            cambio = monto_pagado - total_venta
            messages.success(request, f'Venta registrada. Medio: {medio_pago.upper()} | Total: ${total_venta:.0f} | Cambio: ${cambio:.0f}')
        else:
            falta = total_venta - monto_pagado
            messages.warning(request, f'Pago incompleto. Falta: ${falta:.0f}')
        return redirect('venta_efectivo_list')
    return render(request, 'core/ventas/venta_efectivo_detail.html', {'venta': venta})

@login_required
def detalle_venta_efectivo_delete(request, pk):
    detalle = get_object_or_404(DetalleVentaEfectivo, pk=pk)
    venta_pk = detalle.venta.pk
    if request.method == 'POST':
        detalle.delete()
        messages.success(request, 'Detalle eliminado.')
    return redirect('venta_efectivo_detail', pk=venta_pk)

@login_required
def venta_efectivo_list(request):
    fecha = request.GET.get('fecha', str(date.today()))
    ventas = VentaEfectivo.objects.filter(fecha=fecha).select_related('producto').order_by('-pk')
    total = sum(v.total for v in ventas)
    num_ventas = len(ventas)
    ctx = {
        'ventas': ventas,
        'total': total,
        'num_ventas': num_ventas,
        'fecha': fecha,
    }
    return render(request, 'core/ventas/venta_efectivo_list.html', ctx)

@login_required
def venta_efectivo_delete(request, pk):
    obj = get_object_or_404(VentaEfectivo, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Venta eliminada.')
        return redirect('venta_efectivo_list')
    return render(request, 'core/genericos/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Venta Efectivo', 'back_url': 'venta_efectivo_list'})

# ---- VENTAS CREDITO ----
@login_required
def venta_credito_list(request):
    ventas = VentaCredito.objects.select_related('cliente', 'producto').all()
    num_ventas = len(ventas)
    total_credito = sum(v.total for v in ventas)
    total_pagado = sum(v.total_pagado for v in ventas)
    total_pendiente = sum(v.saldo_pendiente for v in ventas)
    total_kg_credito = DetalleVentaCredito.objects.aggregate(
        t=Coalesce(Sum('kg_vendido'), Value(0), output_field=DecimalField())
    )['t']
    ctx = {
        'ventas': ventas,
        'num_ventas': num_ventas,
        'total_credito': total_credito,
        'total_pagado': total_pagado,
        'total_pendiente': total_pendiente,
        'total_kg_credito': total_kg_credito,
    }
    return render(request, 'core/ventas/venta_credito_list.html', ctx)

@login_required
def venta_credito_create(request):
    """Crea una nueva venta a crédito (sin detalles, se agregan después)"""
    if request.method == 'POST':
        form = VentaCreditoForm(request.POST)
        if form.is_valid():
            venta = form.save()
            messages.success(request, 'Venta a crédito creada. Ahora agrega los productos vendidos.')
            return redirect('venta_credito_detail', pk=venta.pk)
    else:
        form = VentaCreditoForm(initial={'fecha': date.today()})
    return render(request, 'core/ventas/venta_credito_form.html', {
        'form': form,
        'titulo': 'Nueva Venta a Crédito',
        'back_url': 'venta_credito_list'
    })

@login_required
def venta_credito_add_detalle_ajax(request, pk):
    """Agrega un detalle de venta a crédito sin recargar la página (AJAX)"""
    import json
    venta = get_object_or_404(VentaCredito, pk=pk)
    
    if request.method == 'POST':
        detalle_form = DetalleVentaCreditoForm(request.POST)
        if detalle_form.is_valid():
            detalle = detalle_form.save(commit=False)
            detalle.venta = venta
            detalle.save()
            
            # Refrescar la clasificación para obtener el stock actualizado
            detalle.clasificacion.refresh_from_db()
            venta.refresh_from_db()
            
            # Retornar JSON con la nueva fila para agregar a la tabla
            response_data = {
                'success': True,
                'detalle': {
                    'pk': detalle.pk,
                    'clasificacion': f"{detalle.clasificacion.producto.nombre} - {detalle.clasificacion.nombre}",
                    'kg_vendido': float(detalle.kg_vendido),
                    'precio_por_kg': float(detalle.precio_por_kg),
                    'total': float(detalle.total),
                    'precio_por_kg_display': f"${detalle.precio_por_kg:.0f}",
                    'total_display': f"${detalle.total:.0f}",
                },
                'resumen': {
                    'total_venta': float(venta.total),
                    'total_pagado': float(venta.total_pagado),
                    'saldo_pendiente': float(venta.saldo_pendiente),
                },
            }
            return JsonResponse(response_data)
        else:
            return JsonResponse({'success': False, 'errors': detalle_form.errors})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def venta_credito_detail(request, pk):
    venta = get_object_or_404(VentaCredito, pk=pk)
    detalles = venta.detalles.select_related('clasificacion').all()
    pagos = venta.pagos.all()
    detalle_form = DetalleVentaCreditoForm()  # Empty form for display only
    pago_form = PagoVentaCreditoForm()
    ctx = {
        'venta': venta, 'detalles': detalles, 'pagos': pagos,
        'detalle_form': detalle_form, 'pago_form': pago_form,
    }
    return render(request, 'core/ventas/venta_credito_detail.html', ctx)

@login_required
def venta_credito_delete(request, pk):
    obj = get_object_or_404(VentaCredito, pk=pk)
    if 'next' in request.GET or 'next' in request.POST:
        next_url = request.GET.get('next') or request.POST.get('next')
    else:
        next_url = 'venta_credito_list'
        
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Venta a crédito y todos sus registros asociados fueron eliminados.')
        if next_url != 'venta_credito_list':
            return redirect(next_url)
        return redirect('venta_credito_list')
    
    return render(request, 'core/genericos/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Venta a Crédito', 'back_url': 'venta_credito_list'})

@login_required
def venta_credito_pago_add(request, pk):
    venta = get_object_or_404(VentaCredito, pk=pk)
    form = PagoVentaCreditoForm(request.POST)
    if form.is_valid():
        pago = form.save(commit=False)
        pago.venta = venta
        pago.save()
        messages.success(request, 'Pago registrado.')
    
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('venta_credito_detail', pk=pk)

@login_required
def detalle_venta_delete(request, pk):
    det = get_object_or_404(DetalleVentaCredito, pk=pk)
    venta_pk = det.venta.pk
    det.delete()
    messages.success(request, 'Detalle eliminado.')
    return redirect('venta_credito_detail', pk=venta_pk)

@login_required
def pago_venta_delete(request, pk):
    pago = get_object_or_404(PagoVentaCredito, pk=pk)
    venta_pk = pago.venta.pk
    pago.delete()
    messages.success(request, 'Pago eliminado.')
    return redirect('venta_credito_detail', pk=venta_pk)

# ---- REPORTES ----
@login_required
def reporte_diario(request):
    from collections import defaultdict
    fecha = request.GET.get('fecha', str(date.today()))
    ventas_ef = VentaEfectivo.objects.filter(fecha=fecha)
    ventas_cr = VentaCredito.objects.filter(fecha=fecha)
    gastos = Gasto.objects.filter(fecha=fecha)
    abonos = PagoVentaCredito.objects.filter(fecha=fecha).select_related('venta__cliente')
    total_efectivo = sum(v.total for v in ventas_ef)
    total_credito = sum(v.total for v in ventas_cr)
    total_abonos = sum(a.monto for a in abonos)
    total_gastos = sum(g.monto for g in gastos)
    balance = total_efectivo + total_abonos - total_gastos

    # Historial de los últimos 30 días
    thirty_days_ago = date.today() - timedelta(days=30)
    ef_by_date = (
        DetalleVentaEfectivo.objects
        .filter(venta__fecha__gte=thirty_days_ago)
        .values('venta__fecha')
        .annotate(total=Sum(F('kg_vendido') * Coalesce(F('precio_por_kg'), Value(0, output_field=DecimalField()))))
    )
    cr_by_date = (
        DetalleVentaCredito.objects
        .filter(venta__fecha__gte=thirty_days_ago)
        .values('venta__fecha')
        .annotate(total=Sum(F('kg_vendido') * F('precio_por_kg')))
    )
    abonos_by_date = (
        PagoVentaCredito.objects
        .filter(fecha__gte=thirty_days_ago)
        .values('fecha')
        .annotate(total=Sum('monto'))
    )
    gastos_by_date = (
        Gasto.objects
        .filter(fecha__gte=thirty_days_ago)
        .values('fecha')
        .annotate(total=Sum('monto'))
    )
    history_dict = defaultdict(lambda: {
        'efectivo': Decimal('0'), 'credito': Decimal('0'),
        'abonos': Decimal('0'), 'gastos': Decimal('0'),
    })
    for row in ef_by_date:
        history_dict[row['venta__fecha']]['efectivo'] = row['total'] or Decimal('0')
    for row in cr_by_date:
        history_dict[row['venta__fecha']]['credito'] = row['total'] or Decimal('0')
    for row in abonos_by_date:
        history_dict[row['fecha']]['abonos'] = row['total'] or Decimal('0')
    for row in gastos_by_date:
        history_dict[row['fecha']]['gastos'] = row['total'] or Decimal('0')
    historial_dias = sorted([
        {
            'fecha': d,
            'efectivo': v['efectivo'],
            'credito': v['credito'],
            'abonos': v['abonos'],
            'gastos': v['gastos'],
            'balance': v['efectivo'] + v['abonos'] - v['gastos'],
        }
        for d, v in history_dict.items()
    ], key=lambda x: x['fecha'], reverse=True)

    ctx = {
        'fecha': fecha, 'ventas_ef': ventas_ef, 'ventas_cr': ventas_cr,
        'gastos': gastos, 'abonos': abonos,
        'total_efectivo': total_efectivo, 'total_abonos': total_abonos,
        'total_credito': total_credito, 'total_gastos': total_gastos, 'balance': balance,
        'historial_dias': historial_dias,
    }
    return render(request, 'core/reportes/reporte_diario.html', ctx)

@login_required
def reporte_cartera(request):
    ventas = _ventas_credito_with_totals(
        VentaCredito.objects.select_related('cliente', 'producto').order_by('-fecha', '-id')
    )
    pendientes = [v for v in ventas if v.saldo_pendiente > 0]
    total_cartera = sum(v.saldo_pendiente for v in pendientes)
    return render(request, 'core/reportes/reporte_cartera.html', {'pendientes': pendientes, 'total_cartera': total_cartera})

@login_required
def reporte_proveedor(request):
    viajes = _viajes_with_totals(
        Viaje.objects.select_related('proveedor', 'producto').order_by('-fecha', '-id')
    )
    pendientes = [v for v in viajes if v.saldo_pendiente > 0]
    total_deuda = sum(v.saldo_pendiente for v in pendientes)
    return render(request, 'core/reportes/reporte_proveedor.html', {'viajes': viajes, 'pendientes': pendientes, 'total_deuda': total_deuda})

# ---- RESUMEN SEMANAL ----

def _week_has_data(lunes):
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


def _get_stock_valorizado():
    """Devuelve las clasificaciones con stock > 0 y su último precio de compra."""
    from django.db.models import Subquery, OuterRef
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

@login_required
def inventario_weekly_summary(request):
    """Vista para mostrar resumen, historial y edición de métricas semanales."""
    hoy = date.today()
    inicio_semana = parse_week_start(request.GET.get('week'))
    weekly_inv = get_week_inventory_data(inicio_semana)
    inicio_semana = weekly_inv['week_monday']
    fin_semana = weekly_inv['week_sunday']
    weekly_record = weekly_inv['weekly_record']

    default_nomina_date = hoy if inicio_semana <= hoy <= fin_semana else inicio_semana
    default_nomina_desc = f'Nómina semana {inicio_semana.strftime("%d/%m")} - {fin_semana.strftime("%d/%m")}'
    if request.method == 'POST' and request.POST.get('form_type') == 'nomina':
        nomina_form = NominaForm(request.POST)
        if nomina_form.is_valid():
            nomina = nomina_form.save(commit=False)
            if not inicio_semana <= nomina.fecha <= fin_semana:
                nomina_form.add_error('fecha', 'La fecha debe pertenecer a la semana seleccionada.')
            else:
                nomina.categoria = get_nomina_category()
                nomina.save()
                messages.success(request, 'Nómina registrada correctamente.')
                return redirect(get_week_summary_url(inicio_semana))
    else:
        nomina_form = NominaForm(initial={
            'fecha': default_nomina_date,
            'descripcion': default_nomina_desc,
        })

    # Evaluados una sola vez (list) para evitar re-ejecuciones del queryset
    _gastos_list = list(
        Gasto.objects.filter(
            fecha__range=[inicio_semana, fin_semana]
        ).select_related('categoria').order_by('-fecha', '-id')
    )
    nominas_semana = [
        g for g in _gastos_list
        if g.categoria and getattr(g.categoria, 'nombre', '') and
           g.categoria.nombre.lower() == NOMINA_CATEGORY_NAME.lower()
    ]
    gastos_operativos_semana = [
        g for g in _gastos_list
        if not (g.categoria and getattr(g.categoria, 'nombre', '') and
                g.categoria.nombre.lower() == NOMINA_CATEGORY_NAME.lower())
    ]
    total_gastos_semana = sum(g.monto for g in gastos_operativos_semana) or Decimal('0')
    monto_nomina = sum(g.monto for g in nominas_semana) or Decimal('0')

    ventas_efectivo_semana = VentaEfectivo.objects.filter(
        fecha__range=[inicio_semana, fin_semana]
    ).select_related('cliente').prefetch_related('detalles__producto').order_by('-fecha', '-id')
    total_efectivo_semana = sum(v.total for v in ventas_efectivo_semana) or Decimal('0')
    num_ventas_efectivo = ventas_efectivo_semana.count()
    promedio_efectivo = total_efectivo_semana / num_ventas_efectivo if num_ventas_efectivo else Decimal('0')

    abonos_semana = PagoVentaCredito.objects.filter(
        fecha__range=[inicio_semana, fin_semana]
    ).select_related('venta__cliente').order_by('-fecha', '-id')
    total_abonos_semana = sum(a.monto for a in abonos_semana) or Decimal('0')

    ventas_credito_semana = VentaCredito.objects.filter(
        fecha__range=[inicio_semana, fin_semana]
    ).select_related('cliente').prefetch_related('detalles', 'pagos').order_by('-fecha', '-id')
    total_credito_semana = sum(v.total for v in ventas_credito_semana) or Decimal('0')
    num_ventas_credito = ventas_credito_semana.count()
    promedio_credito = total_credito_semana / num_ventas_credito if num_ventas_credito else Decimal('0')

    total_ventas_semana = total_efectivo_semana + total_credito_semana

    viajes_semana = Viaje.objects.filter(
        fecha__range=[inicio_semana, fin_semana]
    ).select_related('proveedor').prefetch_related('lotes__clasificacion').order_by('-fecha', '-id')

    # Desechos: legado (PesadaViaje.kg_podridos) + DesechoInventario
    desechos_legado = PesadaViaje.objects.filter(
        viaje__in=viajes_semana, kg_podridos__gt=0
    ).select_related('viaje__proveedor', 'viaje__producto', 'clasificacion')
    desechos_inv_semana = DesechoInventario.objects.filter(
        fecha__range=[inicio_semana, fin_semana]
    ).select_related('clasificacion__producto')
    total_kg_podridos = (
        sum(p.kg_podridos for p in desechos_legado) +
        sum(d.kg for d in desechos_inv_semana)
    ) or Decimal('0')

    # Unificar en lista de dicts para el template
    desechos_semana = []
    for p in desechos_legado:
        desechos_semana.append({
            'proveedor': p.viaje.proveedor.nombre if p.viaje.proveedor else '—',
            'producto': p.viaje.producto.nombre if p.viaje.producto else '—',
            'clasificacion': p.clasificacion.nombre if p.clasificacion else '—',
            'kg': p.kg_podridos,
            'fecha': p.viaje.fecha,
        })
    for d in desechos_inv_semana:
        desechos_semana.append({
            'proveedor': '—',
            'producto': d.clasificacion.producto.nombre if d.clasificacion else '—',
            'clasificacion': d.clasificacion.nombre if d.clasificacion else '—',
            'kg': d.kg,
            'fecha': d.fecha,
        })
    desechos_semana.sort(key=lambda x: x['fecha'], reverse=True)

    # Desecho local (sin impacto en stock, solo conteo)
    desechos_locales = DesechoLocal.objects.filter(
        fecha__range=[inicio_semana, fin_semana]
    ).order_by('-fecha', '-id')
    total_desecho_local = sum(d.kg for d in desechos_locales) or Decimal('0')

    compras_semana = EntradaInventario.objects.filter(
        fecha__range=[inicio_semana, fin_semana]
    ).select_related('proveedor', 'clasificacion').prefetch_related('pesadas').order_by('-fecha', '-id')
    compras_semana_kg = sum(e.kg for e in compras_semana) or Decimal('0')
    total_compras_semana = sum(e.total for e in compras_semana) or Decimal('0')

    viajes_kg_semana = sum(
        sum(l.kg_neto for l in v.lotes.all()) for v in viajes_semana
    ) or Decimal('0')
    total_kg_ingresado_semana = compras_semana_kg + viajes_kg_semana

    ingresos_semana = []
    for e in compras_semana:
        ingresos_semana.append({
            'fecha': e.fecha, 'proveedor': e.proveedor, 'clasificacion': e.clasificacion,
            'kg': e.kg, 'precio_por_kg': e.precio_por_kg, 'total': e.total,
            'origen': 'Entrada', 'url': reverse('entrada_inventario_detail', args=[e.pk]),
        })
    for v in viajes_semana:
        for l in v.lotes.all():
            ingresos_semana.append({
                'fecha': v.fecha, 'proveedor': v.proveedor, 'clasificacion': l.clasificacion,
                'kg': l.kg_neto, 'precio_por_kg': None, 'total': None,
                'origen': 'Viaje', 'url': reverse('viaje_detail', args=[v.pk]),
            })
    ingresos_semana.sort(key=lambda x: (x['fecha'], 0 if x['origen'] == 'Entrada' else 1), reverse=True)

    balance_neto = total_ventas_semana - total_gastos_semana - monto_nomina
    dias_nomina = [10, 20, 30]
    tiene_nomina_hoy = hoy.day in dias_nomina
    dias_nomina_semana = [
        inicio_semana + timedelta(days=i)
        for i in range(7)
        if (inicio_semana + timedelta(days=i)).day in dias_nomina
    ]

    current_week_start = get_week_monday(hoy)
    next_week_start = inicio_semana + timedelta(days=7) if inicio_semana < current_week_start else None

    ctx = {
        'hoy': hoy,
        'inicio_semana': inicio_semana,
        'fin_semana': fin_semana,
        'weekly_record': weekly_record,
        'current_week_start': current_week_start,
        'previous_week_start': inicio_semana - timedelta(days=7),
        'previous_week_has_data': _week_has_data(inicio_semana - timedelta(days=7)),
        'next_week_start': next_week_start,
        'selected_week_is_current': inicio_semana == current_week_start,
        'total_gastos_semana': total_gastos_semana,
        'total_egresos_semana': total_gastos_semana + monto_nomina,
        'total_efectivo_semana': total_efectivo_semana,
        'total_credito_semana': total_credito_semana,
        'total_ventas_semana': total_ventas_semana,
        'total_abonos_semana': total_abonos_semana,
        'balance_neto': balance_neto,
        'total_kg_podridos': total_kg_podridos,
        'tiene_nomina_hoy': tiene_nomina_hoy,
        'dias_nomina_semana': dias_nomina_semana,
        'monto_nomina': monto_nomina,
        'num_gastos': len(gastos_operativos_semana),
        'num_nominas_semana': len(nominas_semana),
        'num_ventas_efectivo': num_ventas_efectivo,
        'num_ventas_credito': num_ventas_credito,
        'num_abonos_semana': abonos_semana.count(),
        'promedio_efectivo': promedio_efectivo,
        'promedio_credito': promedio_credito,
        'initial_inventory_kg': weekly_inv['initial_inventory_kg'],
        'total_inventory_kg': weekly_inv['total_inventory_kg'],
        'compras_semana_kg': compras_semana_kg,
        'total_compras_semana': total_compras_semana,
        'viajes_semana': viajes_semana,
        'total_viajes_semana': sum(v.precio_total_acordado for v in viajes_semana) or Decimal('0'),
        'viajes_kg_semana': viajes_kg_semana,
        'total_kg_ingresado_semana': total_kg_ingresado_semana,
        'gastos_semana': gastos_operativos_semana,
        'nominas_semana': nominas_semana,
        'ventas_efectivo_semana': ventas_efectivo_semana,
        'abonos_semana': abonos_semana,
        'ventas_credito_semana': ventas_credito_semana,
        'desechos_semana': desechos_semana,
        'desechos_locales': desechos_locales,
        'total_desecho_local': total_desecho_local,
        'compras_semana': compras_semana,
        'ingresos_semana': ingresos_semana,
        'weekly_history': get_weekly_history(),
        'nomina_form': nomina_form,
        'stock_valorizado': _get_stock_valorizado(),
    }

    return render(request, 'core/inventario/inventario_weekly_summary.html', ctx)


# ---- ENTRADAS DE INVENTARIO ----
@login_required
def entrada_inventario_list(request):
    return inventario_weekly_summary(request)


@login_required
def entrada_inventario_create(request):
    proveedores = Proveedor.objects.order_by('nombre')
    clasificaciones = Clasificacion.objects.select_related('producto').order_by('producto__nombre', 'nombre')

    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'entrada')

        if form_type == 'nomina':
            nomina_form = NominaForm(request.POST)
            desecho_local_form = DesechoLocalForm()
            if nomina_form.is_valid():
                nomina = nomina_form.save(commit=False)
                nomina.categoria = get_nomina_category()
                nomina.save()
                messages.success(request, 'Nómina registrada correctamente.')
                return redirect('entrada_inventario_create')
            return render(request, 'core/inventario/entrada_inventario_nueva.html', {
                'proveedores': proveedores, 'clasificaciones': clasificaciones,
                'fecha_default': date.today().isoformat(),
                'nomina_form': nomina_form, 'desecho_local_form': desecho_local_form,
            })

        if form_type == 'desecho':
            nomina_form = NominaForm(initial={'fecha': date.today()})
            desecho_local_form = DesechoLocalForm(request.POST)
            if desecho_local_form.is_valid():
                desecho_local_form.save()
                messages.success(request, 'Desecho registrado correctamente.')
                return redirect('entrada_inventario_create')
            return render(request, 'core/inventario/entrada_inventario_nueva.html', {
                'proveedores': proveedores, 'clasificaciones': clasificaciones,
                'fecha_default': date.today().isoformat(),
                'nomina_form': nomina_form, 'desecho_local_form': desecho_local_form,
            })

        # --- Entrada de inventario (default) ---
        form_errors = []
        fecha = request.POST.get('fecha', '').strip()
        proveedor_id = request.POST.get('proveedor', '').strip()

        if not fecha:
            form_errors.append('La fecha es requerida.')
        if not proveedor_id:
            form_errors.append('El proveedor es requerido.')

        # Parse pesada rows
        rows = []
        i = 0
        while f'kg_bruto_{i}' in request.POST:
            kg_val = request.POST.get(f'kg_bruto_{i}', '').strip()
            if kg_val:
                cid = request.POST.get(f'clasificacion_{i}', '').strip()
                precio_raw = request.POST.get(f'precio_por_kg_{i}', '0').strip().replace('.', '')
                try:
                    precio_val = Decimal(precio_raw) if precio_raw else Decimal('0')
                except InvalidOperation:
                    precio_val = Decimal('0')
                rows.append({
                    'clasificacion_id': cid,
                    'num_canastillas_negras': int(request.POST.get(f'num_canastillas_negras_{i}', 0) or 0),
                    'num_canastillas_colores': int(request.POST.get(f'num_canastillas_colores_{i}', 0) or 0),
                    'kg_bruto': kg_val,
                })
            i += 1

        if not rows:
            form_errors.append('Debes registrar al menos una pesada con Kg Bruto.')
        for r in rows:
            if not r['clasificacion_id']:
                form_errors.append('Todas las filas deben tener una clasificación seleccionada.')
                break

        if not form_errors:
            from collections import defaultdict
            groups = defaultdict(list)
            for row in rows:
                groups[row['clasificacion_id']].append(row)

            # Read precio per classification from receipt inputs
            precios = {}
            for cid in groups.keys():
                precio_raw = request.POST.get(f'precio_clasif_{cid}', '0').strip().replace('.', '')
                try:
                    precio_val = Decimal(precio_raw) if precio_raw else Decimal('0')
                    if precio_val > 0:
                        precios[cid] = precio_val
                except InvalidOperation:
                    pass
            try:
                with transaction.atomic():
                    last_pk = None
                    for cid, group_rows in groups.items():
                        entrada = EntradaInventario(
                            fecha=fecha,
                            proveedor_id=int(proveedor_id),
                            clasificacion_id=int(cid),
                            precio_por_kg=precios.get(cid, Decimal('0')),
                        )
                        entrada.full_clean()
                        entrada.save()
                        for row in group_rows:
                            PesadaEntrada.objects.create(
                                entrada=entrada,
                                num_canastillas_negras=row['num_canastillas_negras'],
                                num_canastillas_colores=row['num_canastillas_colores'],
                                kg_bruto=Decimal(row['kg_bruto']),
                            )
                        last_pk = entrada.pk
                messages.success(request, 'Entrada registrada correctamente.')
                if last_pk and len(groups) == 1:
                    return redirect('entrada_inventario_detail', pk=last_pk)
                return redirect('entrada_inventario_list')
            except Exception as e:
                form_errors.append(f'Error al guardar: {e}')

        return render(request, 'core/inventario/entrada_inventario_nueva.html', {
            'proveedores': proveedores,
            'clasificaciones': clasificaciones,
            'form_errors': form_errors,
            'fecha_default': request.POST.get('fecha', date.today().isoformat()),
            'proveedor_selected': proveedor_id,
            'nomina_form': NominaForm(initial={'fecha': date.today()}),
            'desecho_local_form': DesechoLocalForm(),
        })

    return render(request, 'core/inventario/entrada_inventario_nueva.html', {
        'proveedores': proveedores,
        'clasificaciones': clasificaciones,
        'fecha_default': date.today().isoformat(),
        'nomina_form': NominaForm(initial={'fecha': date.today()}),
        'desecho_local_form': DesechoLocalForm(),
    })


@login_required
def entrada_inventario_detail(request, pk):
    entrada = get_object_or_404(EntradaInventario.objects.select_related('proveedor', 'clasificacion__producto').prefetch_related('pesadas'), pk=pk)
    pesadas = entrada.pesadas.all()

    # Actualizar precio si se envía
    if request.method == 'POST' and request.POST.get('form_type') == 'precio':
        precio_form = EntradaInventarioForm(request.POST, instance=entrada)
        if precio_form.is_valid():
            precio_form.save()
            messages.success(request, 'Datos de la entrada actualizados.')
            return redirect('entrada_inventario_detail', pk=pk)
    else:
        precio_form = EntradaInventarioForm(instance=entrada)

    kg_bruto_total = sum(p.kg_bruto for p in pesadas)
    peso_total_canastillas = sum(p.peso_canastillas for p in pesadas)
    kg_neto_total = entrada.kg
    cant_neg = sum(p.num_canastillas_negras for p in pesadas)
    cant_col = sum(p.num_canastillas_colores for p in pesadas)

    return render(request, 'core/inventario/entrada_inventario_detail.html', {
        'entrada': entrada,
        'pesadas': pesadas,
        'precio_form': precio_form,
        'kg_bruto_total': kg_bruto_total,
        'peso_total_canastillas': peso_total_canastillas,
        'kg_neto_total': kg_neto_total,
        'cant_neg': cant_neg,
        'cant_col': cant_col,
    })


@login_required
def pesada_entrada_add(request, pk):
    entrada = get_object_or_404(EntradaInventario, pk=pk)
    if request.method == 'POST':
        if 'kg_bruto_0' in request.POST:
            guardadas = 0
            i = 0
            while f'kg_bruto_{i}' in request.POST:
                kg_bruto_val = request.POST.get(f'kg_bruto_{i}', '').strip()
                if kg_bruto_val:
                    data = {
                        'num_canastillas_negras': request.POST.get(f'num_canastillas_negras_{i}', '') or 0,
                        'num_canastillas_colores': request.POST.get(f'num_canastillas_colores_{i}', '') or 0,
                        'kg_bruto': kg_bruto_val,
                    }
                    form = PesadaEntradaForm(data)
                    if form.is_valid():
                        p = form.save(commit=False)
                        p.entrada = entrada
                        p.save()
                        guardadas += 1
                i += 1
            if guardadas:
                messages.success(request, f'{guardadas} pesada{"s" if guardadas > 1 else ""} registrada{"s" if guardadas > 1 else ""}.')
            else:
                messages.warning(request, 'No se ingresó ningún Kg Bruto válido.')
    return redirect('entrada_inventario_detail', pk=pk)


@login_required
def pesada_entrada_delete(request, pk):
    pesada = get_object_or_404(PesadaEntrada, pk=pk)
    entrada_pk = pesada.entrada_id
    pesada.delete()
    messages.success(request, 'Pesada eliminada.')
    return redirect('entrada_inventario_detail', pk=entrada_pk)


@login_required
def entrada_inventario_edit(request, pk):
    entrada = get_object_or_404(EntradaInventario, pk=pk)
    form = EntradaInventarioForm(request.POST or None, instance=entrada)
    if form.is_valid():
        form.save()
        messages.success(request, 'Entrada actualizada.')
        return redirect('entrada_inventario_detail', pk=pk)
    return render(request, 'core/genericos/form_generic.html', {
        'form': form,
        'titulo': 'Editar Entrada de Inventario',
        'back_url': 'entrada_inventario_list',
    })


@login_required
def entrada_inventario_delete(request, pk):
    entrada = get_object_or_404(EntradaInventario, pk=pk)
    if request.method == 'POST':
        entrada.delete()
        messages.success(request, 'Entrada eliminada.')
        return redirect('entrada_inventario_list')
    return render(request, 'core/genericos/confirm_delete.html', {
        'obj': entrada,
        'titulo': 'Eliminar Entrada de Inventario',
        'back_href': reverse('entrada_inventario_list'),
    })
