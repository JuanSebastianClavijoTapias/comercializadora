# -*- coding: utf-8 -*-
import re

with open("C:/Users/samue/Downloads/PROYECTOS_GAMORA/django_comercializadora/comercializadora/fruta_system/fruta_system/core/templates/core/viaje_detail.html", "r", encoding="utf-8") as f:
    text = f.read()

new_html = r"""  <div class="col-md-8">
    <div class="card">
      <div class="card-header py-2 fw-semibold d-flex justify-content-between align-items-center">
        <span><i class="bi bi-list-check me-2 text-success"></i>Distribuir Neto en Clasificaciones</span>
        <span class="badge bg-primary" id="kilos_restantes_badge">Calculando...</span>
      </div>
      <div class="card-body p-0">
        <form method="post" id="clasificaciones_form">
          {% csrf_token %}
          <input type="hidden" name="guardar_clasificaciones" value="1">
          <table class="table table-hover mb-0">
            <thead>
              <tr>
                <th>Clasificaci&oacute;n</th>
                <th>Kg Neto</th>
                <th>Precio / Kg</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {% for cd in clases_data %}
              <tr>
                <td class="align-middle fw-medium">{{ cd.clasificacion.nombre }}</td>
                <td>
                  <input type="number" step="0.01" name="kg_neto_{{ cd.clasificacion.id }}" 
                         class="form-control form-control-sm neto-input" 
                         value="{{ cd.kg_neto }}">
                </td>
                <td>
                  <input type="number" step="0.01" name="precio_por_kg_{{ cd.clasificacion.id }}" 
                         class="form-control form-control-sm precio-input" 
                         value="{{ cd.precio_por_kg }}">
                </td>
                <td class="align-middle fw-bold text-success total-row">$0</td>
              </tr>
              {% empty %}
              <tr><td colspan="4" class="text-center text-muted">No hay clasificaciones activas para este producto.</td></tr>
              {% endfor %}
            </tbody>
            <tfoot class="table-light">
              <tr>
                <th class="text-end">Total Distribuido:</th>
                <th id="total_kg_distribuido" class="fs-6">0.00 kg</th>
                <th></th>
                <th id="total_dinero_calculado" class="text-success fs-6">$0</th>
              </tr>
            </tfoot>
          </table>
          <div class="p-3 border-top d-flex justify-content-between align-items-center">
            <span class="text-danger small fw-bold" id="error_msg" style="display:none;">
              <i class="bi bi-exclamation-triangle me-1"></i>!Excedido de Kg Netos!
            </span>
            <button type="submit" class="btn btn-success" id="btn_guardar_clas">
              <i class="bi bi-save me-1"></i>Guardar Clasificaciones
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>"""

match = re.search(r'  <div class="col-md-8">.*?</table>\s*</div>\s*</div>', text, re.DOTALL)
if match:
    text = text.replace(match.group(0), new_html)
    with open("C:/Users/samue/Downloads/PROYECTOS_GAMORA/django_comercializadora/comercializadora/fruta_system/fruta_system/core/templates/core/viaje_detail.html", "w", encoding="utf-8") as f:
        f.write(text)

