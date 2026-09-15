from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import services
from .models import (
    Clasificacion, Cliente, DetalleVentaCredito, Gasto, LoteClasificacion,
    PagoVentaCredito, Producto, VentaCredito, VentaEfectivo, WeeklyInventory,
)


class BaseDataMixin:
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tester',
            password='secret123',
        )
        self.client.force_login(self.user)
        self.producto = Producto.objects.create(nombre='Mango')
        self.clasificacion = Clasificacion.objects.create(
            producto=self.producto, nombre='Extra', orden=1, stock_kg=Decimal('0'),
        )
        self.cliente = Cliente.objects.create(nombre='Cliente 1')


class WeeklySummaryTests(BaseDataMixin, TestCase):
    def test_weekly_summary_post_creates_payroll_expense(self):
        week_start = date(2026, 5, 4)
        response = self.client.post(
            f"{reverse('entrada_inventario_list')}?week={week_start.isoformat()}",
            {
                'form_type': 'nomina',
                'descripcion': 'Nómina operativa',
                'monto': '250000',
                'fecha': '2026-05-05',
            },
        )

        self.assertRedirects(response, f"{reverse('entrada_inventario_list')}?week={week_start.isoformat()}")
        nomina = Gasto.objects.get(descripcion='Nómina operativa')
        self.assertEqual(nomina.categoria.nombre, 'Nómina')
        self.assertEqual(nomina.monto, Decimal('250000'))

    def test_weekly_inventory_edit_updates_selected_week(self):
        weekly = WeeklyInventory.objects.create(
            week_start=date(2026, 5, 4),
            initial_inventory_kg=Decimal('10.00'),
        )

        response = self.client.post(
            reverse('weekly_inventory_edit', args=[weekly.pk]),
            {
                'week_start': '2026-05-04',
                'initial_inventory_kg': '125.50',
            },
        )

        self.assertRedirects(response, f"{reverse('entrada_inventario_list')}?week={weekly.week_start.isoformat()}")
        weekly.refresh_from_db()
        self.assertEqual(weekly.initial_inventory_kg, Decimal('125.50'))


class FechaHelperTests(TestCase):
    def test_parse_fecha_valida(self):
        self.assertEqual(services.parse_fecha('2026-09-14'), date(2026, 9, 14))

    def test_parse_fecha_invalida_devuelve_default(self):
        default = date(1970, 1, 1)
        self.assertEqual(services.parse_fecha('basura', default), default)
        self.assertEqual(services.parse_fecha('2026-13-45', default), default)
        self.assertEqual(services.parse_fecha(None, default), default)

    def test_normalizar_precio_cop(self):
        self.assertEqual(services.normalizar_precio_cop('2.500'), '2500')
        self.assertEqual(services.normalizar_precio_cop('1.234,50'), '1234.50')
        self.assertEqual(services.normalizar_precio_cop(''), '')

    def test_get_week_monday(self):
        self.assertEqual(services.get_week_monday(date(2026, 9, 14)), date(2026, 9, 14))
        self.assertEqual(services.get_week_monday(date(2026, 9, 20)), date(2026, 9, 14))


