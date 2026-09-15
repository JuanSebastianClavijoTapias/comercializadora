"""Agregados de resumen diario y viajes.

Calcula las métricas de un día (con override manual vía ResumenDiario) y anota
los pagos de proveedor por viaje sin caer en N+1.
"""
from decimal import Decimal

from django.db.models import Sum, DecimalField, Subquery, OuterRef, Value
from django.db.models.functions import Coalesce

from ..models import (
    DesechoInventario, Gasto, LoteClasificacion, PagoProveedor, PagoVentaCredito,
    PesadaViaje, ResumenDiario, VentaCredito, VentaEfectivo, Viaje,
)
from .ventas import ventas_credito_with_totals

__all__ = ['RESUMEN_CAMPOS', 'resumen_fecha', 'viajes_with_totals']

RESUMEN_CAMPOS = ['efectivo', 'abonos', 'kg_credito', 'kg_total', 'ventas_total', 'por_cobrar', 'gastos', 'balance']


def _sum_sq(model, join_field, value_field):
    """Subquery de suma de ``value_field`` para las filas de ``model`` ligadas por ``join_field``."""
    return (
        model.objects
        .filter(**{join_field: OuterRef('pk')})
        .values(join_field)
        .annotate(t=Sum(value_field, output_field=DecimalField()))
        .values('t')
    )


def viajes_with_totals(qs=None):
    """Viaje con kg (lotes/podridos/desechos) y _total_pagado anotados.

    Permite que ``total_valor``, ``kg_neto_despues_podrido`` y ``saldo_pendiente``
    lean los agregados sin disparar queries por fila.
    """
    if qs is None:
        qs = Viaje.objects.all()
    return qs.annotate(
        _lotes_kg=Coalesce(Subquery(_sum_sq(LoteClasificacion, 'viaje', 'kg_neto'), output_field=DecimalField()),
                           Value(0, output_field=DecimalField())),
        _podridos_kg=Coalesce(Subquery(_sum_sq(PesadaViaje, 'viaje', 'kg_podridos'), output_field=DecimalField()),
                              Value(0, output_field=DecimalField())),
        _desechos_kg=Coalesce(Subquery(_sum_sq(DesechoInventario, 'viaje', 'kg'), output_field=DecimalField()),
                              Value(0, output_field=DecimalField())),
        _total_pagado=Coalesce(Subquery(_sum_sq(PagoProveedor, 'viaje', 'monto'), output_field=DecimalField()),
                               Value(0, output_field=DecimalField())),
    )


def resumen_fecha(fecha):
    """Métricas agregadas de un día; el valor manual (ResumenDiario) pisa al calculado."""
    ventas_ef = VentaEfectivo.objects.filter(fecha=fecha).prefetch_related('detalles')
    ventas_cr = VentaCredito.objects.filter(fecha=fecha).prefetch_related('detalles')
    gastos = Gasto.objects.filter(fecha=fecha)
    abonos = PagoVentaCredito.objects.filter(fecha=fecha)

    efectivo = sum(v.total for v in ventas_ef)
    abonos_total = sum(a.monto for a in abonos)
    credito_money = sum(v.total for v in ventas_cr)
    gastos_total = sum(g.monto for g in gastos)

    kg_credito = sum(v.total_kg for v in ventas_cr)
    kg_efectivo = Decimal('0')
    for ve in ventas_ef:
        detalles = list(ve.detalles.all())
        if detalles:
            kg_efectivo += sum(d.kg_vendido for d in detalles)
        else:
            kg_efectivo += ve.kg_vendido or Decimal('0')
    kg_total = kg_efectivo + kg_credito

    ventas_total = efectivo + credito_money

    por_cobrar = sum(
        v.saldo_pendiente for v in ventas_credito_with_totals(
            VentaCredito.objects.select_related('cliente').order_by('-fecha', '-id')
        ) if v.saldo_pendiente > 0
    )

    balance = (efectivo + abonos_total) - gastos_total

    calculado = {
        'efectivo': efectivo,
        'abonos': abonos_total,
        'kg_credito': kg_credito,
        'kg_total': kg_total,
        'ventas_total': ventas_total,
        'por_cobrar': por_cobrar,
        'gastos': gastos_total,
        'balance': balance,
    }

    manual = ResumenDiario.objects.filter(fecha=fecha).first()
    resultado = {}
    flags = {}
    for campo in RESUMEN_CAMPOS:
        valor_manual = getattr(manual, campo) if manual else None
        if valor_manual is not None:
            resultado[campo] = valor_manual
            flags[campo] = True
        else:
            resultado[campo] = calculado[campo]
            flags[campo] = False
    resultado['manual'] = flags
    return resultado
