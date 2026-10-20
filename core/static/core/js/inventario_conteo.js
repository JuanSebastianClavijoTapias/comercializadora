// Conteo semanal de inventario: captura agrupada por proveedor,
// producto+calidad y pesadas. Cada pesada descuenta las canastillas
// (negras 1.6 kg, color 2.2 kg) para obtener el kg neto.
//
// El formulario se arma en JS a partir de los datos serializados en la
// plantilla (json_script). Los proveedor_N / clasificacion_N de cada fila se
// sincronizan desde los selects de su grupo (van como inputs ocultos).
(function () {
  'use strict';

  const PESO_NEGRA = 1.6;
  const PESO_COLOR = 2.2;

  function readData(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : [];
  }

  const PROVEEDORES = readData('proveedores-data');
  const PRODUCTOS = readData('productos-data');
  const CLASIFICACIONES = readData('clasificaciones-data');
  const INITIAL_ROWS = readData('initial-rows');

  const container = document.getElementById('proveedores_container');
  const resumenEl = document.getElementById('resumen_conteo');
  const form = document.getElementById('form_conteo');
  if (!container) return;

  let seq = 0;

  // ---------- helpers ----------
  function makeOption(value, label, selected) {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = label;
    if (selected) opt.selected = true;
    return opt;
  }

  function fillSelect(select, items, placeholder) {
    select.innerHTML = '';
    select.appendChild(makeOption('', placeholder, true));
    items.forEach(function (it) {
      select.appendChild(makeOption(it.value, it.label, false));
    });
  }

  function clasificacionesDe(productoId) {
    return CLASIFICACIONES
      .filter(function (c) { return String(c.producto_id) === String(productoId); })
      .map(function (c) { return { value: c.id, label: c.calidad }; });
  }

  function fmtCOP(n) {
    return '$' + Math.round(n).toLocaleString('es-CO');
  }

  function calcPesada(row) {
    const bruto = parseFloat(row.querySelector('.input-bruto').value) || 0;
    const neg = parseFloat(row.querySelector('.input-neg').value) || 0;
    const col = parseFloat(row.querySelector('.input-col').value) || 0;
    const precioInput = row.querySelector('.input-precio');
    const precio = precioInput ? (parseFloat(precioInput.value) || 0) : 0;
    const neto = Math.max(bruto - (neg * PESO_NEGRA + col * PESO_COLOR), 0);
    const valor = neto * precio;

    const netoEl = row.querySelector('.kg-neto');
    if (netoEl) netoEl.textContent = bruto > 0 ? neto.toFixed(2) + ' kg' : '-';

    const valorEl = row.querySelector('.valor-pesada');
    if (valorEl) valorEl.textContent = valor > 0 ? fmtCOP(valor) : '-';

    return { bruto: bruto, neto: neto, valor: valor };
  }

  // ---------- sincronización de la fila con su grupo ----------
  function syncCalidad(calBlock) {
    const provSel = calBlock.closest('.proveedor-block').querySelector('.prov-select');
    const calSel = calBlock.querySelector('.cal-select');
    calBlock.querySelectorAll('.pesada-row').forEach(function (row) {
      row.querySelector('input[name^="proveedor_"]').value = provSel.value;
      row.querySelector('input[name^="clasificacion_"]').value = calSel.value;
    });
  }

  function syncProveedor(provBlock) {
    provBlock.querySelectorAll('.calidad-block').forEach(syncCalidad);
  }

  function syncAll() {
    container.querySelectorAll('.calidad-block').forEach(syncCalidad);
  }

  // ---------- recálculo y resumen ----------
  function recalcAll() {
    const porCalidad = {};
    const porProveedor = {};
    let total = 0;
    let totalValor = 0;

    container.querySelectorAll('.calidad-block').forEach(function (calBlock) {
      const provSel = calBlock.closest('.proveedor-block').querySelector('.prov-select');
      const calSel = calBlock.querySelector('.cal-select');
      const provLabel = provSel.value ? provSel.options[provSel.selectedIndex].text : '—';
      const calLabel = calSel.value ? calSel.options[calSel.selectedIndex].text : '';

      let calTotal = 0;
      calBlock.querySelectorAll('.pesada-row').forEach(function (row) {
        const r = calcPesada(row);
        if (r.bruto > 0) calTotal += r.neto;
        totalValor += r.valor;
      });

      const badge = calBlock.querySelector('.calidad-total');
      if (badge) badge.textContent = calTotal.toFixed(2) + ' kg';

      if (calTotal > 0) {
        total += calTotal;
        if (calSel.value) {
          const key = calSel.value;
          if (!porCalidad[key]) porCalidad[key] = { label: calLabel, neto: 0 };
          porCalidad[key].neto += calTotal;
        }
        const pkey = provSel.value || '—';
        if (!porProveedor[pkey]) porProveedor[pkey] = { label: provLabel, neto: 0 };
        porProveedor[pkey].neto += calTotal;
      }
    });

    renderResumen(porCalidad, porProveedor, total, totalValor);
  }

  function renderResumen(porCalidad, porProveedor, total, totalValor) {
    if (!resumenEl) return;
    resumenEl.innerHTML = '';

    function section(title, items) {
      const wrap = document.createElement('div');
      wrap.className = 'mb-3';
      const h = document.createElement('div');
      h.className = 'small fw-semibold text-uppercase text-muted mb-1';
      h.textContent = title;
      wrap.appendChild(h);
      const keys = Object.keys(items);
      if (!keys.length) {
        const empty = document.createElement('div');
        empty.className = 'text-muted small';
        empty.textContent = 'Sin pesadas todavía';
        wrap.appendChild(empty);
        return wrap;
      }
      keys.forEach(function (k) {
        const row = document.createElement('div');
        row.className = 'd-flex justify-content-between';
        row.style.fontSize = '0.85rem';
        const label = document.createElement('span');
        label.textContent = items[k].label;
        const val = document.createElement('span');
        val.className = 'fw-semibold text-success';
        val.textContent = items[k].neto.toFixed(2) + ' kg';
        row.append(label, val);
        wrap.appendChild(row);
      });
      return wrap;
    }

    resumenEl.appendChild(section('Total por calidad', porCalidad));
    resumenEl.appendChild(section('Por proveedor', porProveedor));

    const totalsBox = document.createElement('div');
    totalsBox.className = 'border-top pt-2 mt-2';

    const totalKgBox = document.createElement('div');
    totalKgBox.className = 'd-flex justify-content-between fw-bold';
    const t1 = document.createElement('span');
    t1.textContent = 'Total en bodega';
    const t2 = document.createElement('span');
    t2.style.color = 'var(--orange-primary)';
    t2.textContent = total.toFixed(2) + ' kg';
    totalKgBox.append(t1, t2);

    const totalValorBox = document.createElement('div');
    totalValorBox.className = 'd-flex justify-content-between fw-bold mt-1';
    const tv1 = document.createElement('span');
    tv1.textContent = 'Total a pagar';
    const tv2 = document.createElement('span');
    tv2.style.color = 'var(--orange-primary)';
    tv2.textContent = totalValor > 0 ? fmtCOP(totalValor) : '-';
    totalValorBox.append(tv1, tv2);

    totalsBox.append(totalKgBox, totalValorBox);
    resumenEl.appendChild(totalsBox);
  }

  // ---------- construcción de bloques ----------
  function buildPesadaRow(data) {
    data = data || {};
    const i = seq++;
    const row = document.createElement('div');
    row.className = 'pesada-row d-flex flex-wrap gap-2 align-items-end mb-2';
    row.innerHTML =
      '<input type="hidden" name="proveedor_' + i + '">' +
      '<input type="hidden" name="clasificacion_' + i + '">' +
      '<div style="flex:1 1 120px;">' +
        '<label class="row-lbl">Kg Bruto</label>' +
        '<input type="number" min="0" step="0.01" name="kg_bruto_' + i + '" class="form-control form-control-sm input-bruto" placeholder="Kg" required>' +
      '</div>' +
      '<div style="flex:1 1 110px;">' +
        '<label class="row-lbl"><span class="tag-neg">N</span> Negras 1.6</label>' +
        '<input type="number" min="0" name="num_canastillas_negras_' + i + '" class="form-control form-control-sm input-neg" placeholder="0">' +
      '</div>' +
      '<div style="flex:1 1 110px;">' +
        '<label class="row-lbl"><span class="tag-col">C</span> Color 2.2</label>' +
        '<input type="number" min="0" name="num_canastillas_colores_' + i + '" class="form-control form-control-sm input-col" placeholder="0">' +
      '</div>' +
      '<div style="flex:0 0 90px;">' +
        '<label class="row-lbl">Neto</label>' +
        '<div class="kg-neto">-</div>' +
      '</div>' +
      '<div style="flex:1 1 110px;">' +
        '<label class="row-lbl">Precio/kg</label>' +
        '<input type="number" min="0" step="0.01" name="precio_' + i + '" class="form-control form-control-sm input-precio" placeholder="$/kg">' +
      '</div>' +
      '<div style="flex:0 0 104px;">' +
        '<label class="row-lbl">Valor</label>' +
        '<div class="kg-neto valor-pesada fw-semibold" style="color:var(--orange-primary);">-</div>' +
      '</div>' +
      '<button type="button" class="btn btn-sm btn-outline-danger btn-rm-pesada" title="Eliminar pesada"><i class="bi bi-x"></i></button>';

    if (data.kg_bruto != null) row.querySelector('.input-bruto').value = data.kg_bruto;
    if (data.num_canastillas_negras) row.querySelector('.input-neg').value = data.num_canastillas_negras;
    if (data.num_canastillas_colores) row.querySelector('.input-col').value = data.num_canastillas_colores;
    if (data.precio_por_kg) row.querySelector('.input-precio').value = data.precio_por_kg;
    return row;
  }

  function buildCalidadBlock(provBlock, data) {
    data = data || {};
    const cal = document.createElement('div');
    cal.className = 'calidad-block border rounded mb-2 p-2';

    const header = document.createElement('div');
    header.className = 'd-flex flex-wrap gap-2 align-items-center mb-2';

    const prodSel = document.createElement('select');
    prodSel.className = 'form-select form-select-sm prod-select';
    prodSel.style.flex = '1 1 160px';
    prodSel.required = true;
    fillSelect(prodSel, PRODUCTOS.map(function (p) { return { value: p.id, label: p.nombre }; }), 'Producto');

    const calSel = document.createElement('select');
    calSel.className = 'form-select form-select-sm cal-select';
    calSel.style.flex = '1 1 160px';
    calSel.required = true;
    fillSelect(calSel, [], 'Calidad');

    const badge = document.createElement('span');
    badge.className = 'badge text-bg-light calidad-total';
    badge.textContent = '0 kg';

    const rm = document.createElement('button');
    rm.type = 'button';
    rm.className = 'btn btn-sm btn-outline-danger btn-rm-calidad';
    rm.title = 'Eliminar calidad';
    rm.innerHTML = '<i class="bi bi-x"></i>';

    header.append(prodSel, calSel, badge, rm);

    const pesadas = document.createElement('div');
    pesadas.className = 'pesadas-container';

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'btn btn-sm btn-outline-primary btn-add-pesada';
    addBtn.innerHTML = '<i class="bi bi-plus-lg me-1"></i>Pesada';

    cal.append(header, pesadas, addBtn);
    provBlock.querySelector('.calidades-container').appendChild(cal);

    if (data.productoId) {
      prodSel.value = data.productoId;
      fillSelect(calSel, clasificacionesDe(data.productoId), 'Calidad');
      if (data.clasificacionId != null) calSel.value = data.clasificacionId;
    }

    const pesadasData = (data.pesadas && data.pesadas.length) ? data.pesadas : [null];
    pesadasData.forEach(function (p) {
      pesadas.appendChild(buildPesadaRow(p));
    });

    syncCalidad(cal);
    return cal;
  }

  function buildProveedorBlock(data) {
    data = data || {};
    const block = document.createElement('div');
    block.className = 'proveedor-block card border-0 shadow-sm mb-3';

    const header = document.createElement('div');
    header.className = 'card-header d-flex flex-wrap gap-2 justify-content-between align-items-center';

    const left = document.createElement('div');
    left.className = 'd-flex align-items-center gap-2';
    const icon = document.createElement('i');
    icon.className = 'bi bi-shop';
    const provSel = document.createElement('select');
    provSel.className = 'form-select form-select-sm prov-select';
    provSel.style.minWidth = '180px';
    provSel.required = true;
    fillSelect(provSel, PROVEEDORES.map(function (p) { return { value: p.id, label: p.nombre }; }), 'Proveedor');
    if (data.proveedorId) provSel.value = data.proveedorId;
    left.append(icon, provSel);

    const right = document.createElement('div');
    right.className = 'd-flex gap-2';
    const addCal = document.createElement('button');
    addCal.type = 'button';
    addCal.className = 'btn btn-sm btn-outline-light btn-add-calidad';
    addCal.innerHTML = '<i class="bi bi-plus-lg me-1"></i>Calidad';
    const rm = document.createElement('button');
    rm.type = 'button';
    rm.className = 'btn btn-sm btn-outline-danger btn-rm-proveedor';
    rm.title = 'Eliminar proveedor';
    rm.innerHTML = '<i class="bi bi-x"></i>';
    right.append(addCal, rm);

    header.append(left, right);

    const body = document.createElement('div');
    body.className = 'card-body calidades-container';

    block.append(header, body);
    container.appendChild(block);

    const calidades = (data.calidades && data.calidades.length) ? data.calidades : [null];
    calidades.forEach(function (c) {
      buildCalidadBlock(block, c);
    });

    syncProveedor(block);
    return block;
  }

  // Reconstruye el formulario agrupado a partir de las pesadas guardadas.
  function buildFromInitial(rows) {
    const byProveedor = new Map();

    rows.forEach(function (r) {
      const pid = String(r.proveedor_id);
      const cid = String(r.clasificacion_id);
      if (!byProveedor.has(pid)) byProveedor.set(pid, new Map());
      const byCalidad = byProveedor.get(pid);
      if (!byCalidad.has(cid)) {
        const cls = CLASIFICACIONES.find(function (c) { return String(c.id) === cid; });
        byCalidad.set(cid, {
          productoId: cls ? cls.producto_id : null,
          clasificacionId: cid,
          pesadas: [],
        });
      }
      byCalidad.get(cid).pesadas.push({
        kg_bruto: r.kg_bruto,
        num_canastillas_negras: r.num_canastillas_negras,
        num_canastillas_colores: r.num_canastillas_colores,
        precio_por_kg: r.precio_por_kg,
      });
    });

    byProveedor.forEach(function (byCalidad, pid) {
      buildProveedorBlock({
        proveedorId: pid,
        calidades: Array.from(byCalidad.values()),
      });
    });
  }

  // ---------- eventos ----------
  container.addEventListener('change', function (e) {
    const t = e.target;
    if (t.classList.contains('prod-select')) {
      const calBlock = t.closest('.calidad-block');
      const calSel = calBlock.querySelector('.cal-select');
      fillSelect(calSel, clasificacionesDe(t.value), 'Calidad');
      syncCalidad(calBlock);
      recalcAll();
    } else if (t.classList.contains('cal-select')) {
      syncCalidad(t.closest('.calidad-block'));
      recalcAll();
    } else if (t.classList.contains('prov-select')) {
      syncProveedor(t.closest('.proveedor-block'));
      recalcAll();
    }
  });

  container.addEventListener('input', function (e) {
    if (e.target.closest('.pesada-row')) recalcAll();
  });

  const btnAddProv = document.getElementById('btn_add_proveedor');
  if (btnAddProv) {
    btnAddProv.addEventListener('click', function () {
      buildProveedorBlock();
      recalcAll();
    });
  }

  container.addEventListener('click', function (e) {
    const addCal = e.target.closest('.btn-add-calidad');
    const addPes = e.target.closest('.btn-add-pesada');
    const rmProv = e.target.closest('.btn-rm-proveedor');
    const rmCal = e.target.closest('.btn-rm-calidad');
    const rmPes = e.target.closest('.btn-rm-pesada');

    if (addCal) {
      const block = addCal.closest('.proveedor-block');
      buildCalidadBlock(block);
      syncProveedor(block);
      recalcAll();
      return;
    }
    if (addPes) {
      const calBlock = addPes.closest('.calidad-block');
      const row = buildPesadaRow();
      calBlock.querySelector('.pesadas-container').appendChild(row);
      syncCalidad(calBlock);
      recalcAll();
      return;
    }
    if (rmProv) {
      rmProv.closest('.proveedor-block').remove();
      if (!container.querySelector('.proveedor-block')) buildProveedorBlock();
      recalcAll();
      return;
    }
    if (rmCal) { rmCal.closest('.calidad-block').remove(); recalcAll(); return; }
    if (rmPes) {
      const calBlock = rmPes.closest('.calidad-block');
      rmPes.closest('.pesada-row').remove();
      const left = calBlock.querySelectorAll('.pesada-row');
      if (!left.length) {
        calBlock.querySelector('.pesadas-container').appendChild(buildPesadaRow());
        syncCalidad(calBlock);
      }
      recalcAll();
      return;
    }
  });

  if (form) {
    form.addEventListener('submit', function () {
      syncAll();
    });
  }

  // ---------- arranque ----------
  if (INITIAL_ROWS.length) {
    buildFromInitial(INITIAL_ROWS);
  } else {
    buildProveedorBlock();
  }
  recalcAll();
})();
