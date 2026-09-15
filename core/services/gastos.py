"""Lógica de negocio de gastos.

Las vistas quedan como orquestación HTTP; acá vive la persistencia y la
agregación, de modo que sea reutilizable y testeable fuera del ciclo request.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from ..models import Gasto

__all__ = ['parse_fecha', 'registrar_gastos', 'ResumenGastos', 'resumen_gastos_del_dia']


def parse_fecha(value, default=None):
    """Convierte una fecha ISO a ``datetime.date``; si es inválida devuelve ``default``."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def registrar_gastos(formset, fecha):
    """Persiste los gastos válidos del formset con la ``fecha`` compartida.

    Ignora las filas vacías y es atómico: o se crean todos o ninguno.
    Devuelve la cantidad de gastos creados.
    """
    with transaction.atomic():
        creados = 0
        for form in formset:
            datos = form.cleaned_data
            if datos.get('descripcion') and datos.get('monto') is not None:
                gasto = form.save(commit=False)
                gasto.fecha = fecha
                gasto.save()
                creados += 1
        return creados


@dataclass(frozen=True)
class ResumenGastos:
    gastos: list[Gasto]
    total: Decimal
    cantidad: int
    promedio: Decimal
    maximo: Decimal


def resumen_gastos_del_dia(fecha):
    """Totales de los gastos de un día (una sola consulta)."""
    gastos = list(Gasto.objects.filter(fecha=fecha))
    total = sum((g.monto for g in gastos), Decimal('0'))
    cantidad = len(gastos)
    promedio = (total / cantidad) if cantidad else Decimal('0')
    maximo = max((g.monto for g in gastos), default=Decimal('0'))
    return ResumenGastos(gastos, total, cantidad, promedio, maximo)
