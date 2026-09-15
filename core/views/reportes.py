from ._common import *

__all__ = ['reporte_diario', 'reporte_cartera', 'reporte_proveedor']


@login_required
def reporte_diario(request):
    from collections import defaultdict
    fecha = request.GET.get('fecha', str(date.today()))
    ventas_ef = VentaEfectivo.objects.filter(fecha=fecha)
    ventas_cr = ventas_credito_with_totals(
        VentaCredito.objects.filter(fecha=fecha).select_related('cliente')
    )
    resumen_gastos = resumen_gastos_del_dia(fecha)
    gastos = resumen_gastos.gastos
    abonos = PagoVentaCredito.objects.filter(fecha=fecha).select_related('venta__cliente')
    total_efectivo = sum(v.total for v in ventas_ef)
    total_credito = sum(v.total for v in ventas_cr)
    total_abonos = sum(a.monto for a in abonos)
    total_gastos = resumen_gastos.total
    balance = total_efectivo + total_abonos - total_gastos
    total_kg_efectivo = sum(v.kg_vendido for v in ventas_ef)
    total_kg_credito = sum(v.total_kg for v in ventas_cr)
    total_kg_vendido = total_kg_efectivo + total_kg_credito
    total_ventas = total_efectivo + total_credito

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
        'total_kg_efectivo': total_kg_efectivo, 'total_kg_credito': total_kg_credito,
        'total_kg_vendido': total_kg_vendido, 'total_ventas': total_ventas,
        'historial_dias': historial_dias,
    }
    return render(request, 'core/reportes/reporte_diario.html', ctx)


@login_required
def reporte_cartera(request):
    ventas = ventas_credito_with_totals(
        VentaCredito.objects.select_related('cliente', 'producto').order_by('-fecha', '-id')
    )
    pendientes = [v for v in ventas if v.saldo_pendiente > 0]
    total_cartera = sum(v.saldo_pendiente for v in pendientes)
    return render(request, 'core/reportes/reporte_cartera.html', {'pendientes': pendientes, 'total_cartera': total_cartera})


@login_required
def reporte_proveedor(request):
    viajes = viajes_with_totals(
        Viaje.objects.select_related('proveedor', 'producto').order_by('-fecha', '-id')
    )
    pendientes = [v for v in viajes if v.saldo_pendiente > 0]
    total_deuda = sum(v.saldo_pendiente for v in pendientes)
    return render(request, 'core/reportes/reporte_proveedor.html', {'viajes': viajes, 'pendientes': pendientes, 'total_deuda': total_deuda})
