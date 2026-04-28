from django.db import models
from decimal import Decimal
from datetime import timedelta

MEDIO_PAGO_CHOICES = [
    ('efectivo', 'Efectivo'),
    ('transferencia', 'Transferencia'),
    ('cheque', 'Cheque'),
]

class Proveedor(models.Model):
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    direccion = models.TextField(blank=True, verbose_name='Dirección')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Proveedor'; verbose_name_plural = 'Proveedores'; ordering = ['nombre']

class Cliente(models.Model):
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    direccion = models.TextField(blank=True, verbose_name='Dirección')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Cliente'; verbose_name_plural = 'Clientes'; ordering = ['nombre']

class Producto(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    tiene_descuento_gobierno = models.BooleanField(default=False, verbose_name='Descuento gobierno')
    porcentaje_descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='% Descuento gobierno')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Producto'; verbose_name_plural = 'Productos'; ordering = ['nombre']

class Clasificacion(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='clasificaciones', verbose_name='Producto')
    nombre = models.CharField(max_length=100, verbose_name='Nombre clasificación')
    orden = models.IntegerField(default=1, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Activa')
    stock_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Stock (Kg)')
    
    def __str__(self): return f"{self.producto.nombre} - {self.nombre} (Stock: {self.stock_kg} kg)"
    class Meta:
        verbose_name = 'Clasificación'; verbose_name_plural = 'Clasificaciones'; ordering = ['producto', 'orden']

class CategoriaGasto(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Categoría de Gasto'; verbose_name_plural = 'Categorías de Gasto'; ordering = ['nombre']

class Viaje(models.Model):
    PESO_CANASTILLA_NEGRA = Decimal('1.6')
    PESO_CANASTILLA_COLOR = Decimal('2.2')

    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='viajes', verbose_name='Proveedor')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='viajes', verbose_name='Producto')
    fecha = models.DateField(verbose_name='Fecha')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    kg_podridos = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Kg Podridos / Rechazo')
    precio_total_acordado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Precio Total Acordado')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"Viaje {self.producto} - {self.fecha} ({self.proveedor})"

    @property
    def kg_bruto(self):
        return sum((p.kg_bruto for p in self.pesadas.all()), Decimal('0'))

    @property
    def cantidad_canastillas_negras(self):
        return sum(p.num_canastillas_negras for p in self.pesadas.all())

    @property
    def cantidad_canastillas_colores(self):
        return sum(p.num_canastillas_colores for p in self.pesadas.all())

    @property
    def peso_canastillas(self):
        return sum((p.peso_canastillas for p in self.pesadas.all()), Decimal('0'))

    @property
    def neto_a_pagar(self):
        kg_p = self.kg_podridos or Decimal('0')
        neto = self.kg_bruto - kg_p - self.peso_canastillas
        if self.producto.tiene_descuento_gobierno and self.producto.porcentaje_descuento > 0:
            neto = neto - (neto * self.producto.porcentaje_descuento / 100)
        return max(neto, Decimal('0'))

    @property
    def total_kg_neto(self): return sum(lote.kg_neto for lote in self.lotes.all())
    @property
    def total_valor(self): return self.precio_total_acordado
    @property
    def total_pagado(self): return sum(p.monto for p in self.pagos_proveedor.all())
    @property
    def saldo_pendiente(self): return self.total_valor - self.total_pagado
    class Meta:
        verbose_name = 'Viaje'; verbose_name_plural = 'Viajes'; ordering = ['-fecha', '-created_at']


