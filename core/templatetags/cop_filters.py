from django import template

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
