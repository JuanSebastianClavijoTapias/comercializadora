from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Gasto, WeeklyInventory


class WeeklySummaryTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='tester',
			password='secret123',
		)
		self.client.force_login(self.user)

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
