from django.http import HttpResponse


def v2_list(request):
    return HttpResponse("approval v2: list")


def v2_new(request):
    return HttpResponse("approval v2: new")


def v2_detail(request, pk: int):
    return HttpResponse(f"approval v2: detail {pk}")
from django.shortcuts import render

# Create your views here.
