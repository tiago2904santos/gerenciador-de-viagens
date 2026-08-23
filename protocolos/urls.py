from django.urls import path

from . import views


app_name = "protocolos"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("vincular/", views.vincular, name="vincular"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/atualizar/", views.atualizar, name="atualizar"),
    path("<int:pk>/enviar-documento/", views.enviar_documento, name="enviar_documento"),
    path("<int:pk>/concluir/", views.concluir, name="concluir"),
    path("<int:pk>/solicitar-assinatura/", views.solicitar_assinatura, name="solicitar_assinatura"),
    path("<int:pk>/tramitar/", views.tramitar, name="tramitar"),
    path("<int:pk>/movimentacoes/", views.movimentacoes, name="movimentacoes"),
    path("<int:pk>/logs/", views.logs, name="logs"),
]