class PesadaViaje(models.Model):
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name='pesadas', verbose_name='Viaje')
    num_canastillas_negras = models.PositiveIntegerField(default=0, verbose_name='Canastillas Negras (1.6 kg)')
    num_canastillas_colores = models.PositiveIntegerField(default=0, verbose_name='Canastillas Color (2.2 kg)')
    kg_bruto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Kg Bruto')

    @property
    def total_canastillas(self):
        return self.num_canastillas_negras + self.num_canastillas_colores

    @property
    def peso_canastillas(self):
        return (Decimal(str(self.num_canastillas_negras)) * Decimal('1.6') +
                Decimal(str(self.num_canastillas_colores)) * Decimal('2.2'))

    @property
    def kg_neto(self):
        return max(self.kg_bruto - self.peso_canastillas, Decimal('0'))

    def __str__(self):
        partes = []
        if self.num_canastillas_negras: partes.append(f"{self.num_canastillas_negras} neg.")
        if self.num_canastillas_colores: partes.append(f"{self.num_canastillas_colores} col.")
        return f"{' + '.join(partes) or '0 can.'} - {self.kg_bruto} kg bruto"

    class Meta:
        verbose_name = 'Pesada'; verbose_name_plural = 'Pesadas'; ordering = ['id']

class LoteClasificacion(models.Model):
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name='lotes', verbose_name='Viaje')
    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.CASCADE, verbose_name='Clasificación')
    kg_neto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Kg Neto Clasificado')
    
    def __str__(self): return f"{self.clasificacion.nombre} - {self.kg_neto:.2f} kg neto"
    class Meta:
        verbose_name = 'Lote por Clasificación'; verbose_name_plural = 'Lotes por Clasificación'

class PagoProveedor(models.Model):
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name='pagos_proveedor', verbose_name='Viaje')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, verbose_name='Medio de pago')
    fecha = models.DateField(verbose_name='Fecha')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    def __str__(self): return f"Pago a {self.viaje.proveedor} - ${self.monto}"
    class Meta:
        verbose_name = 'Pago a Proveedor'; verbose_name_plural = 'Pagos a Proveedores'; ordering = ['-fecha']

class Gasto(models.Model):
    categoria = models.ForeignKey(CategoriaGasto, on_delete=models.CASCADE, verbose_name='Categoría')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    fecha = models.DateField(verbose_name='Fecha')
    pago_proveedor = models.OneToOneField(PagoProveedor, on_delete=models.CASCADE, null=True, blank=True, related_name='gasto_generado', verbose_name='Pago Proveedor (vinculado)')
    def __str__(self): return f"{self.descripcion} - ${self.monto}"
    class Meta:
        verbose_name = 'Gasto'; verbose_name_plural = 'Gastos'; ordering = ['-fecha']

class WeeklyInventory(models.Model):
    """Tracks weekly inventory snapshots for Monday reset mechanism"""
    week_start = models.DateField(verbose_name='Inicio de Semana (Lunes)', unique=True)
    initial_inventory_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Inventario Inicial (kg)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado')
    
    def __str__(self):
        week_end = self.week_start + timedelta(days=6)
        return f"Semana {self.week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m/%Y')}"
    
    @property
    def total_inventory_kg(self):
        """Calcula el inventario total: inicial + compras de la semana"""
        from datetime import timedelta
        week_end = self.week_start + timedelta(days=6)
        # Obtener todos los lotes clasificados de viajes de esta semana
        lotes_semana = LoteClasificacion.objects.filter(viaje__fecha__range=[self.week_start, week_end])
        compras_semana = sum(lote.kg_neto for lote in lotes_semana) or Decimal('0')
        return self.initial_inventory_kg + compras_semana
    
    class Meta:
        verbose_name = 'Inventario Semanal'
        verbose_name_plural = 'Inventarios Semanales'
        ordering = ['-week_start']
        indexes = [models.Index(fields=['week_start'])]

class VentaEfectivo(models.Model):
    fecha = models.DateField(verbose_name='Fecha')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='ventas_efectivo', verbose_name='Cliente', null=True, blank=True)
    descripcion = models.CharField(max_length=300, blank=True, verbose_name='Descripción')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    
    @property
    def total(self):
        return sum(d.total for d in self.detalles.all())
    
    def __str__(self):
        cliente_str = self.cliente.nombre if self.cliente else 'General'
        return f"Venta Efectivo {self.fecha} - {cliente_str} - ${self.total}"
    
    class Meta:
        verbose_name = 'Venta en Efectivo'
        verbose_name_plural = 'Ventas en Efectivo'
        ordering = ['-fecha']

