from django.core.management.base import BaseCommand

from core.models import Clasificacion
from core.services.inventario import recalcular_stock_clasificacion


class Command(BaseCommand):
    help = (
        'Recalcula el stock de cada clasificación a partir del conteo de '
        'inventario más reciente que la incluye (semántica de conteo físico). '
        'Útil una sola vez tras cambiar la lógica de stock.'
    )

    def handle(self, *args, **options):
        total = 0
        for clasificacion in Clasificacion.objects.all():
            recalcular_stock_clasificacion(clasificacion.pk)
            total += 1
        self.stdout.write(
            self.style.SUCCESS(f'Stock recalculado para {total} clasificaciones.')
        )
