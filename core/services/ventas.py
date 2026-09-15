"""Helpers de consulta y normalización de ventas.

Evitan N+1 anotando totales con subqueries, de modo que las propiedades de los
modelos lean el valor anotado en lugar de disparar una query por fila.
"""
from django.db.models import Sum, F, DecimalField, Subquery, OuterRef, Value
from django.db.models.functions import Coalesce

from ..models import VentaCredito, DetalleVentaCredito, PagoVentaCredito

__all__ = ['ventas_credito_with_totals', 'normalizar_precio_cop']


def ventas_credito_with_totals(qs=None):
    """VentaCredito con _total, _total_pagado y _total_kg anotados (evita N+1)."""
    if qs is None:
        qs = VentaCredito.objects.all()
    total_sq = (
        DetalleVentaCredito.objects
        .filter(venta=OuterRef('pk'))
        .values('venta')
        .annotate(t=Sum(F('kg_vendido') * F('precio_por_kg'), output_field=DecimalField()))
        .values('t')
    )
    pagado_sq = (
        PagoVentaCredito.objects
        .filter(venta=OuterRef('pk'))
        .values('venta')
        .annotate(t=Sum('monto', output_field=DecimalField()))
        .values('t')
    )
    kg_sq = (
        DetalleVentaCredito.objects
        .filter(venta=OuterRef('pk'))
        .values('venta')
        .annotate(t=Sum('kg_vendido', output_field=DecimalField()))
        .values('t')
    )
    return qs.annotate(
        _total=Coalesce(Subquery(total_sq, output_field=DecimalField()),
                        Value(0, output_field=DecimalField())),
        _total_pagado=Coalesce(Subquery(pagado_sq, output_field=DecimalField()),
                               Value(0, output_field=DecimalField())),
        _total_kg=Coalesce(Subquery(kg_sq, output_field=DecimalField()),
                           Value(0, output_field=DecimalField())),
    )


def normalizar_precio_cop(valor):
    """Convierte un precio con formato colombiano (2.500) a string numérico (2500)."""
    if not valor:
        return ''
    return str(valor).replace('.', '').replace(',', '.').strip()
