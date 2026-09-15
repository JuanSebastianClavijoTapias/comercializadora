from ._common import *

__all__ = ['inventario_weekly_summary', 'entrada_inventario_list', 'entrada_inventario_historial', 'entrada_inventario_create', 'entrada_inventario_detail', 'pesada_entrada_add', 'pesada_entrada_delete', 'entrada_inventario_edit', 'entrada_inventario_delete']


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
    kg_credito_semana = sum(sum(d.kg_vendido for d in v.detalles.all()) for v in ventas_credito_semana) or Decimal('0')
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

    # Historial completo de entradas (todas, sin filtrar por semana) —
    # lo que se registra en entrada_inventario_create se ve aquí directo.
    entradas_historial = EntradaInventario.objects.select_related(
        'proveedor', 'clasificacion__producto'
    ).prefetch_related('pesadas').order_by('-fecha', '-created_at')
    entradas_historial_kg = sum(e.kg for e in entradas_historial) or Decimal('0')
    entradas_historial_total = sum(e.total for e in entradas_historial) or Decimal('0')

    # Agrupación por proveedor
    from collections import defaultdict
    proveedores_data = defaultdict(lambda: {'kg': Decimal('0'), 'total': Decimal('0')})
    for e in compras_semana:
        pid = e.proveedor_id
        proveedores_data[pid]['kg'] += e.kg
        proveedores_data[pid]['total'] += e.total
    resumen_proveedores = []
    for pid, data in proveedores_data.items():
        # find the proveedor name
        prov = next((e.proveedor for e in compras_semana if e.proveedor_id == pid), None)
        if prov:
            resumen_proveedores.append({
                'proveedor': prov.nombre,
                'kg': data['kg'],
                'total': data['total'],
            })
    resumen_proveedores.sort(key=lambda x: x['kg'], reverse=True)

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
        'previousweek_has_data': week_has_data(inicio_semana - timedelta(days=7)),
        'next_week_start': next_week_start,
        'selected_week_is_current': inicio_semana == current_week_start,
        'total_gastos_semana': total_gastos_semana,
        'total_egresos_semana': total_gastos_semana + monto_nomina,
        'total_efectivo_semana': total_efectivo_semana,
        'total_credito_semana': total_credito_semana,
        'kg_credito_semana': kg_credito_semana,
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
        'entradas_historial': entradas_historial,
        'entradas_historial_kg': entradas_historial_kg,
        'entradas_historial_total': entradas_historial_total,
        'resumen_proveedores': resumen_proveedores,
        'ingresos_semana': ingresos_semana,
        'weekly_history': get_weekly_history(),
        'nomina_form': nomina_form,
        'stock_valorizado': stock_valorizado(),
    }

    return render(request, 'core/inventario/inventario_weekly_summary.html', ctx)


@login_required
def entrada_inventario_list(request):
    return inventario_weekly_summary(request)


