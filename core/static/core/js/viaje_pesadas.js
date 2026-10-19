// Registro de pesadas de un viaje: agregar, duplicar y eliminar filas.
// El índice de los name (kg_bruto_N, clasificacion_N, ...) es monótono: nunca
// se reutiliza, para evitar colisiones cuando se elimina una fila intermedia.
(function () {
  'use strict';

  const container = document.getElementById('pesadas_container');
  if (!container) return;

  const btnAdd = document.getElementById('btn_add_row');
  const btnDup = document.getElementById('btn_dup_row');
  let rowIndex = 1;

  function ordinal(n) {
    const nombres = {
      1: '1ra', 2: '2da', 3: '3ra', 4: '4ta', 5: '5ta',
      6: '6ta', 7: '7ma', 8: '8va', 9: '9na',
    };
    return nombres[n] || n + 'ma';
  }

  function baseName(el) {
    return (el.getAttribute('name') || '').replace(/_\d+$/, '');
  }

  function renumberLabels() {
    container.querySelectorAll('.pesada-row').forEach(function (row, idx) {
      const ord = ordinal(idx + 1);
      row.querySelectorAll('.num-label, .num-label-badge').forEach(function (el) {
        el.textContent = ord;
      });
    });
  }

  function updateRemoveButtons() {
    const rows = container.querySelectorAll('.pesada-row');
    rows.forEach(function (row) {
      row.querySelector('.btn-rm-row').disabled = rows.length === 1;
    });
  }

  // Clona una fila reasignando los name *_N y conservando el estado vivo de
  // los <select>. cloneNode solo copia la opción por defecto, no la elegida
  // por el usuario; por eso el valor se sincroniza a mano, emparejando por
  // nombre de campo y no por posición.
  function cloneRow(sourceRow) {
    const newRow = sourceRow.cloneNode(true);

    const selectValues = {};
    sourceRow.querySelectorAll('select').forEach(function (el) {
      selectValues[baseName(el)] = el.value;
    });

    newRow.querySelectorAll('input, select, textarea').forEach(function (el) {
      const name = el.getAttribute('name');
      if (name) el.setAttribute('name', name.replace(/_\d+$/, '_' + rowIndex));
    });

    newRow.querySelectorAll('select').forEach(function (el) {
      const value = selectValues[baseName(el)];
      if (value !== undefined) el.value = value;
    });

    return newRow;
  }

  function clearInputs(row) {
    row.querySelectorAll('input').forEach(function (el) { el.value = ''; });
  }

  function clearSelects(row) {
    row.querySelectorAll('select').forEach(function (el) { el.selectedIndex = 0; });
  }

  function appendRow(sourceRow, keepProduct) {
    const newRow = cloneRow(sourceRow);
    clearInputs(newRow);
    if (!keepProduct) clearSelects(newRow);

    container.appendChild(newRow);
    rowIndex++;
    renumberLabels();
    updateRemoveButtons();
  }

  if (btnAdd) {
    btnAdd.addEventListener('click', function () {
      appendRow(container.querySelector('.pesada-row'), false);
    });
  }

  if (btnDup) {
    btnDup.addEventListener('click', function () {
      const rows = container.querySelectorAll('.pesada-row');
      appendRow(rows[rows.length - 1], true);
    });
  }

  container.addEventListener('click', function (e) {
    const btn = e.target.closest('.btn-rm-row');
    if (!btn) return;
    const rows = container.querySelectorAll('.pesada-row');
    if (rows.length <= 1) return;
    btn.closest('.pesada-row').remove();
    renumberLabels();
    updateRemoveButtons();
  });

  updateRemoveButtons();
})();
