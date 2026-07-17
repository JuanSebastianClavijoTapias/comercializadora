from django import template
import re

register = template.Library()

@register.filter
def cop(value):
    """Formatea un número con separador de miles colombiano (punto).
    Ej: 1500000 → 1.500.000"""
    try:
        n = int(round(float(value)))
        return f"{n:,}".replace(",", ".")
    except (ValueError, TypeError):
        return value


@register.filter
def abr_clasif(value):
    """Abrevia 'Clasificación X' → 'C. X'"""
    return re.sub(r'^[Cc]lasificaci[oó]n\s*', 'C. ', str(value))