@login_required
def entrada_inventario_historial(request):
    entradas = EntradaInventario.objects.select_related(
        'proveedor', 'clasificacion__producto'
    ).prefetch_related('pesadas').order_by('-fecha', '-created_at')
    total_kg = sum(e.kg for e in entradas) or Decimal('0')
    total_valor = sum(e.total for e in entradas) or Decimal('0')
    return render(request, 'core/inventario/entrada_inventario_list.html', {
        'entradas': entradas,
        'total_kg': total_kg,
        'total_valor': total_valor,
    })


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
                next_url = request.POST.get('next', '').strip()
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    return redirect(next_url)
                return redirect('entrada_inventario_create')
            return render(request, 'core/inventario/entrada_inventario_nueva.html', {
                'proveedores': proveedores, 'clasificaciones': clasificaciones,
                'fecha_default': date.today().isoformat(),
                'nomina_form': nomina_form, 'desecho_local_form': desecho_local_form,
            })

        # --- Entrada de inventario (default) ---
        form_errors = []
        fecha = request.POST.get('fecha', '').strip()

        if not fecha:
            form_errors.append('La fecha es requerida.')

        # Parse pesada rows
        rows = []
        i = 0
        while f'kg_bruto_{i}' in request.POST:
            kg_val = request.POST.get(f'kg_bruto_{i}', '').strip()
            if kg_val:
                cid = request.POST.get(f'clasificacion_{i}', '').strip()
                pid = request.POST.get(f'proveedor_{i}', '').strip()
                rows.append({
                    'clasificacion_id': cid,
                    'proveedor_id': pid,
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
        for r in rows:
            if not r['proveedor_id']:
                form_errors.append('Todas las filas deben tener un proveedor seleccionado.')
                break

        if not form_errors:
            from collections import defaultdict
            groups = defaultdict(list)
            for row in rows:
                groups[(row['clasificacion_id'], row['proveedor_id'])].append(row)

            # Read precio per classification from receipt inputs
            precios = {}
            for cid, _pid in groups.keys():
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
                    for (cid, pid), group_rows in groups.items():
                        entrada = EntradaInventario(
                            fecha=fecha,
                            proveedor_id=int(pid),
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

    # Agrupación por clasificación desde las pesadas
    from collections import defaultdict
    clasif_kg = defaultdict(Decimal)
    for p in pesadas:
        cid = p.clasificacion_id or p.entrada.clasificacion_id
        if cid:
            clasif_kg[cid] += p.kg_neto
    # Buscar objetos Clasificacion para los IDs encontrados
    clasif_ids = list(clasif_kg.keys())
    clasif_map = {c.pk: c for c in Clasificacion.objects.filter(pk__in=clasif_ids).select_related('producto')}
    resumen_clasificaciones = []
    for cid, kg in clasif_kg.items():
        cobj = clasif_map.get(cid)
        if cobj:
            resumen_clasificaciones.append({'clasificacion': cobj, 'kg': kg})

    return render(request, 'core/inventario/entrada_inventario_detail.html', {
        'entrada': entrada,
        'pesadas': pesadas,
        'precio_form': precio_form,
        'proveedores': Proveedor.objects.order_by('nombre'),
        'clasificaciones': Clasificacion.objects.filter(activo=True).select_related('producto').order_by('producto__nombre', 'nombre'),
        'kg_bruto_total': kg_bruto_total,
        'peso_total_canastillas': peso_total_canastillas,
        'kg_neto_total': kg_neto_total,
        'cant_neg': cant_neg,
        'cant_col': cant_col,
        'resumen_clasificaciones': resumen_clasificaciones,
    })


@login_required
def pesada_entrada_add(request, pk):
    entrada = get_object_or_404(EntradaInventario, pk=pk)
    if request.method == 'POST':
        if 'kg_bruto_0' in request.POST:
            from collections import defaultdict
            rows = []
            i = 0
            while f'kg_bruto_{i}' in request.POST:
                kg_bruto_val = request.POST.get(f'kg_bruto_{i}', '').strip()
                if kg_bruto_val:
                    clasif_id = request.POST.get(f'clasificacion_{i}', '').strip() or str(entrada.clasificacion_id)
                    prov_id = request.POST.get(f'proveedor_{i}', '').strip() or str(entrada.proveedor_id)
                    rows.append({
                        'clasificacion_id': clasif_id,
                        'proveedor_id': prov_id,
                        'num_canastillas_negras': request.POST.get(f'num_canastillas_negras_{i}', '') or 0,
                        'num_canastillas_colores': request.POST.get(f'num_canastillas_colores_{i}', '') or 0,
                        'kg_bruto': kg_bruto_val,
                    })
                i += 1

            groups = defaultdict(list)
            for row in rows:
                groups[(row['clasificacion_id'], row['proveedor_id'])].append(row)

            guardadas = 0
            nuevas_entradas = 0
            with transaction.atomic():
                for (cid, pid), group_rows in groups.items():
                    if cid == str(entrada.clasificacion_id) and pid == str(entrada.proveedor_id):
                        target = entrada
                    else:
                        target = EntradaInventario.objects.create(
                            fecha=entrada.fecha,
                            proveedor_id=int(pid),
                            clasificacion_id=int(cid),
                            precio_por_kg=Decimal('0'),
                        )
                        nuevas_entradas += 1
                    for row in group_rows:
                        data = {
                            'num_canastillas_negras': row['num_canastillas_negras'],
                            'num_canastillas_colores': row['num_canastillas_colores'],
                            'kg_bruto': row['kg_bruto'],
                            'clasificacion': cid,
                        }
                        form = PesadaEntradaForm(data)
                        if form.is_valid():
                            p = form.save(commit=False)
                            p.entrada = target
                            p.save()
                            guardadas += 1

            if guardadas:
                msg = f'{guardadas} pesada{"s" if guardadas != 1 else ""} registrada{"s" if guardadas != 1 else ""}.'
                if nuevas_entradas:
                    msg += f' Se crearon {nuevas_entradas} entrada{"s" if nuevas_entradas != 1 else ""} nueva{"s" if nuevas_entradas != 1 else ""} para el/los proveedor(es) distinto(s).'
                messages.success(request, msg)
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
