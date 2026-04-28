from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Q, F, Count
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from .models import *
from .forms import *

# ---- FUNCIONES AUXILIARES DE INVENTARIO SEMANAL ----

def get_week_monday(fecha):
    """Retorna el lunes de la semana de la fecha dada"""
    return fecha - timedelta(days=fecha.weekday())

def get_or_create_weekly_inventory(fecha):
    """Obtiene o crea el registro de inventario para la semana de la fecha dada"""
    lunes = get_week_monday(fecha)
    weekly, created = WeeklyInventory.objects.get_or_create(
        week_start=lunes,
        defaults={'initial_inventory_kg': Decimal('0')}
    )
    return weekly, created

def get_current_week_inventory_data():
    """Obtiene los datos de inventario inicial y total para la semana actual
    
    Lógica de reset de lunes:
    - Cada lunes, el inventario inicial = total de inventario del domingo anterior
    - El total de inventario = inicial + compras de esta semana
    
    Primera vez:
    - Si no existe semana anterior, usa el stock actual como inicial
    """
    hoy = date.today()
    lunes = get_week_monday(hoy)
    domingo = lunes + timedelta(days=6)
    
    # Obtener o crear registro de inventario para esta semana
    weekly, created = get_or_create_weekly_inventory(hoy)
    
    # Si el inventario inicial está vacío (0) y es la primera vez que se accede
    # o si es lunes, copiar del total de la semana anterior
    if created or (weekly.initial_inventory_kg == 0 and hoy == lunes):
        # Obtener la semana anterior
        prev_lunes = lunes - timedelta(days=7)
        try:
            prev_weekly = WeeklyInventory.objects.get(week_start=prev_lunes)
            # El inventario inicial de esta semana = total de la semana anterior (domingo 11:59 PM)
            weekly.initial_inventory_kg = prev_weekly.total_inventory_kg
            weekly.save()
        except WeeklyInventory.DoesNotExist:
            # Si no hay semana anterior, intentar usar el stock actual como inicial
            # Esto solo ocurre la primera vez que se usa el sistema
            if weekly.initial_inventory_kg == 0:
                # Obtener todas las clasificaciones activas y sumar su stock
                from .models import Clasificacion
                all_clasificaciones = Clasificacion.objects.filter(activo=True)
                current_stock = sum(c.stock_kg for c in all_clasificaciones) or Decimal('0')
                if current_stock > 0:
                    weekly.initial_inventory_kg = current_stock
                    weekly.save()
    
    initial_kg = weekly.initial_inventory_kg
    total_kg = weekly.total_inventory_kg
    
    return {
        'week_monday': lunes,
        'week_sunday': domingo,
        'initial_inventory_kg': initial_kg,
        'total_inventory_kg': total_kg,
        'weekly_record': weekly
    }

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
    ventas_por_cobrar = [v for v in VentaCredito.objects.all().order_by('-fecha') if v.saldo_pendiente > 0]
    total_por_cobrar = sum(v.saldo_pendiente for v in ventas_por_cobrar)
    
    viajes_recientes = Viaje.objects.all().order_by('-id')[:5]
    ventas_pendientes_top = ventas_por_cobrar[:5]
    
    # 10 Últimas ventas del día (mezclando efectivo y crédito)
    ultimas_ventas = []
    for ve in ventas_efectivo_hoy:
        # Solo incluir si tiene detalles
        if ve.detalles.exists():
            productos = ', '.join([d.clasificacion.producto.nombre for d in ve.detalles.all()])
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
    
    # ---- MÉTRICAS DE INVENTARIO DE MANDARINA ----
    # Obtener el producto "Mandarina" o el primero disponible
    producto_mandarina = Producto.objects.filter(nombre__icontains='Mandarina').first() or Producto.objects.first()
    
    # 1. INVENTARIO INICIAL: Stock total de mandarina al inicio del día
    clasificaciones_mandarina = Clasificacion.objects.filter(producto=producto_mandarina) if producto_mandarina else Clasificacion.objects.none()
    inventario_inicial_kg = sum(c.stock_kg for c in clasificaciones_mandarina)
    inventario_inicial_toneladas = inventario_inicial_kg / 1000 if inventario_inicial_kg > 0 else Decimal('0')
    
    # Detalles de clasificaciones para modal
    detalles_inventario_inicial = []
    for clasificacion in clasificaciones_mandarina:
        detalles_inventario_inicial.append({
            'nombre': clasificacion.nombre,
            'stock_kg': clasificacion.stock_kg,
            'stock_toneladas': clasificacion.stock_kg / 1000
        })
    
    # 2. COMPRAS DEL DÍA: Suma de kg_neto de lotes clasificados de viajes de hoy
    lotes_hoy = LoteClasificacion.objects.filter(
        viaje__fecha=hoy,
        viaje__producto=producto_mandarina
    ) if producto_mandarina else LoteClasificacion.objects.none()
    compras_hoy_kg = sum(lote.kg_neto for lote in lotes_hoy)
    compras_hoy_toneladas = compras_hoy_kg / 1000 if compras_hoy_kg > 0 else Decimal('0')
    
    # Detalles de compras para modal
    detalles_compras = []
    lotes_hoy_list = list(lotes_hoy)
    for lote in lotes_hoy_list:
        detalles_compras.append({
            'proveedor': lote.viaje.proveedor.nombre if lote.viaje.proveedor else 'N/A',
            'clasificacion': lote.clasificacion.nombre,
            'kg_neto': lote.kg_neto,
            'fecha': lote.viaje.fecha
        })
    
    # 3. VENDIDO: Suma de kg_vendido de todas las ventas de hoy
    # 3a. Ventas en efectivo del día
    detalles_efectivo_mandarina = [d for v in ventas_efectivo_hoy for d in v.detalles.all() if d.clasificacion.producto == producto_mandarina] if producto_mandarina else []
    kg_vendido_efectivo = sum(d.kg_vendido for d in detalles_efectivo_mandarina)
    
    # 3b. Ventas a crédito del día - filtrar por clasificación.producto, no por venta.producto
    detalles_credito_todos = DetalleVentaCredito.objects.filter(venta__fecha=hoy)
    detalles_credito_hoy = [d for d in detalles_credito_todos if d.clasificacion.producto == producto_mandarina] if producto_mandarina else []
    kg_vendido_credito = sum(d.kg_vendido for d in detalles_credito_hoy)
    
    # Total vendido en kg y toneladas
    total_kg_vendido = kg_vendido_efectivo + kg_vendido_credito
    vendido_toneladas = total_kg_vendido / 1000 if total_kg_vendido > 0 else Decimal('0')
    
    # Detalles de ventas para modal
    detalles_ventas = []
    for detalle in detalles_efectivo_mandarina:
        detalles_ventas.append({
            'tipo': 'Efectivo',
            'cliente': detalle.venta.cliente.nombre if detalle.venta.cliente else 'General',
            'clasificacion': detalle.clasificacion.nombre if detalle.clasificacion else 'N/A',
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
    
    # 4. DESECHOS: Suma de kg_podridos de viajes de hoy
    viajes_hoy = Viaje.objects.filter(fecha=hoy, producto=producto_mandarina) if producto_mandarina else Viaje.objects.none()
    desechos_kg = sum(v.kg_podridos for v in viajes_hoy)
    desechos_toneladas = desechos_kg / 1000 if desechos_kg > 0 else Decimal('0')
    
    # Detalles de desechos para modal
    detalles_desechos = []
    viajes_hoy_list = list(viajes_hoy)
    for viaje in viajes_hoy_list:
        if viaje.kg_podridos > 0:
            detalles_desechos.append({
                'proveedor': viaje.proveedor.nombre if viaje.proveedor else 'N/A',
                'kg_podridos': viaje.kg_podridos,
                'fecha': viaje.fecha,
                'observaciones': viaje.observaciones
            })
    
    pago_form = PagoVentaCreditoForm()
    
    # Obtener datos de inventario semanal
    weekly_inv = get_current_week_inventory_data()
    
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

        messages.success(request, 'Clasificaciones guardadas exitosamente.')
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
                    data = {
                        'num_canastillas_negras': request.POST.get(f'num_canastillas_negras_{i}', '') or None,
                        'num_canastillas_colores': request.POST.get(f'num_canastillas_colores_{i}', '') or None,
                        'kg_bruto': kg_bruto_val,
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
def venta_efectivo_create(request):
    if request.method == 'POST':
        form = VentaEfectivoForm(request.POST)
        if form.is_valid():
            venta = form.save()
            messages.success(request, 'Venta en efectivo creada. Ahora agrega los productos vendidos.')
            return redirect('venta_efectivo_detail', pk=venta.pk)
    else:
        form = VentaEfectivoForm(initial={'fecha': date.today()})
    return render(request, 'core/form_generic.html', {
        'form': form,
        'titulo': 'Nueva Venta en Efectivo',
        'back_url': 'venta_efectivo_list'
    })

@login_required
def venta_efectivo_detail(request, pk):
    venta = get_object_or_404(VentaEfectivo, pk=pk)
    detalles = venta.detalles.all()
    detalle_form = DetalleVentaEfectivoForm(request.POST or None)
    
    if request.method == 'POST' and 'finalizar_venta' in request.POST:
        # Validar que tenga al menos un detalle
        if not detalles.exists():
            messages.error(request, '❌ Debe agregar al menos un producto antes de registrar la venta.')
            return redirect('venta_efectivo_detail', pk=venta.pk)
        
        # Obtener datos del pago del formulario
        medio_pago = request.POST.get('medio_pago', 'efectivo')
        monto_pagado_str = request.POST.get('monto_pagado', '')
        
        # Validar y convertir monto pagado
        monto_pagado = None
        if monto_pagado_str:
            # Reemplazar coma por punto si es necesario
            monto_pagado_str = str(monto_pagado_str).replace(',', '.')
            try:
                monto_pagado = float(monto_pagado_str)
            except (ValueError, TypeError):
                monto_pagado = None
        
        if not monto_pagado or monto_pagado <= 0:
            messages.error(request, '❌ Ingrese un monto pagado válido (debe ser mayor a 0).')
            return redirect('venta_efectivo_detail', pk=venta.pk)
        
        total_venta = float(venta.total)
        
        # Mensaje dependiendo del pago
        if monto_pagado >= total_venta:
            cambio = monto_pagado - total_venta
            messages.success(
                request, 
                f'✅ ¡Venta registrada exitosamente! | Medio: {medio_pago.upper()} | Total: ${total_venta:.0f} | Cambio: ${cambio:.0f}'
            )
        else:
            falta = total_venta - monto_pagado
            messages.warning(
                request, 
                f'⚠️ Venta registrada con pago incompleto. Falta: ${falta:.0f}'
            )
        
        return redirect('venta_efectivo_list')
    
    if request.method == 'POST' and 'detalle_submit' in request.POST:
        if detalle_form.is_valid():
            detalle = detalle_form.save(commit=False)
            detalle.venta = venta
            
            # Validar stock
            if detalle.kg_vendido > detalle.clasificacion.stock_kg:
                messages.error(request, f'No hay suficiente stock. Disponible: {detalle.clasificacion.stock_kg} kg')
            else:
                detalle.save()
                messages.success(request, f'Producto agregado: {detalle.clasificacion} - {detalle.kg_vendido} kg')
                return redirect('venta_efectivo_detail', pk=venta.pk)
    
    ctx = {
        'venta': venta,
        'detalles': detalles,
        'detalle_form': detalle_form
    }
    return render(request, 'core/venta_efectivo_detail.html', ctx)

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
    # Filtrar solo ventas que tengan detalles (no vacías)
    ventas = VentaEfectivo.objects.filter(fecha=fecha).prefetch_related('detalles').annotate(num_detalles=models.Count('detalles')).filter(num_detalles__gt=0)
    total = sum(v.total for v in ventas)
    total_kg = sum(sum(d.kg_vendido for d in v.detalles.all()) for v in ventas)
    precio_promedio = (total / total_kg) if total_kg > 0 else 0
    num_ventas = len(ventas)
    
    ctx = {
        'ventas': ventas,
        'total': total,
        'total_kg': total_kg,
        'precio_promedio': precio_promedio,
        'num_ventas': num_ventas,
        'fecha': fecha
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
    """Crea una nueva venta a crédito (sin detalles, se agregan después)"""
    if request.method == 'POST':
        form = VentaCreditoForm(request.POST)
        if form.is_valid():
            venta = form.save()
            messages.success(request, 'Venta a crédito creada. Ahora agrega los productos vendidos.')
            return redirect('venta_credito_detail', pk=venta.pk)
    else:
        form = VentaCreditoForm(initial={'fecha': date.today()})
    return render(request, 'core/form_generic.html', {
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
                }
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

# ---- REPORTES ----
@login_required
def reporte_diario(request):
    fecha = request.GET.get('fecha', str(date.today()))
    ventas_ef = VentaEfectivo.objects.filter(fecha=fecha)
    ventas_cr = VentaCredito.objects.filter(fecha=fecha)
    gastos = Gasto.objects.filter(fecha=fecha).select_related('categoria')
    total_efectivo = sum(v.total for v in ventas_ef)
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

# ---- RESUMEN SEMANAL ----
@login_required
def inventario_weekly_summary(request):
    """Vista para mostrar resumen de métricas operacionales por semana"""
    hoy = date.today()
    
    # Calcular rango de semana (lunes a domingo)
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes
    fin_semana = inicio_semana + timedelta(days=6)       # Domingo
    
    # 1. GASTOS DE LA SEMANA
    gastos_semana = Gasto.objects.filter(fecha__range=[inicio_semana, fin_semana])
    total_gastos_semana = sum(g.monto for g in gastos_semana) or Decimal('0')
    
    # 2. VENTAS EN EFECTIVO DE LA SEMANA
    ventas_efectivo_semana = VentaEfectivo.objects.filter(fecha__range=[inicio_semana, fin_semana])
    total_efectivo_semana = sum(v.total for v in ventas_efectivo_semana) or Decimal('0')
    promedio_efectivo = total_efectivo_semana / len(ventas_efectivo_semana) if ventas_efectivo_semana else Decimal('0')
    
    # 3. VENTAS A CRÉDITO DE LA SEMANA
    ventas_credito_semana = VentaCredito.objects.filter(fecha__range=[inicio_semana, fin_semana])
    total_credito_semana = sum(v.total for v in ventas_credito_semana) or Decimal('0')
    promedio_credito = total_credito_semana / len(ventas_credito_semana) if ventas_credito_semana else Decimal('0')
    
    # 4. TOTAL VENTAS
    total_ventas_semana = total_efectivo_semana + total_credito_semana
    
    # 5. DESECHOS/PODRIDO DE LA SEMANA
    viajes_semana = Viaje.objects.filter(fecha__range=[inicio_semana, fin_semana])
    total_kg_podridos = sum(v.kg_podridos for v in viajes_semana) or Decimal('0')
    
    # 6. BALANCE NETO
    balance_neto = total_ventas_semana - total_gastos_semana
    
    # 7. DETECTAR SI HAY NÓMINA EN LA SEMANA (días 10, 20, 30)
    dias_nomina = [10, 20, 30]
    tiene_nomina_hoy = hoy.day in dias_nomina
    hay_nomina_en_semana = any(
        (inicio_semana + timedelta(days=i)).day in dias_nomina 
        for i in range(7)
    )
    
    # Si hay nómina en la semana, calcular monto estimado (puede ajustarse según lógica del negocio)
    # Por ahora, mostrar un placeholder o calcular desde otra fuente
    monto_nomina = Decimal('0')  # Placeholder - ajustar según lógica del negocio
    
    # 8. INVENTARIO SEMANAL
    weekly_inv = get_current_week_inventory_data()
    initial_inventory_kg = weekly_inv['initial_inventory_kg']
    total_inventory_kg = weekly_inv['total_inventory_kg']
    
    ctx = {
        'hoy': hoy,
        'inicio_semana': inicio_semana,
        'fin_semana': fin_semana,
        'total_gastos_semana': total_gastos_semana,
        'total_efectivo_semana': total_efectivo_semana,
        'total_credito_semana': total_credito_semana,
        'total_ventas_semana': total_ventas_semana,
        'balance_neto': balance_neto,
        'total_kg_podridos': total_kg_podridos,
        'tiene_nomina_hoy': tiene_nomina_hoy,
        'hay_nomina_en_semana': hay_nomina_en_semana,
        'monto_nomina': monto_nomina,
        'num_gastos': gastos_semana.count(),
        'num_ventas_efectivo': ventas_efectivo_semana.count(),
        'num_ventas_credito': ventas_credito_semana.count(),
        'promedio_efectivo': promedio_efectivo,
        'promedio_credito': promedio_credito,
        # Inventario Semanal
        'initial_inventory_kg': initial_inventory_kg,
        'total_inventory_kg': total_inventory_kg,
    }
    
    return render(request, 'core/inventario_weekly_summary.html', ctx)
