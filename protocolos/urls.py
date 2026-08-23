from django.urls import path

from . import views


app_name = "protocolos"

# Fatia 1 da restauração (NOVO-20260823-014253): o ciclo de PROTOCOLAR —
# listar, criar (de ofício ou vínculo manual), detalhar, enviar documento e
# sincronizar. As ações de retorno (solicitar assinatura, tramitar, concluir,
# movimentações e logs em página própria) entram na fatia 2; os métodos
# `get_*_url` do modelo já as preveem e só resolvem quando chamados.
urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.protocolo_create, name="protocolo_create"),
    path("vincular/", views.vincular, name="vincular"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/atualizar/", views.atualizar, name="atualizar"),
    path("<int:pk>/enviar-documento/", views.enviar_documento, name="enviar_documento"),
]
