from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db import transaction
from django.urls import reverse
from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from ..models import *
from ..forms import *
from ..services import *
