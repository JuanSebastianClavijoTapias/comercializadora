from ._common import *

__all__ = ['venta_efectivo_create', 'venta_efectivo_edit', 'venta_efectivo_detail', 'detalle_venta_efectivo_delete', 'venta_efectivo_list', 'venta_efectivo_delete', 'venta_credito_list', 'venta_credito_create', 'venta_credito_add_detalle_ajax', 'venta_credito_detail', 'venta_credito_delete', 'venta_credito_pago_add', 'detalle_venta_delete', 'pago_venta_delete']


@login_required
def venta_efectivo_create(request):
    if request.method == 'POST':
        form = VentaEfectivoForm(request.POST)
        if form.is_valid():
            venta = form.save()
            messages.success(request, f'Venta registrada: {venta.producto} - {venta.kg_vendido} kg - ${venta.total}')
            return redirect(f"{reverse('venta_efectivo_list')}?fecha={venta.fecha.isoformat()}")
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
    fecha = request.GET.get('fecha', '')
    if request.GET.get('todas') == '1':
        ventas = VentaEfectivo.objects.select_related('producto').order_by('-fecha', '-pk')
        mostrar_todas = True
        fecha = ''
    elif fecha:
        ventas = VentaEfectivo.objects.filter(fecha=fecha).select_related('producto').order_by('-pk')
        mostrar_todas = False
    else:
        fecha = str(date.today())
        ventas = VentaEfectivo.objects.filter(fecha=fecha).select_related('producto').order_by('-pk')
        mostrar_todas = False

    total = sum(v.total for v in ventas)
    num_ventas = len(ventas)
    ctx = {
        'ventas': ventas,
        'total': total,
        'num_ventas': num_ventas,
        'fecha': fecha,
        'mostrar_todas': mostrar_todas,
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


@login_required
def venta_credito_list(request):
    from django.core.paginator import Paginator

    # Queryset anotado con totales en SQL (evita N+1 en las propiedades del modelo)
    ventas_qs = ventas_credito_with_totals(
        VentaCredito.objects.select_related('cliente', 'producto').order_by('-fecha', '-id')
    )

    paginator = Paginator(ventas_qs, 10)
    ventas = paginator.get_page(request.GET.get('page'))
    num_ventas = paginator.count

    # Totales globales con agregaciones de BD (2 queries), no en Python
    totales_detalle = DetalleVentaCredito.objects.aggregate(
        total=Coalesce(Sum(F('kg_vendido') * F('precio_por_kg'), output_field=DecimalField()), Value(0, output_field=DecimalField())),
        kg=Coalesce(Sum('kg_vendido'), Value(0, output_field=DecimalField())),
    )
    total_pagado = PagoVentaCredito.objects.aggregate(
        t=Coalesce(Sum('monto'), Value(0, output_field=DecimalField()))
    )['t']

    total_credito = totales_detalle['total']
    total_pendiente = total_credito - total_pagado
    total_kg_credito = totales_detalle['kg']

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
    """Registra ventas a crédito por filas. Al guardar, agrupa por cliente y crea
    una venta separada por cliente (nunca se mezclan)."""
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    clasificaciones = Clasificacion.objects.select_related('producto').order_by('producto__nombre', 'orden')

    if request.method == 'POST':
        ventas_creadas, errores = _guardar_ventas_credito(request)
        if errores:
            return render(request, 'core/ventas/venta_credito_nueva.html', {
                'clientes': clientes,
                'clasificaciones': clasificaciones,
                'form_errors': errores,
                'fecha_default': request.POST.get('fecha', date.today().isoformat()),
            })
        plural = 's' if ventas_creadas != 1 else ''
        messages.success(request, f'{ventas_creadas} venta{plural} registrada{plural}.')
        return redirect('venta_credito_list')

    return render(request, 'core/ventas/venta_credito_nueva.html', {
        'clientes': clientes,
        'clasificaciones': clasificaciones,
        'fecha_default': date.today().isoformat(),
    })


def _guardar_ventas_credito(request):
    """Agrupa las filas del formulario por cliente y crea/usa una venta por
    cliente. Todo dentro de una transacción. Devuelve ``(n_ventas, errores)``."""
    fecha = parse_fecha(request.POST.get('fecha'), date.today())

    rows = []
    i = 0
    while f'kg_vendido_{i}' in request.POST:
        cliente_id = (request.POST.get(f'cliente_{i}') or '').strip()
        clasif_id = (request.POST.get(f'clasificacion_{i}') or '').strip()
        kg_raw = (request.POST.get(f'kg_vendido_{i}') or '').strip()
        precio_raw = (request.POST.get(f'precio_por_kg_{i}') or '').strip()
        if cliente_id or clasif_id or kg_raw or precio_raw:
            rows.append((cliente_id, clasif_id, kg_raw, precio_raw))
        i += 1

    if not rows:
        return 0, ['Agrega al menos una fila con cliente, clasificación, kg y precio.']

    errores = []
    if any(not r[0] for r in rows):
        errores.append('Todas las filas deben tener un cliente.')
    if any(not r[1] for r in rows):
        errores.append('Todas las filas deben tener una clasificación.')
    if any(not r[2] for r in rows):
        errores.append('Todas las filas deben tener kg.')
    if any(not r[3] for r in rows):
        errores.append('Todas las filas deben tener precio por kg.')
    if errores:
        return 0, errores

    grupos = {}
    for cliente_id, clasif_id, kg_raw, precio_raw in rows:
        grupos.setdefault(cliente_id, []).append((clasif_id, kg_raw, precio_raw))

    try:
        with transaction.atomic():
            for cliente_id, items in grupos.items():
                cliente = Cliente.objects.get(pk=cliente_id)
                venta, _creada = resolver_venta_credito(cliente, fecha)
                for clasif_id, kg_raw, precio_raw in items:
                    clasificacion = Clasificacion.objects.get(pk=clasif_id)
                    DetalleVentaCredito.objects.create(
                        venta=venta,
                        clasificacion=clasificacion,
                        kg_vendido=Decimal(kg_raw),
                        precio_por_kg=Decimal(normalizar_precio_cop(precio_raw) or '0'),
                    )
                    if venta.producto_id is None:
                        venta.producto = clasificacion.producto
                        venta.save(update_fields=['producto'])
    except (Cliente.DoesNotExist, Clasificacion.DoesNotExist, InvalidOperation, ValueError):
        return 0, ['Hay datos inválidos en alguna fila (cliente, clasificación, kg o precio).']

    return len(grupos), []


@login_required
def venta_credito_add_detalle_ajax(request, pk):
    """Agrega un detalle a una venta a crédito existente (AJAX desde el detalle)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    venta = get_object_or_404(VentaCredito, pk=pk)
    detalle_form = DetalleVentaCreditoForm(request.POST)
    if not detalle_form.is_valid():
        return JsonResponse({'success': False, 'errors': detalle_form.errors})

    # En el detalle el select de cliente va deshabilitado (no se envía),
    # así que se cae al cliente ya asignado a la venta.
    cliente = detalle_form.cleaned_data.get('cliente') or venta.cliente
    if cliente is None:
        return JsonResponse({'success': False, 'errors': {'cliente': ['Selecciona el cliente de la venta.']}})
    if venta.cliente_id and venta.cliente_id != cliente.pk:
        return JsonResponse(
            {'success': False, 'errors': {'cliente': ['Esta venta pertenece a otro cliente.']}}
        )

    detalle = detalle_form.save(commit=False)
    detalle.venta = venta
    detalle.save()

    if venta.cliente_id is None:
        venta.cliente = cliente
        venta.producto = detalle.clasificacion.producto
        venta.save(update_fields=['cliente', 'producto'])

    detalle.clasificacion.refresh_from_db()
    venta.refresh_from_db()

    return JsonResponse({
        'success': True,
        'venta_id': venta.pk,
        'detalle': {
            'pk': detalle.pk,
            'clasificacion': f"{detalle.clasificacion.producto.nombre} - {detalle.clasificacion.nombre}",
            'kg_vendido': float(detalle.kg_vendido),
            'precio_por_kg': float(detalle.precio_por_kg),
            'total': float(detalle.total),
            'precio_por_kg_display': f"${detalle.precio_por_kg:.0f}",
            'total_display': f"${detalle.total:.0f}",
        },
        'cliente': {'id': venta.cliente_id, 'nombre': str(venta.cliente)} if venta.cliente else None,
        'resumen': {
            'total_venta': float(venta.total),
            'total_pagado': float(venta.total_pagado),
            'saldo_pendiente': float(venta.saldo_pendiente),
        },
    })


@login_required
def venta_credito_detail(request, pk):
    venta = get_object_or_404(VentaCredito, pk=pk)
    detalles = venta.detalles.select_related('clasificacion').all()
    pagos = venta.pagos.all()
    detalle_form = DetalleVentaCreditoForm(initial={'cliente': venta.cliente_id})  # Empty form for display only
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
