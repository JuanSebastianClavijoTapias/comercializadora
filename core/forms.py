from django import forms
from .models import *


class COPInputNormalizationMixin:
    cop_fields = ()

    def __init__(self, *args, **kwargs):
        data = kwargs.get('data')
        if data is not None:
            data = data.copy()
            for field_name in self.cop_fields:
                value = data.get(field_name)
                if value not in (None, ''):
                    data[field_name] = str(value).replace('.', '').strip()
            kwargs['data'] = data
        super().__init__(*args, **kwargs)

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
        fields = ['nombre', 'orden', 'stock_kg', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
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
        fields = ['proveedor', 'producto', 'fecha', 'observaciones']
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones opcionales...'}),
        }

class ViajeDetallesForm(forms.ModelForm):
    """Formulario para editar detalles del viaje después de su creación"""
    class Meta:
        model = Viaje
        fields = ['kg_podridos']
        widgets = {
            'kg_podridos': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class PesadaViajeForm(forms.ModelForm):
    class Meta:
        model = PesadaViaje
        fields = ['num_canastillas_negras', 'num_canastillas_colores', 'kg_bruto']
        widgets = {
            'num_canastillas_negras': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '0'}),
            'num_canastillas_colores': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '0'}),
            'kg_bruto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 180.00'}),
        }

class LoteClasificacionForm(forms.ModelForm):
    class Meta:
        model = LoteClasificacion
        fields = ['clasificacion', 'kg_neto']
        widgets = {
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'kg_neto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class PagoProveedorForm(COPInputNormalizationMixin, forms.ModelForm):
    cop_fields = ('monto',)

    class Meta:
        model = PagoProveedor
        fields = ['monto', 'medio_pago', 'fecha', 'observaciones']
        widgets = {
            'monto': forms.TextInput(attrs={'class': 'form-control price-cop', 'inputmode': 'numeric', 'autocomplete': 'off', 'step': '0.01', 'id': 'input_monto_proveedor'}),
            'medio_pago': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class GastoForm(COPInputNormalizationMixin, forms.ModelForm):
    cop_fields = ('monto',)

    class Meta:
        model = Gasto
        fields = ['categoria', 'descripcion', 'monto', 'fecha']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'monto': forms.TextInput(attrs={'class': 'form-control price-cop', 'inputmode': 'numeric', 'autocomplete': 'off'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

class NominaForm(COPInputNormalizationMixin, forms.ModelForm):
    cop_fields = ('monto',)

    class Meta:
        model = Gasto
        fields = ['descripcion', 'monto', 'fecha']
        widgets = {
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Nómina operativa semana 01/05'}),
            'monto': forms.TextInput(attrs={'class': 'form-control price-cop', 'inputmode': 'numeric', 'autocomplete': 'off'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

class WeeklyInventoryForm(forms.ModelForm):
    class Meta:
        model = WeeklyInventory
        fields = ['week_start', 'initial_inventory_kg']
        widgets = {
            'week_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'initial_inventory_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

class VentaEfectivoForm(forms.ModelForm):
    class Meta:
        model = VentaEfectivo
        fields = ['fecha', 'cliente', 'descripcion', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción opcional'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class DetalleVentaEfectivoForm(COPInputNormalizationMixin, forms.ModelForm):
    cop_fields = ('precio_por_kg',)

    class Meta:
        model = DetalleVentaEfectivo
        fields = ['clasificacion', 'kg_vendido', 'precio_por_kg']
        widgets = {
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'kg_vendido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Kg a vender'}),
            'precio_por_kg': forms.TextInput(attrs={'class': 'form-control price-cop', 'inputmode': 'numeric', 'autocomplete': 'off', 'placeholder': 'Precio por kg'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['clasificacion'].queryset = Clasificacion.objects.filter(
            activo=True
        ).order_by('producto', 'orden')

class VentaCreditoForm(forms.ModelForm):
    class Meta:
        model = VentaCredito
        fields = ['fecha', 'fecha_vencimiento', 'cliente', 'observaciones']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class DetalleVentaCreditoForm(COPInputNormalizationMixin, forms.ModelForm):
    cop_fields = ('precio_por_kg',)

    class Meta:
        model = DetalleVentaCredito
        fields = ['clasificacion', 'kg_vendido', 'precio_por_kg']
        widgets = {
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'kg_vendido': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'precio_por_kg': forms.TextInput(attrs={'class': 'form-control price-cop', 'inputmode': 'numeric', 'autocomplete': 'off'}),
        }

class PagoVentaCreditoForm(COPInputNormalizationMixin, forms.ModelForm):
    cop_fields = ('monto',)

    class Meta:
        model = PagoVentaCredito
        fields = ['monto', 'medio_pago', 'fecha', 'observaciones']
        widgets = {
            'monto': forms.TextInput(attrs={'class': 'form-control price-cop', 'inputmode': 'numeric', 'autocomplete': 'off'}),
            'medio_pago': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
