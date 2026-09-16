"""API pública de la capa de servicios de ``core``.

Las vistas importan desde acá (``from .services import *``) para no acoplarse a
la ubicación interna de cada helper.
"""
from .gastos import (
    ResumenGastos,
    parse_fecha,
    registrar_gastos,
    resumen_gastos_del_dia,
)
from .inventario import (
    NOMINA_CATEGORY_NAME,
    get_current_week_inventory_data,
    get_nomina_category,
    get_or_create_weekly_inventory,
    get_or_create_weekly_inventory_for_monday,
    get_week_inventory_data,
    get_week_monday,
    get_week_summary_url,
    get_weekly_history,
    parse_week_start,
    stock_valorizado,
    week_has_data,
)
from .resumen import RESUMEN_CAMPOS, resumen_fecha, viajes_with_totals
from .ventas import (
    normalizar_precio_cop,
    resolver_venta_credito,
    ventas_credito_with_totals,
)

__all__ = [
    'ResumenGastos',
    'parse_fecha',
    'registrar_gastos',
    'resumen_gastos_del_dia',
    'NOMINA_CATEGORY_NAME',
    'get_current_week_inventory_data',
    'get_nomina_category',
    'get_or_create_weekly_inventory',
    'get_or_create_weekly_inventory_for_monday',
    'get_week_inventory_data',
    'get_week_monday',
    'get_week_summary_url',
    'get_weekly_history',
    'parse_week_start',
    'stock_valorizado',
    'week_has_data',
    'RESUMEN_CAMPOS',
    'resumen_fecha',
    'viajes_with_totals',
    'normalizar_precio_cop',
    'ventas_credito_with_totals',
    'resolver_venta_credito',
]
