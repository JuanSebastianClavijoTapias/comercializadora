from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, F
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
from decimal import Decimal
from .models import *
from .forms import *

# ---- DASHBOARD ----
@login_required
def dashboard(request):
    hoy = date.today()
    ventas_efectivo_hoy = VentaEfectivo.objects.filter(fecha=hoy)
    ventas_credito_hoy = VentaCredito.objects.filter(fecha=hoy)
    gastos_hoy = Gasto.objects.filter(fecha=hoy)
    abonos_hoy = PagoVentaCredito.objects.filter(fecha=hoy)
    
    total_ventas_efectivo = sum(v.monto for v in ventas_efectivo_hoy)
    total_abonos = sum(a.monto for a in abonos_hoy)
    
    total_efectivo = total_ventas_efectivo + total_abonos
    
    # Credito del dia - Saldo pendiente
    saldo_credito_hoy = sum(v.saldo_pendiente for v in ventas_credito_hoy)
    total_credito_hoy = sum(v.total for v in ventas_credito_hoy)
    
    total_gastos = sum(g.monto for g in gastos_hoy)
    balance_hoy = total_efectivo - total_gastos
    
    # Cuanto hay que cobrar en total historico
    ventas_por_cobrar = [v for v in VentaCredito.objects.all().order_by('-fecha') if v.saldo_pendiente > 0]
    total_por_cobrar = sum(v.saldo_pendiente for v in ventas_por_cobrar)
    
    viajes_recientes = Viaje.objects.all().order_by('-id')[:5]
    ventas_pendientes_top = ventas_por_cobrar[:5]
    
    # 10 Últimas ventas del día (mezclando efectivo y crédito)
    ultimas_ventas = []
    for ve in ventas_efectivo_hoy:
        ultimas_ventas.append({
            'tipo': 'Efectivo',
            'cliente': str(ve.cliente) if ve.cliente else 'General',
            'producto': str(ve.producto) if ve.producto else 'Varios',
            'monto': ve.monto,
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
        total_ventas_ef_dia = sum(v.monto for v in ventas_ef_dia)
        
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
    
    pago_form = PagoVentaCreditoForm()
    
    ctx = {
        'hoy': hoy,
        'total_efectivo': total_efectivo,
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
    return render(request, 'core/proveedor_list.html', {
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
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': 'Nuevo Proveedor', 'back_url': 'proveedor_list'})

@login_required
def proveedor_edit(request, pk):
    obj = get_object_or_404(Proveedor, pk=pk)
    form = ProveedorForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Proveedor actualizado.')
        return redirect('proveedor_list')
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'proveedor_list'})

@login_required
def proveedor_delete(request, pk):
    obj = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Proveedor eliminado.')
        return redirect('proveedor_list')
    return render(request, 'core/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Proveedor', 'back_url': 'proveedor_list'})

# ---- CLIENTES ----
@login_required
def cliente_list(request):
    q = request.GET.get('q', '')
    clientes = Cliente.objects.filter(nombre__icontains=q) if q else Cliente.objects.all()
    num_clientes = clientes.count()
    num_activos = clientes.filter(activo=True).count()
    num_inactivos = clientes.filter(activo=False).count()
    return render(request, 'core/cliente_list.html', {
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
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': 'Nuevo Cliente', 'back_url': 'cliente_list'})

@login_required
def cliente_edit(request, pk):
    obj = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cliente actualizado.')
        return redirect('cliente_list')
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'cliente_list'})

@login_required
def cliente_delete(request, pk):
    obj = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Cliente eliminado.')
        return redirect('cliente_list')
    return render(request, 'core/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Cliente', 'back_url': 'cliente_list'})

# ---- PRODUCTOS ----
@login_required
def producto_list(request):
    productos = Producto.objects.all()
    num_productos = productos.count()
    num_activos = productos.filter(activo=True).count()
    num_descuento = productos.filter(tiene_descuento_gobierno=True).count()
    return render(request, 'core/producto_list.html', {
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
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': 'Nuevo Producto', 'back_url': 'producto_list'})

@login_required
def producto_edit(request, pk):
    obj = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Producto actualizado.')
        return redirect('producto_list')
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'producto_list'})

@login_required
def producto_delete(request, pk):
    obj = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Producto eliminado.')
        return redirect('producto_list')
    return render(request, 'core/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Producto', 'back_url': 'producto_list'})

