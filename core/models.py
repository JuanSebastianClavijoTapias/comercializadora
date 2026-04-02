from django.db import models
from decimal import Decimal

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
    def __str__(self): return f"{self.producto.nombre} - {self.nombre}"
    class Meta:
        verbose_name = 'Clasificación'; verbose_name_plural = 'Clasificaciones'; ordering = ['producto', 'orden']

class CategoriaGasto(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Categoría de Gasto'; verbose_name_plural = 'Categorías de Gasto'; ordering = ['nombre']

class Viaje(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='viajes', verbose_name='Proveedor')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='viajes', verbose_name='Producto')
    fecha = models.DateField(verbose_name='Fecha')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"Viaje {self.producto} - {self.fecha} ({self.proveedor})"
    @property
    def total_kg_neto(self): return sum(lote.kg_neto for lote in self.lotes.all())
    @property
    def total_valor(self): return sum(lote.total for lote in self.lotes.all())
    @property
    def total_pagado(self): return sum(p.monto for p in self.pagos_proveedor.all())
    @property
    def saldo_pendiente(self): return self.total_valor - self.total_pagado
    class Meta:
        verbose_name = 'Viaje'; verbose_name_plural = 'Viajes'; ordering = ['-fecha', '-created_at']

class LoteClasificacion(models.Model):
    PESO_CANASTILLA_NEGRA = Decimal('1.6')
    PESO_CANASTILLA_COLOR = Decimal('2.2')
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name='lotes', verbose_name='Viaje')
    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.PROTECT, verbose_name='Clasificación')
    precio_por_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio por kg')
    kg_bruto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Kg bruto (con canastillas)')
    cantidad_canastillas_negras = models.IntegerField(default=0, verbose_name='Canastillas negras')
    cantidad_canastillas_colores = models.IntegerField(default=0, verbose_name='Canastillas de colores')
    @property
    def peso_canastillas(self):
        return (Decimal(str(self.cantidad_canastillas_negras)) * self.PESO_CANASTILLA_NEGRA +
                Decimal(str(self.cantidad_canastillas_colores)) * self.PESO_CANASTILLA_COLOR)
    @property
    def kg_neto(self):
        neto = self.kg_bruto - self.peso_canastillas
        if self.viaje.producto.tiene_descuento_gobierno and self.viaje.producto.porcentaje_descuento > 0:
            neto = neto - (neto * self.viaje.producto.porcentaje_descuento / 100)
        return neto
    @property
    def total(self): return self.kg_neto * self.precio_por_kg
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
    categoria = models.ForeignKey(CategoriaGasto, on_delete=models.PROTECT, verbose_name='Categoría')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    fecha = models.DateField(verbose_name='Fecha')
    def __str__(self): return f"{self.descripcion} - ${self.monto}"
    class Meta:
        verbose_name = 'Gasto'; verbose_name_plural = 'Gastos'; ordering = ['-fecha']

class VentaEfectivo(models.Model):
    fecha = models.DateField(verbose_name='Fecha')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='ventas_efectivo', verbose_name='Producto', null=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='ventas_efectivo', verbose_name='Cliente', null=True, blank=True)
    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.PROTECT, related_name='ventas_efectivo', verbose_name='Clasificación', null=True, blank=True)
    kg_vendido = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Kg vendido')
    precio_por_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Precio por kg')
    descripcion = models.CharField(max_length=300, blank=True, verbose_name='Descripción')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    def __str__(self): return f"Efectivo {self.fecha} - ${self.monto}"
    class Meta:
        verbose_name = 'Venta en Efectivo'; verbose_name_plural = 'Ventas en Efectivo'; ordering = ['-fecha']

class VentaCredito(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='ventas', verbose_name='Cliente')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='ventas_credito', verbose_name='Producto', null=True, blank=True)
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
    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.PROTECT, verbose_name='Clasificación')
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

class LiquidacionInventario(models.Model):
    fecha_inicio = models.DateField(verbose_name='Fecha inicio')
    fecha_fin = models.DateField(verbose_name='Fecha fin')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    @property
    def total_valor(self): return sum(d.total for d in self.detalles.all())
    def __str__(self): return f"Liquidación {self.fecha_inicio} al {self.fecha_fin}"
    class Meta:
        verbose_name = 'Liquidación de Inventario'; verbose_name_plural = 'Liquidaciones de Inventario'; ordering = ['-fecha_fin']

class DetalleInventario(models.Model):
    liquidacion = models.ForeignKey(LiquidacionInventario, on_delete=models.CASCADE, related_name='detalles', verbose_name='Liquidación')
    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.PROTECT, verbose_name='Clasificación')
    kg_ingresado = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Kg ingresado')
    kg_vendido = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Kg vendido')
    kg_restante = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Kg restante')
    precio_por_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio por kg')
    @property
    def total(self): return self.kg_restante * self.precio_por_kg
    def __str__(self): return f"{self.clasificacion} - {self.kg_restante} kg restante"
    class Meta:
        verbose_name = 'Detalle de Inventario'; verbose_name_plural = 'Detalles de Inventario'
