from ._common import *

__all__ = ['proveedor_list', 'proveedor_create', 'proveedor_edit', 'proveedor_delete', 'cliente_list', 'cliente_create', 'cliente_edit', 'cliente_delete', 'producto_list', 'producto_create', 'producto_edit', 'producto_delete', 'producto_clasificaciones', 'producto_stock_update', 'clasificacion_edit', 'categoria_gasto_list', 'categoria_gasto_edit', 'categoria_gasto_delete']


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


@login_required
def cliente_list(request):
    from django.core.paginator import Paginator

    q = request.GET.get('q', '')
    clientes_qs = Cliente.objects.filter(nombre__icontains=q) if q else Cliente.objects.all()

    paginator = Paginator(clientes_qs, 10)
    clientes = paginator.get_page(request.GET.get('page'))

    num_clientes = paginator.count
    num_activos = clientes_qs.filter(activo=True).count()
    num_inactivos = clientes_qs.filter(activo=False).count()
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
