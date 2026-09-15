from ._common import *

__all__ = ['viaje_list', 'viaje_create', 'viaje_detail', 'pesada_add', 'pesada_delete', 'pesada_edit', 'pesada_update_field', 'desecho_clasificacion_update', 'viaje_pago_add', 'viaje_delete', 'viaje_precio_update', 'lote_delete', 'pago_proveedor_delete']


@login_required
def viaje_list(request):
    viajes = viajes_with_totals(Viaje.objects.select_related('proveedor', 'producto'))

    tipo_filtro = request.GET.get('tipo', '').strip()
    if tipo_filtro in dict(Viaje.Tipo.choices):
        viajes = viajes.filter(tipo=tipo_filtro)

    solo_pendientes = request.GET.get('pendiente_clasificar') == '1'
    viajes = list(viajes)
    if solo_pendientes:
        viajes = [v for v in viajes if v.pendiente_clasificar]

    num_viajes = len(viajes)
    total_kg = sum(v.total_kg_neto for v in viajes)
    total_costo = sum(v.total_valor for v in viajes)
    saldo_pendiente = sum(v.saldo_pendiente for v in viajes)
    return render(request, 'core/viajes/viaje_list.html', {
        'viajes': viajes,
        'tipo_filtro': tipo_filtro,
        'solo_pendientes': solo_pendientes,
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
    from decimal import Decimal
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
        'total_pagado_valor': float(viaje.total_pagado),
        'total_valor_actual': float(viaje.total_valor),
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
def pesada_update_field(request, pk):
    """AJAX: actualiza un campo editable de la pesada (kg_bruto, canastillas)."""
    pesada = get_object_or_404(PesadaViaje, pk=pk)
    field = request.POST.get('field', '')
    value = request.POST.get('value', '')

    allowed = {'kg_bruto', 'num_canastillas_negras', 'num_canastillas_colores', 'clasificacion'}
    if field not in allowed:
        return JsonResponse({'ok': False, 'error': 'Campo no permitido'}, status=400)

    try:
        if field == 'kg_bruto':
            pesada.kg_bruto = Decimal(value) if value else Decimal('0')
        elif field == 'clasificacion':
            pesada.clasificacion_id = int(value) if value else None
        else:
            pesada.__setattr__(field, int(value) if value else 0)
        pesada.save(update_fields=[field])
    except (ValueError, InvalidOperation) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    pesada.refresh_from_db()
    viaje = pesada.viaje
    return JsonResponse({
        'ok': True,
        'kg_bruto': float(pesada.kg_bruto),
        'peso_canastillas': float(pesada.peso_canastillas),
        'kg_neto': float(pesada.kg_neto),
        'total_kg_neto': float(viaje.kg_neto_despues_podrido),
        'total_valor': float(viaje.total_valor),
        'total_pagado': float(viaje.total_pagado),
        'saldo_pendiente': float(viaje.saldo_pendiente),
        'clasificacion_id': pesada.clasificacion_id,
        'clasificacion_label': str(pesada.clasificacion) if pesada.clasificacion_id else None,
    })


@login_required
def desecho_clasificacion_update(request, pk, clasificacion_pk):
    """AJAX: crea/actualiza/elimina el DesechoInventario de un viaje para una clasificación."""
    viaje = get_object_or_404(Viaje, pk=pk)
    clasificacion = get_object_or_404(Clasificacion, pk=clasificacion_pk)
    value = request.POST.get('value', '').strip()
    try:
        kg_val = Decimal(value) if value else Decimal('0')
    except InvalidOperation:
        return JsonResponse({'ok': False, 'error': 'Valor inválido'}, status=400)

    if kg_val > 0:
        DesechoInventario.objects.update_or_create(
            viaje=viaje, clasificacion=clasificacion,
            defaults={'fecha': viaje.fecha, 'kg': kg_val},
        )
    else:
        DesechoInventario.objects.filter(viaje=viaje, clasificacion=clasificacion).delete()

    return JsonResponse({'ok': True})


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
    """Actualiza el precio por kg acordado del viaje vía AJAX."""
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == 'POST':
        val = request.POST.get('precio_total_acordado', '').strip()
        val = val.replace('.', '').replace(',', '.')
        try:
            if val:
                precio = Decimal(val)
                if precio >= 0:
                    viaje.precio_total_acordado = precio
                    viaje.save(update_fields=['precio_total_acordado'])
                    return JsonResponse({
                        'ok': True,
                        'total_valor': float(viaje.total_valor),
                        'total_pagado': float(viaje.total_pagado),
                        'saldo_pendiente': float(viaje.saldo_pendiente),
                    })
                else:
                    return JsonResponse({'ok': False, 'error': 'El precio no puede ser negativo.'}, status=400)
            else:
                return JsonResponse({'ok': False, 'error': 'Ingrese un valor.'}, status=400)
        except (ValueError, InvalidOperation):
            return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)
    return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)


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
