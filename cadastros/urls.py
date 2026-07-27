from django.urls import path

from . import views

app_name = "cadastros"

urlpatterns = [
    path("", views.index, name="index"),
    path("configuracao/", views.configuracao_sistema, name="configuracao"),
    path("api/cep/<str:cep>/", views.api_consulta_cep, name="api_consulta_cep"),
    path("estados/", views.estados_index, name="estados_index"),
    path("estados/<int:pk>/editar/", views.estado_update, name="estado_update"),
    path("estados/<int:pk>/excluir/", views.estado_delete, name="estado_delete"),
    path("unidades/", views.unidades_index, name="unidades_index"),
    path("unidades/nova/", views.unidades_index, name="unidade_create"),
    path("unidades/<int:pk>/editar/", views.unidade_update, name="unidade_update"),
    path("unidades/<int:pk>/excluir/", views.unidade_delete, name="unidade_delete"),
    path("cargos/", views.cargos_index, name="cargos_index"),
    path("cargos/novo/", views.cargos_index, name="cargo_create"),
    path("cargos/<int:pk>/editar/", views.cargo_update, name="cargo_update"),
    path("cargos/<int:pk>/definir-padrao/", views.cargo_set_default, name="cargo_set_default"),
    path("cargos/<int:pk>/excluir/", views.cargo_delete, name="cargo_delete"),
    path("combustiveis/", views.combustiveis_index, name="combustiveis_index"),
    path("combustiveis/novo/", views.combustiveis_index, name="combustivel_create"),
    path("combustiveis/<int:pk>/editar/", views.combustivel_update, name="combustivel_update"),
    path(
        "combustiveis/<int:pk>/definir-padrao/",
        views.combustivel_set_default,
        name="combustivel_set_default",
    ),
    path("combustiveis/<int:pk>/excluir/", views.combustivel_delete, name="combustivel_delete"),
    path("cidades/", views.cidades_index, name="cidades_index"),
    path("cidades/nova/", views.cidades_index, name="cidade_create"),
    path("cidades/exportar.csv", views.cidades_export_csv, name="cidades_export_csv"),
    path("servidores/", views.servidores_index, name="servidores_index"),
    path("servidores/novo/", views.servidor_create, name="servidor_create"),
    path("servidores/<int:pk>/editar/", views.servidor_update, name="servidor_update"),
    path("servidores/<int:pk>/excluir/", views.servidor_delete, name="servidor_delete"),
    path("viaturas/", views.viaturas_index, name="viaturas_index"),
    path("viaturas/nova/", views.viatura_create, name="viatura_create"),
    path("viaturas/<int:pk>/editar/", views.viatura_update, name="viatura_update"),
    path("viaturas/<int:pk>/excluir/", views.viatura_delete, name="viatura_delete"),
]
