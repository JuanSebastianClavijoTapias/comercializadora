from django import forms
from .models import *

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'telefono', 'direccion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'direccion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'tiene_descuento_gobierno', 'porcentaje_descuento', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tiene_descuento_gobierno': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'porcentaje_descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ClasificacionForm(forms.ModelForm):
    class Meta:
        model = Clasificacion
        fields = ['nombre', 'orden', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CategoriaGastoForm(forms.ModelForm):
    class Meta:
        model = CategoriaGasto
        fields = ['nombre']
        widgets = {'nombre': forms.TextInput(attrs={'class': 'form-control'})}

class ViajeForm(forms.ModelForm):
    """Formulario simplificado para registrar nuevo viaje - solo datos básicos"""
    class Meta:
        model = Viaje
        fields = ['proveedor', 'producto', 'fecha', 'kg_bruto']
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'kg_bruto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class ViajeDetallesForm(forms.ModelForm):
    """Formulario para editar detalles del viaje después de su creación"""
    class Meta:
        model = Viaje
        fields = ['kg_podridos', 'cantidad_canastillas_negras', 'cantidad_canastillas_colores', 'precio_total_acordado']
        widgets = {
            'kg_podridos': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cantidad_canastillas_negras': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'cantidad_canastillas_colores': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'precio_total_acordado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class LoteClasificacionForm(forms.ModelForm):
    class Meta:
        model = LoteClasificacion
        fields = ['clasificacion', 'kg_neto']
        widgets = {
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'kg_neto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class PagoProveedorForm(forms.ModelForm):
    class Meta:
        model = PagoProveedor
        fields = ['monto', 'medio_pago', 'fecha', 'observaciones']
        widgets = {
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'medio_pago': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = ['categoria', 'descripcion', 'monto', 'fecha']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

class VentaEfectivoForm(forms.ModelForm):
    class Meta:
        model = VentaEfectivo
        fields = ['fecha', 'producto', 'cliente', 'clasificacion', 'kg_vendido', 'precio_por_kg', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'kg_vendido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_kg_vendido'}),
            'precio_por_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_precio_por_kg'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Asegurar que el queryset de clasificación muestre el stock en las opciones
        self.fields['clasificacion'].queryset = Clasificacion.objects.filter(
            activo=True
        ).order_by('producto', 'orden')

class VentaCreditoForm(forms.ModelForm):
    clasificacion = forms.ModelChoiceField(
        queryset=Clasificacion.objects.filter(activo=True).order_by('producto', 'orden'), 
        required=True, 
        label='Clasificación', 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    kg_vendido = forms.DecimalField(max_digits=10, decimal_places=2, required=True, label='Kg vendido', widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_kg_vendido_c'}))
    precio_por_kg = forms.DecimalField(max_digits=10, decimal_places=2, required=True, label='Precio por kg', widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_precio_por_kg_c'}))

    class Meta:
        model = VentaCredito
        fields = ['fecha', 'fecha_vencimiento', 'cliente', 'producto', 'observaciones']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class DetalleVentaCreditoForm(forms.ModelForm):
    class Meta:
        model = DetalleVentaCredito
        fields = ['clasificacion', 'kg_vendido', 'precio_por_kg']
        widgets = {
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'kg_vendido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'precio_por_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class PagoVentaCreditoForm(forms.ModelForm):
    class Meta:
        model = PagoVentaCredito
        fields = ['monto', 'medio_pago', 'fecha', 'observaciones']
        widgets = {
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'medio_pago': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class LiquidacionInventarioForm(forms.ModelForm):
    class Meta:
        model = LiquidacionInventario
        fields = ['fecha_inicio', 'fecha_fin', 'observaciones']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
