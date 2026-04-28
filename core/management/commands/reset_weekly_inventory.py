from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.models import WeeklyInventory

class Command(BaseCommand):
    help = 'Reset weekly inventory: copies previous week total as current week initial inventory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Fecha específica (YYYY-MM-DD). Por defecto usa hoy.',
        )

    def handle(self, *args, **options):
        # Obtener la fecha
        if options['date']:
            try:
                target_date = date.fromisoformat(options['date'])
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"Formato de fecha inválido: {options['date']}. Use YYYY-MM-DD")
                )
                return
        else:
            target_date = date.today()

        # Calcular lunes de la semana actual
        lunes = target_date - timedelta(days=target_date.weekday())
        
        # Validar que sea lunes
        if lunes != target_date and target_date.weekday() != 0:
            # Si no es lunes, usar el lunes de esa semana
            lunes = target_date - timedelta(days=target_date.weekday())

        self.stdout.write(f"Reseteando inventario para semana que comienza: {lunes}")

        # Obtener o crear registro de esta semana
        weekly_current, created = WeeklyInventory.objects.get_or_create(
            week_start=lunes,
            defaults={'initial_inventory_kg': Decimal('0')}
        )

        # Obtener la semana anterior
        prev_lunes = lunes - timedelta(days=7)
        
        try:
            weekly_prev = WeeklyInventory.objects.get(week_start=prev_lunes)
            prev_total = weekly_prev.total_inventory_kg
            
            # Copiar total anterior como inicial de esta semana
            weekly_current.initial_inventory_kg = prev_total
            weekly_current.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Inventario resetizado exitosamente:\n"
                    f"   Semana anterior (finalizó): {prev_total:.2f} kg\n"
                    f"   Inventario inicial esta semana: {weekly_current.initial_inventory_kg:.2f} kg\n"
                    f"   Inventario total esta semana: {weekly_current.total_inventory_kg:.2f} kg"
                )
            )
        except WeeklyInventory.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  No se encontró registro de la semana anterior ({prev_lunes}).\n"
                    f"   Se mantiene el inventario inicial actual: {weekly_current.initial_inventory_kg:.2f} kg"
                )
            )