@login_required
def producto_clasificaciones(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    clasificaciones = producto.clasificaciones.all()
    return render(request, 'core/producto_clasificaciones.html', {'producto': producto, 'clasificaciones': clasificaciones})

@login_required
def clasificacion_edit(request, pk):
    obj = get_object_or_404(Clasificacion, pk=pk)
    form = ClasificacionForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Clasificación actualizada.')
        return redirect('producto_clasificaciones', pk=obj.producto.pk)
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': f'Editar Clasificación', 'back_url': None, 'back_pk': obj.producto.pk})

# ---- CATEGORIAS GASTO ----
@login_required
def categoria_gasto_list(request):
    categorias = CategoriaGasto.objects.all()
    form = CategoriaGastoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Categoría creada.')
        return redirect('categoria_gasto_list')
    return render(request, 'core/categoria_gasto_list.html', {'categorias': categorias, 'form': form})

@login_required
def categoria_gasto_edit(request, pk):
    obj = get_object_or_404(CategoriaGasto, pk=pk)
    form = CategoriaGastoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Categoría actualizada.')
        return redirect('categoria_gasto_list')
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': f'Editar: {obj.nombre}', 'back_url': 'categoria_gasto_list'})

@login_required
def categoria_gasto_delete(request, pk):
    obj = get_object_or_404(CategoriaGasto, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Categoría eliminada.')
        return redirect('categoria_gasto_list')
    return render(request, 'core/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Categoría', 'back_url': 'categoria_gasto_list'})

# ---- VIAJES ----
@login_required
def viaje_list(request):
    viajes = Viaje.objects.select_related('proveedor', 'producto').all()
    num_viajes = len(viajes)
    total_kg = sum(v.total_kg_neto for v in viajes)
    total_costo = sum(v.total_valor for v in viajes)
    saldo_pendiente = sum(v.saldo_pendiente for v in viajes)
    return render(request, 'core/viaje_list.html', {
        'viajes': viajes,
        'num_viajes': num_viajes, 'total_kg': total_kg,
        'total_costo': total_costo, 'saldo_pendiente': saldo_pendiente
    })

@login_required
def viaje_create(request):
    form = ViajeForm(request.POST or None)
    if form.is_valid():
        viaje = form.save()
        messages.success(request, 'Viaje registrado. Ahora ingrese las pesadas del viaje.')
        return redirect('viaje_detail', pk=viaje.pk)
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': 'Registrar Nuevo Viaje', 'back_url': 'viaje_list'})

@login_required
def viaje_detail(request, pk):
    from decimal import Decimal, InvalidOperation
    viaje = get_object_or_404(Viaje, pk=pk)
    lotes = viaje.lotes.select_related('clasificacion').all()
    lotes_dict = {lote.clasificacion_id: lote for lote in lotes}
    pesadas = viaje.pesadas.all()

    clasificaciones = Clasificacion.objects.filter(
        producto=viaje.producto, activo=True
    ).order_by('orden', 'nombre')

    if request.method == 'POST' and 'guardar_clasificaciones' in request.POST:
        for c in clasificaciones:
            kg_str = request.POST.get(f'kg_neto_{c.id}', '')
            try:
                kg_val = Decimal(kg_str) if kg_str.strip() else Decimal('0')
            except InvalidOperation:
                kg_val = Decimal('0')
            if kg_val > 0:
                lote, created = LoteClasificacion.objects.get_or_create(
                    viaje=viaje, clasificacion=c, defaults={'kg_neto': kg_val}
                )
                if not created:
                    lote.kg_neto = kg_val
                    lote.save()
            else:
                if c.id in lotes_dict:
                    lotes_dict[c.id].delete()

        # Guardar automáticamente en inventario
        liq, _ = LiquidacionInventario.objects.get_or_create(
            fecha_inicio=viaje.fecha, fecha_fin=viaje.fecha,
            defaults={'observaciones': f'Entrada de viaje {viaje.id}'}
        )
        for lote in viaje.lotes.all():
            DetalleInventario.objects.filter(liquidacion=liq, clasificacion=lote.clasificacion).delete()
            DetalleInventario.objects.create(
                liquidacion=liq, clasificacion=lote.clasificacion,
                kg_ingresado=lote.kg_neto, kg_vendido=Decimal('0'),
                kg_restante=lote.kg_neto, precio_por_kg=Decimal('0')
            )
        messages.success(request, 'Clasificaciones guardadas y registradas en inventario.')
        return redirect('viaje_detail', pk=pk)

    # Pre-build data for the template
    clases_data = []
    for c in clasificaciones:
        ext_lote = lotes_dict.get(c.id)
        clases_data.append({
            'clasificacion': c,
            'kg_neto': float(ext_lote.kg_neto) if (ext_lote and ext_lote.kg_neto) else '',
        })

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
    kg_podrido = viaje.kg_podridos or Decimal('0')
    neto_final = max(kg_bruto_total - peso_total_canastillas - kg_podrido, Decimal('0'))

    ctx = {
        'viaje': viaje,
        'pesadas': pesadas,
        'pesada_form': pesada_form,
        'clases_data': clases_data,
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
    return render(request, 'core/viaje_detail.html', ctx)

@login_required
def pesada_add(request, pk):
    """Agrega una pesada (remesa de canastillas) al viaje."""
    viaje = get_object_or_404(Viaje, pk=pk)
    if request.method == 'POST':
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
    return render(request, 'core/confirm_delete.html', {'obj': viaje, 'tipo': 'Viaje', 'cancel_url': 'viaje_list'})

@login_required
def viaje_detalles_edit(request, pk):
    """Editar detalles adicionales del viaje (rechazos, canastillas, precio)"""
    viaje = get_object_or_404(Viaje, pk=pk)
    form = ViajeDetallesForm(request.POST or None, instance=viaje)
    if form.is_valid():
        form.save()
        messages.success(request, 'Detalles del viaje actualizados correctamente.')
        return redirect('viaje_detail', pk=pk)
    return render(request, 'core/form_generic.html', {
        'form': form, 
        'titulo': f'Editar Detalles - {viaje}', 
        'back_url': 'viaje_detail',
        'back_url_args': [pk]
    })

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
    gastos = Gasto.objects.filter(fecha=fecha).select_related('categoria')
    total = sum(g.monto for g in gastos)
    num_gastos = len(gastos)
    gasto_promedio = (total / num_gastos) if num_gastos > 0 else 0
    gasto_maximo = max((g.monto for g in gastos), default=0)

    form = GastoForm(request.POST or None, initial={'fecha': fecha})
    if form.is_valid():
        form.save()
        messages.success(request, 'Gasto registrado.')
        return redirect(f'/gastos/?fecha={fecha}')
    return render(request, 'core/gasto_list.html', {
        'gastos': gastos, 'total': total, 'form': form, 'fecha': fecha,
        'num_gastos': num_gastos, 'gasto_promedio': gasto_promedio, 'gasto_maximo': gasto_maximo
    })

@login_required
def gasto_edit(request, pk):
    obj = get_object_or_404(Gasto, pk=pk)
    form = GastoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Gasto actualizado.')
        return redirect('gasto_list')
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': 'Editar Gasto', 'back_url': 'gasto_list'})

@login_required
def gasto_delete(request, pk):
    obj = get_object_or_404(Gasto, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Gasto eliminado.')
        return redirect('gasto_list')
    return render(request, 'core/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Gasto', 'back_url': 'gasto_list'})

# ---- VENTAS EFECTIVO ----
@login_required
def venta_efectivo_list(request):
    fecha = request.GET.get('fecha', str(date.today()))
    ventas = VentaEfectivo.objects.filter(fecha=fecha).select_related('producto', 'cliente', 'clasificacion')
    total = sum(v.monto for v in ventas)
    total_kg = sum(v.kg_vendido for v in ventas)
    precio_promedio = (total / total_kg) if total_kg > 0 else 0
    num_ventas = len(ventas)

    form = VentaEfectivoForm(request.POST or None, initial={'fecha': fecha})
    if form.is_valid():
        venta = form.save(commit=False)
        venta.monto = venta.kg_vendido * venta.precio_por_kg
        # Validar que hay stock disponible
        if venta.clasificacion and venta.kg_vendido > venta.clasificacion.stock_kg:
            messages.error(request, f'No hay suficiente stock. Disponible: {venta.clasificacion.stock_kg} kg')
            return render(request, 'core/form_generic.html', {'form': form, 'titulo': 'Nueva Venta en Efectivo', 'back_url': 'venta_efectivo_list'})
        venta.save()
        messages.success(request, 'Venta en efectivo registrada.')
        return redirect(f'/ventas/efectivo/?fecha={fecha}')
    
    ctx = {
        'ventas': ventas, 'total': total, 'total_kg': total_kg,
        'precio_promedio': precio_promedio, 'num_ventas': num_ventas,
        'form': form, 'fecha': fecha
    }
    return render(request, 'core/venta_efectivo_list.html', ctx)

@login_required
def venta_efectivo_delete(request, pk):
    obj = get_object_or_404(VentaEfectivo, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Venta eliminada.')
        return redirect('venta_efectivo_list')
    return render(request, 'core/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Venta Efectivo', 'back_url': 'venta_efectivo_list'})

# ---- VENTAS CREDITO ----
@login_required
def venta_credito_list(request):
    ventas = VentaCredito.objects.select_related('cliente', 'producto').all()
    num_ventas = len(ventas)
    total_credito = sum(v.total for v in ventas)
    total_pagado = sum(v.total_pagado for v in ventas)
    total_pendiente = sum(v.saldo_pendiente for v in ventas)
    ctx = {
        'ventas': ventas,
        'num_ventas': num_ventas,
        'total_credito': total_credito,
        'total_pagado': total_pagado,
        'total_pendiente': total_pendiente
    }
    return render(request, 'core/venta_credito_list.html', ctx)

@login_required
def venta_credito_create(request):
    form = VentaCreditoForm(request.POST or None)
    if form.is_valid():
        clasificacion = form.cleaned_data['clasificacion']
        kg_vendido = form.cleaned_data['kg_vendido']
        
        # Validar stock disponible
        if kg_vendido > clasificacion.stock_kg:
            messages.error(request, f'No hay suficiente stock. Disponible: {clasificacion.stock_kg} kg')
            return render(request, 'core/venta_credito_form.html', {'form': form})
        
        venta = form.save()
        DetalleVentaCredito.objects.create(
            venta=venta,
            clasificacion=clasificacion,
            kg_vendido=kg_vendido,
            precio_por_kg=form.cleaned_data['precio_por_kg']
        )
        
        # Procesar abono inicial si aplica
        if request.POST.get('aplicar_abono_inicial') == 'on':
            monto_abono = request.POST.get('monto_abono_inicial')
            medio_pago = request.POST.get('medio_pago_abono', 'efectivo')
            if monto_abono and float(monto_abono) > 0:
                PagoVentaCredito.objects.create(
                    venta=venta,
                    monto=monto_abono,
                    fecha=venta.fecha,  # Se usa la misma fecha de la venta para el abono
                    medio_pago=medio_pago
                )
                messages.success(request, f'Venta a crédito creada con un abono inicial de ${monto_abono}.')
            else:
                messages.success(request, 'Venta a crédito creada (Abono ignorado por monto invalido).')
        else:
            messages.success(request, 'Venta a crédito creada exitosamente.')
            
        return redirect('venta_credito_detail', pk=venta.pk)
    return render(request, 'core/venta_credito_form.html', {'form': form})

@login_required
def venta_credito_detail(request, pk):
    venta = get_object_or_404(VentaCredito, pk=pk)
    detalles = venta.detalles.select_related('clasificacion').all()
    pagos = venta.pagos.all()
    detalle_form = DetalleVentaCreditoForm(request.POST or None)
    pago_form = PagoVentaCreditoForm()
    if 'detalle_submit' in request.POST and detalle_form.is_valid():
        detalle = detalle_form.save(commit=False)
        detalle.venta = venta
        detalle.save()
        messages.success(request, 'Producto agregado a la venta.')
        return redirect('venta_credito_detail', pk=pk)
    ctx = {
        'venta': venta, 'detalles': detalles, 'pagos': pagos,
        'detalle_form': detalle_form, 'pago_form': pago_form,
    }
    return render(request, 'core/venta_credito_detail.html', ctx)

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
    
    return render(request, 'core/confirm_delete.html', {'obj': obj, 'titulo': 'Eliminar Venta a Crédito', 'back_url': 'venta_credito_list'})

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

# ---- INVENTARIO ----
@login_required
def inventario_list(request):
    liquidaciones = LiquidacionInventario.objects.all()
    num_liquidaciones = len(liquidaciones)
    total_valor = sum(l.total_valor() if callable(l.total_valor) else getattr(l, 'total_valor', 0) for l in liquidaciones) if liquidaciones else 0
    valor_promedio = (total_valor / num_liquidaciones) if num_liquidaciones > 0 else 0
    return render(request, 'core/inventario_list.html', {
        'liquidaciones': liquidaciones, 'num_liquidaciones': num_liquidaciones,
        'total_valor': total_valor, 'valor_promedio': valor_promedio
    })

@login_required
def inventario_create(request):
    form = LiquidacionInventarioForm(request.POST or None)
    if form.is_valid():
        liq = form.save()
        fecha_ini = liq.fecha_inicio
        fecha_fin = liq.fecha_fin
        # Calcular inventario automáticamente
        clasificaciones = Clasificacion.objects.filter(activo=True).select_related('producto')
        for clas in clasificaciones:
            kg_ingresado = sum(
                l.kg_neto for l in LoteClasificacion.objects.filter(
                    clasificacion=clas, viaje__fecha__range=[fecha_ini, fecha_fin]))
            kg_vendido_credito = sum(
                d.kg_vendido for d in DetalleVentaCredito.objects.filter(
                    clasificacion=clas, venta__fecha__range=[fecha_ini, fecha_fin]))
            kg_vendido_efectivo = sum(
                v.kg_vendido for v in VentaEfectivo.objects.filter(
                    clasificacion=clas, fecha__range=[fecha_ini, fecha_fin]))
            kg_vendido = kg_vendido_credito + kg_vendido_efectivo
            kg_restante = kg_ingresado - kg_vendido
            # Precio: último precio del lote en ese periodo
            ultimo_lote = LoteClasificacion.objects.filter(
                clasificacion=clas, viaje__fecha__range=[fecha_ini, fecha_fin]
            ).order_by('-viaje__fecha').first()
            precio = ultimo_lote.precio_por_kg if ultimo_lote else 0
            if kg_ingresado > 0 or kg_vendido > 0:
                DetalleInventario.objects.create(
                    liquidacion=liq,
                    clasificacion=clas,
                    kg_ingresado=kg_ingresado,
                    kg_vendido=kg_vendido,
                    kg_restante=max(kg_restante, 0),
                    precio_por_kg=precio,
                )
        messages.success(request, 'Liquidación de inventario generada.')
        return redirect('inventario_detail', pk=liq.pk)
    return render(request, 'core/form_generic.html', {'form': form, 'titulo': 'Nueva Liquidación de Inventario', 'back_url': 'inventario_list'})

@login_required
def inventario_detail(request, pk):
    liq = get_object_or_404(LiquidacionInventario, pk=pk)
    detalles = liq.detalles.select_related('clasificacion__producto').all()
    return render(request, 'core/inventario_detail.html', {'liq': liq, 'detalles': detalles})

@login_required
def inventario_delete(request, pk):
    liq = get_object_or_404(LiquidacionInventario, pk=pk)
    if request.method == 'POST':
        liq.delete()
        messages.success(request, 'Liquidación de Inventario eliminada satisfactoriamente.')
        return redirect('inventario_list')
    return render(request, 'core/confirm_delete.html', {'obj': liq, 'tipo': 'Liquidación de Inventario', 'cancel_url': 'inventario_list'})

@login_required
def detalle_inventario_edit(request, pk):
    detalle = get_object_or_404(DetalleInventario, pk=pk)
    liq_id = detalle.liquidacion.pk
    
    if request.method == 'POST':
        # Si la diferencia de kg_restante es positiva, suma al stock. Si es negativa, resta.
        diff_kg = detalle.kg_restante - Decimal(request.POST.get('kg_restante', '0'))
        detalle.kg_restante = Decimal(request.POST.get('kg_restante', '0'))
        detalle.kg_ingresado = Decimal(request.POST.get('kg_ingresado', '0'))
        detalle.kg_vendido = Decimal(request.POST.get('kg_vendido', '0'))
        detalle.precio_por_kg = Decimal(request.POST.get('precio_por_kg', '0')) if request.POST.get('precio_por_kg') else Decimal('0')
        detalle.save()
        
        # Actualizar stock de la clasificación
        if diff_kg != 0 and detalle.clasificacion:
            detalle.clasificacion.stock_kg = F('stock_kg') - diff_kg
            detalle.clasificacion.save(update_fields=['stock_kg'])
        
        messages.success(request, 'Detalle de inventario actualizado.')
        return redirect('inventario_detail', pk=liq_id)
    
    ctx = {
        'detalle': detalle,
        'liq': detalle.liquidacion,
    }
    return render(request, 'core/detalle_inventario_form.html', ctx)

@login_required
def detalle_inventario_delete(request, pk):
    detalle = get_object_or_404(DetalleInventario, pk=pk)
    liq_id = detalle.liquidacion.pk
    
    if request.method == 'POST':
        # Devolver los kg al stock de la clasificación
        if detalle.clasificacion:
            detalle.clasificacion.stock_kg = F('stock_kg') + detalle.kg_restante
            detalle.clasificacion.save(update_fields=['stock_kg'])
        
        detalle.delete()
        messages.success(request, 'Detalle de inventario eliminado.')
        return redirect('inventario_detail', pk=liq_id)
    
    ctx = {
        'obj': detalle,
        'titulo': 'Eliminar Detalle de Inventario',
        'back_url': 'inventario_detail',
        'back_url_id': liq_id,
    }
    return render(request, 'core/confirm_delete.html', ctx)

# ---- REPORTES ----
@login_required
def reporte_diario(request):
    fecha = request.GET.get('fecha', str(date.today()))
    ventas_ef = VentaEfectivo.objects.filter(fecha=fecha)
    ventas_cr = VentaCredito.objects.filter(fecha=fecha)
    gastos = Gasto.objects.filter(fecha=fecha).select_related('categoria')
    total_efectivo = sum(v.monto for v in ventas_ef)
    total_credito = sum(v.total for v in ventas_cr)
    total_gastos = sum(g.monto for g in gastos)
    balance = total_efectivo + total_credito - total_gastos
    ctx = {
        'fecha': fecha, 'ventas_ef': ventas_ef, 'ventas_cr': ventas_cr,
        'gastos': gastos, 'total_efectivo': total_efectivo,
        'total_credito': total_credito, 'total_gastos': total_gastos, 'balance': balance,
    }
    return render(request, 'core/reporte_diario.html', ctx)

@login_required
def reporte_cartera(request):
    ventas = VentaCredito.objects.select_related('cliente', 'producto').all()
    pendientes = [v for v in ventas if v.saldo_pendiente > 0]
    total_cartera = sum(v.saldo_pendiente for v in pendientes)
    return render(request, 'core/reporte_cartera.html', {'pendientes': pendientes, 'total_cartera': total_cartera})

@login_required
def reporte_proveedor(request):
    viajes = Viaje.objects.select_related('proveedor', 'producto').all()
    pendientes = [v for v in viajes if v.saldo_pendiente > 0]
    total_deuda = sum(v.saldo_pendiente for v in pendientes)
    return render(request, 'core/reporte_proveedor.html', {'viajes': viajes, 'pendientes': pendientes, 'total_deuda': total_deuda})
