from ._common import *

__all__ = ['gasto_list', 'gasto_edit', 'gasto_delete', 'gasto_detail', 'weekly_inventory_edit', 'weekly_inventory_delete', 'nomina_edit', 'nomina_delete']


@login_required
def gasto_list(request):
    fecha = parse_fecha(request.GET.get('fecha') or request.POST.get('fecha'), date.today())

    formset = GastoFormSet(request.POST or None, prefix='gastos')
    if request.method == 'POST':
        if formset.is_valid():
            creados = registrar_gastos(formset, fecha)
            if creados:
                plural = 's' if creados != 1 else ''
                messages.success(request, f'{creados} gasto{plural} registrado{plural}.')
                return redirect(f"{reverse('gasto_list')}?fecha={fecha.isoformat()}")
            messages.warning(request, 'Agrega al menos una descripción y un monto.')
        else:
            messages.error(request, 'Revisa los datos del formulario.')

    return render(request, 'core/gastos/gasto_list.html', {
        'resumen': resumen_gastos_del_dia(fecha),
        'formset': formset,
        'fecha': fecha.isoformat(),
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
