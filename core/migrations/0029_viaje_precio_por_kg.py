from django.db import migrations
from decimal import Decimal


def convertir_precios_a_por_kg(apps, schema_editor):
    Viaje = apps.get_model('core', 'Viaje')
    LoteClasificacion = apps.get_model('core', 'LoteClasificacion')
    for viaje in Viaje.objects.all():
        # Calcular kg neto total del viaje
        kg_neto = Decimal('0')
        for lote in viaje.lotes.all():
            kg_neto += lote.kg_neto
        if kg_neto > 0 and viaje.precio_total_acordado > 0:
            viaje.precio_total_acordado = viaje.precio_total_acordado / kg_neto
            viaje.save(update_fields=['precio_total_acordado'])


def reverse_conversion(apps, schema_editor):
    Viaje = apps.get_model('core', 'Viaje')
    for viaje in Viaje.objects.all():
        kg_neto = Decimal('0')
        for lote in viaje.lotes.all():
            kg_neto += lote.kg_neto
        if kg_neto > 0 and viaje.precio_total_acordado > 0:
            viaje.precio_total_acordado = viaje.precio_total_acordado * kg_neto
            viaje.save(update_fields=['precio_total_acordado'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_pesada_entrada_clasificacion'),
    ]

    operations = [
        migrations.RunPython(convertir_precios_a_por_kg, reverse_conversion),
    ]