class GastoServiceTests(BaseDataMixin, TestCase):
    def _formset(self, filas):
        from django.forms import formset_factory
        from .forms import GastoRowForm

        formset_cls = formset_factory(GastoRowForm, extra=0)
        total = len(filas)
        data = {
            'gastos-TOTAL_FORMS': str(total),
            'gastos-INITIAL_FORMS': '0',
            'gastos-MIN_NUM_FORMS': '0',
            'gastos-MAX_NUM_FORMS': '1000',
        }
        for i, (desc, monto) in enumerate(filas):
            data[f'gastos-{i}-descripcion'] = desc
            data[f'gastos-{i}-monto'] = monto
        return formset_cls(data, prefix='gastos')

    def test_registrar_gastos_crea_validos_e_ignora_vacios(self):
        fecha = date(2026, 9, 14)
        formset = self._formset([('Flete', '1.000'), ('Empaque', '2.500'), ('', '')])
        self.assertTrue(formset.is_valid())

        creados = services.registrar_gastos(formset, fecha)

        self.assertEqual(creados, 2)
        self.assertEqual(Gasto.objects.filter(fecha=fecha).count(), 2)
        self.assertEqual(Gasto.objects.get(descripcion='Flete').monto, Decimal('1000'))

    def test_resumen_gastos_del_dia(self):
        fecha = date(2026, 9, 14)
        Gasto.objects.create(descripcion='A', monto=Decimal('1000'), fecha=fecha)
        Gasto.objects.create(descripcion='B', monto=Decimal('3000'), fecha=fecha)

        r = services.resumen_gastos_del_dia(fecha)

        self.assertEqual(r.cantidad, 2)
        self.assertEqual(r.total, Decimal('4000'))
        self.assertEqual(r.promedio, Decimal('2000'))
        self.assertEqual(r.maximo, Decimal('3000'))


class VentaCreditoTotalsTests(BaseDataMixin, TestCase):
    def test_annotations_evitan_n_plus_1(self):
        venta = VentaCredito.objects.create(cliente=self.cliente, fecha=date(2026, 9, 14))
        DetalleVentaCredito.objects.create(
            venta=venta, clasificacion=self.clasificacion,
            kg_vendido=Decimal('10'), precio_por_kg=Decimal('1500'),
        )
        DetalleVentaCredito.objects.create(
            venta=venta, clasificacion=self.clasificacion,
            kg_vendido=Decimal('5'), precio_por_kg=Decimal('1500'),
        )
        PagoVentaCredito.objects.create(
            venta=venta, monto=Decimal('5000'), medio_pago='efectivo', fecha=date(2026, 9, 14),
        )

        anotada = services.ventas_credito_with_totals().get(pk=venta.pk)

        self.assertEqual(anotada.total, Decimal('22500'))
        self.assertEqual(anotada.total_pagado, Decimal('5000'))
        self.assertEqual(anotada.total_kg, Decimal('15'))
        self.assertEqual(anotada.saldo_pendiente, Decimal('17500'))

    def test_resumen_fecha(self):
        venta = VentaCredito.objects.create(cliente=self.cliente, fecha=date(2026, 9, 14))
        DetalleVentaCredito.objects.create(
            venta=venta, clasificacion=self.clasificacion,
            kg_vendido=Decimal('10'), precio_por_kg=Decimal('1000'),
        )

        r = services.resumen_fecha(date(2026, 9, 14))

        self.assertEqual(r['ventas_total'], Decimal('10000'))
        self.assertEqual(r['kg_total'], Decimal('10'))
        self.assertEqual(r['por_cobrar'], Decimal('10000'))
        self.assertFalse(r['manual']['efectivo'])


class StockSignalTests(BaseDataMixin, TestCase):
    def test_lote_suma_stock_y_detalle_credito_resta(self):
        self.assertEqual(self.clasificacion.stock_kg, Decimal('0'))

        lote = LoteClasificacion.objects.create(
            viaje=self._viaje(), clasificacion=self.clasificacion, kg_neto=Decimal('100'),
        )
        self.clasificacion.refresh_from_db()
        self.assertEqual(self.clasificacion.stock_kg, Decimal('100'))

        venta = VentaCredito.objects.create(cliente=self.cliente, fecha=date(2026, 9, 14))
        DetalleVentaCredito.objects.create(
            venta=venta, clasificacion=self.clasificacion,
            kg_vendido=Decimal('30'), precio_por_kg=Decimal('1000'),
        )
        self.clasificacion.refresh_from_db()
        self.assertEqual(self.clasificacion.stock_kg, Decimal('70'))

        lote.delete()
        self.clasificacion.refresh_from_db()
        self.assertEqual(self.clasificacion.stock_kg, Decimal('0'))

    def _viaje(self):
        from .models import Proveedor, Viaje
        proveedor = Proveedor.objects.create(nombre='Prov')
        return Viaje.objects.create(proveedor=proveedor, producto=self.producto, fecha=date(2026, 9, 14))


