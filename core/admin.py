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

@admin.register(VentaCredito)
class VentaCreditoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'cliente']

@admin.register(VentaEfectivo)
class VentaEfectivoAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'descripcion', 'monto']
