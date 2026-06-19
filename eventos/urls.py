from django.urls import path

from . import views


app_name = "eventos"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("api/cidades/<str:uf>/", views.api_cidades_por_uf, name="api_cidades_por_uf"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/guiado/", views.detalhe, name="guiado"),
    path("<int:pk>/guiado/etapa-<int:etapa>/", views.detalhe, name="guiado_etapa"),
    path("<int:pk>/guiado_etapa-<int:etapa>/", views.detalhe, name="guiado_etapa_legacy"),
    path("<int:pk>/guiado_termos/", views.guiado_termos, name="guiado_termos"),
    path("<int:pk>/editar/", views.editar, name="editar"),
]