class ViajeTotalsTests(BaseDataMixin, TestCase):
    def test_anotaciones_equivalen_al_calculo_por_consultas(self):
        from .models import DesechoInventario, PagoProveedor, PesadaViaje, Proveedor, Viaje

        proveedor = Proveedor.objects.create(nombre='Prov')
        viaje = Viaje.objects.create(
            proveedor=proveedor, producto=self.producto, fecha=date(2026, 9, 14),
            precio_total_acordado=Decimal('1000'),
        )
        PesadaViaje.objects.create(
            viaje=viaje, clasificacion=self.clasificacion,
            num_canastillas_negras=0, num_canastillas_colores=0,
            kg_bruto=Decimal('100'), kg_podridos=Decimal('10'),
        )
        DesechoInventario.objects.create(
            fecha=date(2026, 9, 14), clasificacion=self.clasificacion,
            viaje=viaje, kg=Decimal('5'),
        )
        PagoProveedor.objects.create(
            viaje=viaje, monto=Decimal('20000'), medio_pago='efectivo', fecha=date(2026, 9, 14),
        )

        plano = Viaje.objects.get(pk=viaje.pk)
        anotado = services.viajes_with_totals(Viaje.objects.filter(pk=viaje.pk)).get()

        self.assertEqual(anotado.total_kg_neto, plano.total_kg_neto)
        self.assertEqual(anotado.kg_neto_despues_podrido, plano.kg_neto_despues_podrido)
        self.assertEqual(anotado.total_valor, plano.total_valor)
        self.assertEqual(anotado.total_pagado, plano.total_pagado)
        self.assertEqual(anotado.saldo_pendiente, plano.saldo_pendiente)


class GastoListViewTests(BaseDataMixin, TestCase):
    def test_lista_filtra_por_fecha(self):
        Gasto.objects.create(descripcion='Hoy', monto=Decimal('100'), fecha=date(2026, 9, 14))
        Gasto.objects.create(descripcion='Ayer', monto=Decimal('200'), fecha=date(2026, 9, 13))

        response = self.client.get(reverse('gasto_list'), {'fecha': '2026-09-14'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hoy')
        self.assertNotContains(response, 'Ayer')

    def test_fecha_invalida_cae_a_hoy(self):
        response = self.client.get(reverse('gasto_list'), {'fecha': 'basura'})
        self.assertEqual(response.status_code, 200)

    def test_post_crea_varios_gastos(self):
        response = self.client.post(reverse('gasto_list'), {
            'fecha': '2026-09-14',
            'gastos-TOTAL_FORMS': '3', 'gastos-INITIAL_FORMS': '0',
            'gastos-MIN_NUM_FORMS': '0', 'gastos-MAX_NUM_FORMS': '1000',
            'gastos-0-descripcion': 'A', 'gastos-0-monto': '1.000',
            'gastos-1-descripcion': 'B', 'gastos-1-monto': '2.000',
            'gastos-2-descripcion': '', 'gastos-2-monto': '',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Gasto.objects.filter(fecha=date(2026, 9, 14)).count(), 2)


class ReporteDiarioTests(BaseDataMixin, TestCase):
    def test_muestra_total_vendido(self):
        venta = VentaCredito.objects.create(cliente=self.cliente, fecha=date(2026, 9, 14))
        DetalleVentaCredito.objects.create(
            venta=venta, clasificacion=self.clasificacion,
            kg_vendido=Decimal('10'), precio_por_kg=Decimal('1000'),
        )
        VentaEfectivo.objects.create(fecha=date(2026, 9, 14), total_dia=Decimal('500'), kg_vendido=Decimal('5'))

        response = self.client.get(reverse('reporte_diario'), {'fecha': '2026-09-14'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total Vendido')
        self.assertEqual(response.context['total_kg_vendido'], Decimal('15'))
        self.assertEqual(response.context['total_ventas'], Decimal('10500'))