class DetalleVentaEfectivo(models.Model):
    venta = models.ForeignKey(VentaEfectivo, on_delete=models.CASCADE, related_name='detalles', verbose_name='Venta')
    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.CASCADE, verbose_name='Clasificación')
    kg_vendido = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Kg vendido')
    precio_por_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio por kg')
    
    @property
    def total(self):
        return self.kg_vendido * self.precio_por_kg
    
    def __str__(self):
        return f"{self.clasificacion} - {self.kg_vendido} kg @ ${self.precio_por_kg}/kg"
    
    class Meta:
        verbose_name = 'Detalle de Venta Efectivo'
        verbose_name_plural = 'Detalles de Ventas Efectivo'

class VentaCredito(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='ventas', verbose_name='Cliente')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='ventas_credito', verbose_name='Producto', null=True, blank=True)
    fecha = models.DateField(verbose_name='Fecha de venta')
    fecha_vencimiento = models.DateField(verbose_name='Fecha de vencimiento', null=True, blank=True)
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    created_at = models.DateTimeField(auto_now_add=True)
    @property
    def total(self): return sum(d.total for d in self.detalles.all())
    @property
    def total_pagado(self): return sum(p.monto for p in self.pagos.all())
    @property
    def saldo_pendiente(self): return self.total - self.total_pagado
    def __str__(self): return f"Venta crédito {self.cliente} - {self.fecha}"
    class Meta:
        verbose_name = 'Venta a Crédito'; verbose_name_plural = 'Ventas a Crédito'; ordering = ['-fecha']

class DetalleVentaCredito(models.Model):
    venta = models.ForeignKey(VentaCredito, on_delete=models.CASCADE, related_name='detalles', verbose_name='Venta')
    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.CASCADE, verbose_name='Clasificación')
    kg_vendido = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Kg vendido')
    precio_por_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio por kg')
    @property
    def total(self): return self.kg_vendido * self.precio_por_kg
    def __str__(self): return f"{self.clasificacion} - {self.kg_vendido} kg"
    class Meta:
        verbose_name = 'Detalle de Venta'; verbose_name_plural = 'Detalles de Venta'

class PagoVentaCredito(models.Model):
    venta = models.ForeignKey(VentaCredito, on_delete=models.CASCADE, related_name='pagos', verbose_name='Venta')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, verbose_name='Medio de pago')
    fecha = models.DateField(verbose_name='Fecha')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    def __str__(self): return f"Pago de {self.venta.cliente} - ${self.monto}"
    class Meta:
        verbose_name = 'Pago de Venta'; verbose_name_plural = 'Pagos de Ventas'; ordering = ['-fecha']

# ------------- SEÑALES PARA ACTUALIZAR STOCK -------------
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.db.models import F

@receiver(pre_save, sender=LoteClasificacion)
def captura_anterior_lote(sender, instance, **kwargs):
    if instance.pk:
        orig = LoteClasificacion.objects.get(pk=instance.pk)
        instance._old_kg_neto = orig.kg_neto
    else:
        instance._old_kg_neto = Decimal('0')

@receiver(post_save, sender=LoteClasificacion)
def actualiza_stock_lote_save(sender, instance, created, **kwargs):
    # Cuando entra mercancia al LoteClasificacion, SUMA al stock
    diff = instance.kg_neto - getattr(instance, '_old_kg_neto', Decimal('0'))
    if diff != 0 and instance.clasificacion:
        instance.clasificacion.stock_kg = F('stock_kg') + diff
        instance.clasificacion.save(update_fields=['stock_kg'])

