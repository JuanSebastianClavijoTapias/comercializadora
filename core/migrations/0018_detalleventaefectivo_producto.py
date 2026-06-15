# Generated manually to migrate DetalleVentaEfectivo from clasificacion to producto
# preserving historical data.

from django.db import migrations, models
import django.db.models.deletion


def migrar_clasificacion_a_producto(apps, schema_editor):
    DetalleVentaEfectivo = apps.get_model('core', 'DetalleVentaEfectivo')
    for detalle in DetalleVentaEfectivo.objects.all():
        if detalle.clasificacion_id and not detalle.producto_id:
            detalle.producto_id = detalle.clasificacion.producto_id
            detalle.save(update_fields=['producto'])


def revertir_producto_a_clasificacion(apps, schema_editor):
    # No es posible revertir de forma determinística a una única clasificación,
    # así que dejamos el campo clasificacion vacío en la reversión.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_desechoinventario'),
    ]

    operations = [
        # 1. Agregar producto como nullable para permitir la migración de datos.
        migrations.AddField(
            model_name='detalleventaefectivo',
            name='producto',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='core.producto',
                verbose_name='Producto'
            ),
        ),
        # 2. Hacer precio_por_kg opcional con valor por defecto 0.
        migrations.AlterField(
            model_name='detalleventaefectivo',
            name='precio_por_kg',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=0,
                max_digits=10,
                null=True,
                verbose_name='Precio por kg'
            ),
        ),
        # 3. Poblar producto desde clasificacion.producto.
        migrations.RunPython(
            migrar_clasificacion_a_producto,
            reverse_code=revertir_producto_a_clasificacion
        ),
        # 4. Asegurar que producto no sea nulo antes de eliminar clasificacion.
        migrations.AlterField(
            model_name='detalleventaefectivo',
            name='producto',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='core.producto',
                verbose_name='Producto'
            ),
        ),
        # 5. Eliminar el campo clasificacion.
        migrations.RemoveField(
            model_name='detalleventaefectivo',
            name='clasificacion',
        ),
    ]
