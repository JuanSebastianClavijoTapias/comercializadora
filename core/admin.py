from django.contrib import admin
from .models import *

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono', 'activo']
    search_fields = ['nombre']

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono', 'activo']
    search_fields = ['nombre']

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tiene_descuento_gobierno', 'porcentaje_descuento', 'activo']

@admin.register(Clasificacion)
class ClasificacionAdmin(admin.ModelAdmin):
    list_display = ['producto', 'nombre', 'orden', 'activo']
    list_filter = ['producto']

@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(admin.ModelAdmin):
    list_display = ['nombre']

@admin.register(Viaje)
class ViajeAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'producto', 'proveedor']
    list_filter = ['producto', 'proveedor']

@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'categoria', 'descripcion', 'monto']
    list_filter = ['categoria', 'fecha']

@admin.register(WeeklyInventory)
class WeeklyInventoryAdmin(admin.ModelAdmin):
    list_display = ['week_start', 'initial_inventory_kg', 'total_inventory_kg_display', 'updated_at']
    readonly_fields = ['created_at', 'updated_at', 'total_inventory_kg_display']
    fields = ['week_start', 'initial_inventory_kg', 'total_inventory_kg_display', 'created_at', 'updated_at']
    list_filter = ['week_start']
    ordering = ['-week_start']
    
    def total_inventory_kg_display(self, obj):
        """Muestra el total de inventario (inicial + compras de la semana)"""
        return f"{obj.total_inventory_kg:.2f} kg"
    total_inventory_kg_display.short_description = 'Total Inventario (Inicial + Compras)'

@admin.register(VentaCredito)
class VentaCreditoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'cliente']

class DetalleVentaEfectivoInline(admin.TabularInline):
    model = DetalleVentaEfectivo
    extra = 1
    fields = ['clasificacion', 'kg_vendido', 'precio_por_kg']
    readonly_fields = []

@admin.register(VentaEfectivo)
class VentaEfectivoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'cliente', 'total']
    inlines = [DetalleVentaEfectivoInline]

@admin.register(DetalleVentaEfectivo)
class DetalleVentaEfectivoAdmin(admin.ModelAdmin):
    list_display = ['venta', 'clasificacion', 'kg_vendido', 'precio_por_kg', 'total']