@receiver(post_delete, sender=LoteClasificacion)
def actualiza_stock_lote_delete(sender, instance, **kwargs):
    if instance.clasificacion:
        instance.clasificacion.stock_kg = F('stock_kg') - instance.kg_neto
        instance.clasificacion.save(update_fields=['stock_kg'])

@receiver(pre_save, sender=VentaEfectivo)
def captura_anterior_venta_efectivo(sender, instance, **kwargs):
    if instance.pk:
        orig = VentaEfectivo.objects.get(pk=instance.pk)
        instance._old_kg_vendido = orig.kg_vendido
    else:
        instance._old_kg_vendido = Decimal('0')

@receiver(pre_save, sender=DetalleVentaEfectivo)
def captura_anterior_detalle_venta_efectivo(sender, instance, **kwargs):
    if instance.pk:
        orig = DetalleVentaEfectivo.objects.get(pk=instance.pk)
        instance._old_kg_vendido = orig.kg_vendido
    else:
        instance._old_kg_vendido = Decimal('0')

@receiver(post_save, sender=DetalleVentaEfectivo)
def actualiza_stock_detalle_venta_efectivo_save(sender, instance, created, **kwargs):
    # Cuando se crea o actualiza un detalle, restar/actualizar el stock
    if instance.clasificacion:
        if created:
            # Venta nueva: restar kg del stock
            instance.clasificacion.stock_kg = F('stock_kg') - instance.kg_vendido
        else:
            # Actualización: calcular la diferencia
            diff = instance.kg_vendido - getattr(instance, '_old_kg_vendido', instance.kg_vendido)
            if diff != 0:
                instance.clasificacion.stock_kg = F('stock_kg') - diff
        instance.clasificacion.save(update_fields=['stock_kg'])

@receiver(post_delete, sender=DetalleVentaEfectivo)
def actualiza_stock_detalle_venta_efectivo_delete(sender, instance, **kwargs):
    # Cuando se elimina un detalle, devolver los kg al stock
    if instance.clasificacion:
        instance.clasificacion.stock_kg = F('stock_kg') + instance.kg_vendido
        instance.clasificacion.save(update_fields=['stock_kg'])

@receiver(post_save, sender=VentaEfectivo)
def actualiza_stock_venta_efectivo_save(sender, instance, created, **kwargs):
    # La lógica de stock se maneja en DetalleVentaEfectivo
    pass

@receiver(pre_save, sender=DetalleVentaCredito)
def captura_anterior_venta_credito(sender, instance, **kwargs):
    if instance.pk:
        orig = DetalleVentaCredito.objects.get(pk=instance.pk)
        instance._old_kg_vendido = orig.kg_vendido
    else:
        instance._old_kg_vendido = Decimal('0')

@receiver(post_save, sender=DetalleVentaCredito)
def actualiza_stock_venta_credito_save(sender, instance, created, **kwargs):
    # Cuando se crea o actualiza un detalle, restar/actualizar el stock
    if instance.clasificacion:
        if created:
            # Venta nueva: restar kg del stock
            instance.clasificacion.stock_kg = F('stock_kg') - instance.kg_vendido
            instance.clasificacion.save(update_fields=['stock_kg'])
        else:
            # Actualización: calcular la diferencia
            old_kg = getattr(instance, '_old_kg_vendido', Decimal('0'))
            diff = instance.kg_vendido - old_kg
            if diff != 0:
                instance.clasificacion.stock_kg = F('stock_kg') - diff
                instance.clasificacion.save(update_fields=['stock_kg'])

@receiver(post_delete, sender=DetalleVentaCredito)
def actualiza_stock_venta_credito_delete(sender, instance, **kwargs):
    if instance.clasificacion:
        instance.clasificacion.stock_kg = F('stock_kg') + instance.kg_vendido
        instance.clasificacion.save(update_fields=['stock_kg'])
