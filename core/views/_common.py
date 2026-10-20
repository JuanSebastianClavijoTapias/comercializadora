from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, F, Value, DecimalField, Q
from django.db.models.functions import Coalesce
from django.db import transaction
from django.urls import reverse
from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from ..models import *
from ..forms import *
from ..services import *


def row_indices(post, prefix):
    """Índices de fila presentes en el POST para un prefijo (ej. ``kg_bruto``).

    Los índices pueden tener huecos (filas eliminadas), por eso se leen del
    POST y se ordenan en vez de asumir una numeración contigua desde 0.
    """
    pattern = re.compile(rf'{re.escape(prefix)}_(\d+)$')
    indices = set()
    for key in post:
        match = pattern.match(key)
        if match:
            indices.add(int(match.group(1)))
    return sorted(indices)
