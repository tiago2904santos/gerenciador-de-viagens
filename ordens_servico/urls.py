from django.urls import path

from . import views


app_name = "ordens_servico"

urlpatterns = [
    path("", views.index, name="index"),
    path("nova/", views.nova, name="nova"),
    path("<int:pk>/editar/", views.editar, name="editar"),
]
