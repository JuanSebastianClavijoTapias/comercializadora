# Generated migration to link Gasto with PagoProveedor

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_remove_loteclasificacion_precio_por_kg_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='gasto',
            name='pago_proveedor',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='gasto_generado',
                to='core.pagoproveedor',
                verbose_name='Pago Proveedor (vinculado)'
            ),
        ),
    ]
