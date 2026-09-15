from ._common import *

__all__ = ['dashboard', 'resumen_dia_json', 'resumen_dia_guardar']


@login_required
def dashboard(request):
    hoy = date.today()
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha_sel = date.fromisoformat(fecha_param)
        except ValueError:
            fecha_sel = hoy
    else:
        fecha_sel = hoy

    ventas_efectivo_hoy = VentaEfectivo.objects.filter(fecha=hoy)
    ventas_credito_hoy = ventas_credito_with_totals(
        VentaCredito.objects.filter(fecha=hoy).select_related('cliente')
    )
    gastos_hoy = Gasto.objects.filter(fecha=hoy)
    abonos_hoy = PagoVentaCredito.objects.filter(fecha=hoy)

    resumen_sel = resumen_fecha(fecha_sel)
    
    total_ventas_efectivo = sum(v.total for v in ventas_efectivo_hoy)
    total_abonos = sum(a.monto for a in abonos_hoy)
    
    total_efectivo = total_ventas_efectivo + total_abonos
    
    # Credito del dia - Saldo pendiente
    saldo_credito_hoy = sum(v.saldo_pendiente for v in ventas_credito_hoy)
    total_credito_hoy = sum(v.total for v in ventas_credito_hoy)
    kg_credito_hoy = sum(v.total_kg for v in ventas_credito_hoy)
    num_ventas_credito = len(ventas_credito_hoy)
    total_vendido_dinero = total_ventas_efectivo + total_credito_hoy
    
    total_gastos = sum(g.monto for g in gastos_hoy)
    balance_hoy = total_efectivo - total_gastos
    
    # Cuanto hay que cobrar en total historico
    ventas_por_cobrar = [v for v in ventas_credito_with_totals(
        VentaCredito.objects.select_related('cliente').order_by('-fecha', '-id')
    ) if v.saldo_pendiente > 0]
    total_por_cobrar = sum(v.saldo_pendiente for v in ventas_por_cobrar)
    
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
    # 3a. Ventas en efectivo del día.
    #     Una venta en efectivo puede registrar los kg de dos formas: con líneas de
    #     detalle (DetalleVentaEfectivo) o directamente en el campo kg_vendido del
    #     encabezado (que es lo que crea el formulario de "Nueva Venta en Efectivo").
    #     Se usan los detalles cuando existen y, si no, el kg del encabezado.
    detalles_efectivo_todos = []
    ventas_efectivo_sin_detalle = []
    kg_vendido_efectivo = Decimal('0')
    for venta_ef in ventas_efectivo_hoy.select_related('producto', 'cliente').prefetch_related('detalles__producto'):
        detalles_venta = list(venta_ef.detalles.all())
        if detalles_venta:
            detalles_efectivo_todos.extend(detalles_venta)
            kg_vendido_efectivo += sum(d.kg_vendido for d in detalles_venta)
        else:
            kg_vendido_efectivo += venta_ef.kg_vendido or Decimal('0')
            ventas_efectivo_sin_detalle.append(venta_ef)
    
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
    for venta_ef in ventas_efectivo_sin_detalle:
        detalles_ventas.append({
            'tipo': 'Efectivo',
            'cliente': venta_ef.cliente.nombre if venta_ef.cliente else 'General',
            'producto': venta_ef.producto.nombre if venta_ef.producto else 'N/A',
            'kg_vendido': venta_ef.kg_vendido or Decimal('0'),
            'monto': venta_ef.total
        })
    for detalle in detalles_credito_hoy:
        detalles_ventas.append({
            'tipo': 'Crédito',
            'cliente': detalle.venta.cliente.nombre,
            'producto': detalle.clasificacion.producto.nombre if detalle.clasificacion and detalle.clasificacion.producto else 'N/A',
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
    
    fecha_anterior = fecha_sel - timedelta(days=1)
    fecha_siguiente = fecha_sel + timedelta(days=1)

    pago_form = PagoVentaCreditoForm()
    
    # Obtener datos de inventario semanal
    weekly_inv = get_current_week_inventory_data()
    
    ctx = {
        'hoy': hoy,
        'total_efectivo': total_efectivo,
        'total_ventas_efectivo': total_ventas_efectivo,
        'total_abonos': total_abonos,
        'total_credito_hoy': total_credito_hoy,
        'total_vendido_dinero': total_vendido_dinero,
        'kg_credito_hoy': kg_credito_hoy,
        'num_ventas_credito': num_ventas_credito,
        'saldo_credito_hoy': saldo_credito_hoy,
        'total_gastos': total_gastos,
        'balance_hoy': balance_hoy,
        'total_por_cobrar': total_por_cobrar,
        'ventas_por_cobrar': ventas_por_cobrar, 
        'ventas_pendientes': ventas_pendientes_top,
        'ultimas_ventas_hoy': ultimas_ventas_hoy_top,
        'resumen_sel': resumen_sel,
        'fecha_sel': fecha_sel,
        'fecha_anterior': fecha_anterior.isoformat(),
        'fecha_siguiente': fecha_siguiente.isoformat(),
        'es_hoy': fecha_sel == hoy,
        'num_ventas_efectivo': ventas_efectivo_hoy.count(),
        'num_abonos': abonos_hoy.count(),
        'num_ventas_credito': ventas_credito_hoy.count(),
        'pago_form': pago_form,
        'ventas_gastos_data': json.dumps(ventas_gastos_data),
        # Métricas de inventario
        'inventario_inicial_kg': inventario_inicial_kg,
        'inventario_inicial_toneladas': inventario_inicial_toneladas,
        'compras_hoy_kg': compras_hoy_kg,
        'compras_hoy_toneladas': compras_hoy_toneladas,
        'vendido_kg': total_kg_vendido,
        'vendido_toneladas': vendido_toneladas,
        'kg_vendido_efectivo': kg_vendido_efectivo,
        'kg_vendido_credito': kg_vendido_credito,
        'desechos_kg': desechos_kg,
        'desechos_toneladas': desechos_toneladas,
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


@login_required
def resumen_dia_json(request):
    """Devuelve el resumen de métricas de un día en JSON (para actualizar la tabla sin recargar)."""
    fecha_param = request.GET.get('fecha')
    try:
        fecha = date.fromisoformat(fecha_param) if fecha_param else date.today()
    except ValueError:
        fecha = date.today()
    r = resumen_fecha(fecha)
    data = {'fecha': fecha.isoformat(), 'manual': r['manual']}
    for campo in RESUMEN_CAMPOS:
        data[campo] = str(r[campo])
    return JsonResponse(data)


@login_required
def resumen_dia_guardar(request):
    """Guarda un valor manual del resumen diario (POST JSON)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'método no permitido'}, status=405)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    campo = body.get('campo')
    if campo not in RESUMEN_CAMPOS:
        return JsonResponse({'error': 'campo inválido'}, status=400)
    fecha_str = body.get('fecha')
    try:
        fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()
    except ValueError:
        return JsonResponse({'error': 'fecha inválida'}, status=400)

    resumen, _ = ResumenDiario.objects.get_or_create(fecha=fecha)
    valor = body.get('valor')
    if valor is None or str(valor).strip() == '':
        setattr(resumen, campo, None)
    else:
        try:
            setattr(resumen, campo, Decimal(str(valor)))
        except (InvalidOperation, ValueError):
            return JsonResponse({'error': 'valor inválido'}, status=400)
    resumen.save()

    r = resumen_fecha(fecha)
    return JsonResponse({'ok': True, 'campo': campo, 'valor': str(r[campo]), 'manual': r['manual'][campo]})
