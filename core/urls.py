from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    # Proveedores
    path('proveedores/', views.proveedor_list, name='proveedor_list'),
    path('proveedores/nuevo/', views.proveedor_create, name='proveedor_create'),
    path('proveedores/<int:pk>/editar/', views.proveedor_edit, name='proveedor_edit'),
    path('proveedores/<int:pk>/eliminar/', views.proveedor_delete, name='proveedor_delete'),
    # Clientes
    path('clientes/', views.cliente_list, name='cliente_list'),
    path('clientes/nuevo/', views.cliente_create, name='cliente_create'),
    path('clientes/<int:pk>/editar/', views.cliente_edit, name='cliente_edit'),
    path('clientes/<int:pk>/eliminar/', views.cliente_delete, name='cliente_delete'),
    # Productos
    path('productos/', views.producto_list, name='producto_list'),
    path('productos/nuevo/', views.producto_create, name='producto_create'),
    path('productos/<int:pk>/editar/', views.producto_edit, name='producto_edit'),
    path('productos/<int:pk>/eliminar/', views.producto_delete, name='producto_delete'),
    path('productos/<int:pk>/clasificaciones/', views.producto_clasificaciones, name='producto_clasificaciones'),
    path('productos/<int:pk>/stock/', views.producto_stock_update, name='producto_stock_update'),
    path('clasificaciones/<int:pk>/editar/', views.clasificacion_edit, name='clasificacion_edit'),
    # Categorias Gasto
    path('categorias-gasto/', views.categoria_gasto_list, name='categoria_gasto_list'),
    path('categorias-gasto/<int:pk>/editar/', views.categoria_gasto_edit, name='categoria_gasto_edit'),
    path('categorias-gasto/<int:pk>/eliminar/', views.categoria_gasto_delete, name='categoria_gasto_delete'),
    # Viajes
    path('viajes/', views.viaje_list, name='viaje_list'),
    path('viajes/nuevo/', views.viaje_create, name='viaje_create'),
    path('viajes/<int:pk>/', views.viaje_detail, name='viaje_detail'),
    path('viajes/<int:pk>/precio/', views.viaje_precio_update, name='viaje_precio_update'),
    path('viajes/<int:pk>/eliminar/', views.viaje_delete, name='viaje_delete'),
    path('viajes/<int:pk>/pago/', views.viaje_pago_add, name='viaje_pago_add'),
    path('viajes/<int:pk>/pesada/', views.pesada_add, name='pesada_add'),
    path('pesadas/<int:pk>/eliminar/', views.pesada_delete, name='pesada_delete'),
    path('pesadas/<int:pk>/editar/', views.pesada_edit, name='pesada_edit'),
    path('pesadas/<int:pk>/update-field/', views.pesada_update_field, name='pesada_update_field'),
    path('lotes/<int:pk>/eliminar/', views.lote_delete, name='lote_delete'),
    path('pagos-proveedor/<int:pk>/eliminar/', views.pago_proveedor_delete, name='pago_proveedor_delete'),
    # Gastos
    path('gastos/', views.gasto_list, name='gasto_list'),
    path('gastos/<int:pk>/', views.gasto_detail, name='gasto_detail'),
    path('gastos/<int:pk>/editar/', views.gasto_edit, name='gasto_edit'),
    path('gastos/<int:pk>/eliminar/', views.gasto_delete, name='gasto_delete'),
    # Ventas Efectivo
    path('ventas/efectivo/', views.venta_efectivo_list, name='venta_efectivo_list'),
    path('ventas/efectivo/nueva/', views.venta_efectivo_create, name='venta_efectivo_create'),
    path('ventas/efectivo/<int:pk>/editar/', views.venta_efectivo_edit, name='venta_efectivo_edit'),
    path('ventas/efectivo/<int:pk>/', views.venta_efectivo_detail, name='venta_efectivo_detail'),
    path('ventas/efectivo/<int:pk>/eliminar/', views.venta_efectivo_delete, name='venta_efectivo_delete'),
    path('ventas/efectivo/detalle/<int:pk>/eliminar/', views.detalle_venta_efectivo_delete, name='detalle_venta_efectivo_delete'),
    # Ventas Credito
    path('ventas/credito/', views.venta_credito_list, name='venta_credito_list'),
    path('ventas/credito/nueva/', views.venta_credito_create, name='venta_credito_create'),
    path('ventas/credito/<int:pk>/', views.venta_credito_detail, name='venta_credito_detail'),
    path('ventas/credito/<int:pk>/detalle-ajax/', views.venta_credito_add_detalle_ajax, name='venta_credito_add_detalle_ajax'),
    path('ventas/credito/<int:pk>/eliminar/', views.venta_credito_delete, name='venta_credito_delete'),
    path('ventas/credito/<int:pk>/pago/', views.venta_credito_pago_add, name='venta_credito_pago_add'),
    path('detalles-venta/<int:pk>/eliminar/', views.detalle_venta_delete, name='detalle_venta_delete'),
    path('pagos-venta/<int:pk>/eliminar/', views.pago_venta_delete, name='pago_venta_delete'),
    # Reportes
    path('reportes/diario/', views.reporte_diario, name='reporte_diario'),
    path('reportes/cartera/', views.reporte_cartera, name='reporte_cartera'),
    path('reportes/proveedores/', views.reporte_proveedor, name='reporte_proveedor'),
    # Entradas de Inventario
    path('inventario/entradas/', views.entrada_inventario_list, name='entrada_inventario_list'),
    path('inventario/entradas/nueva/', views.entrada_inventario_create, name='entrada_inventario_create'),
    path('inventario/entradas/<int:pk>/', views.entrada_inventario_detail, name='entrada_inventario_detail'),
    path('inventario/entradas/<int:pk>/editar/', views.entrada_inventario_edit, name='entrada_inventario_edit'),
    path('inventario/entradas/<int:pk>/eliminar/', views.entrada_inventario_delete, name='entrada_inventario_delete'),
    path('inventario/entradas/<int:pk>/pesada/', views.pesada_entrada_add, name='pesada_entrada_add'),
    path('inventario/pesadas-entrada/<int:pk>/eliminar/', views.pesada_entrada_delete, name='pesada_entrada_delete'),
    # Inventario semanal (edición y nóminas — accesibles desde /inventario/entradas/)
    path('inventario/semanal/<int:pk>/editar/', views.weekly_inventory_edit, name='weekly_inventory_edit'),
    path('inventario/semanal/<int:pk>/eliminar/', views.weekly_inventory_delete, name='weekly_inventory_delete'),
    path('inventario/semanal/nominas/<int:pk>/editar/', views.nomina_edit, name='nomina_edit'),
    path('inventario/semanal/nominas/<int:pk>/eliminar/', views.nomina_delete, name='nomina_delete'),
    # Redirect antiguo módulo semanal → inventario/entradas/
    path('inventario/semanal/', RedirectView.as_view(pattern_name='entrada_inventario_list', permanent=True)),
]
