from django.db.models.signals import m2m_changed
from django.db.models.signals import post_save
from django.dispatch import receiver


def _sincronizar_prestacao_servidores(oficio):
    """Reconcilia os ``PrestacaoServidor`` do ofício com a equipe atual.

    A prestação (uma por ofício) passa a refletir exatamente ``oficio.servidores``:
    cria uma linha para cada servidor que ainda não tem e — crucialmente — remove
    as linhas de servidores que saíram do ofício. Sem essa remoção, servidores
    apenas "semeados" no wizard de um novo ofício (que herda a equipe do ofício
    anterior do mesmo evento) e depois retirados continuariam aparecendo na
    prestação, misturando equipes entre ofícios.
    """
    from .models import PrestacaoContas
    from .models import PrestacaoServidor

    if oficio.cancelado:
        return

    prestacao, _ = PrestacaoContas.objects.get_or_create(
        oficio=oficio,
        defaults={"status": PrestacaoContas.STATUS_PENDENTE},
    )

    ids_atuais = set(oficio.servidores.values_list("pk", flat=True))

    # Remove quem não faz mais parte do ofício (cascata apaga os dados individuais
    # daquele servidor: solicitação, comprovante e assinatura do RT).
    prestacao.servidores_prestacao.exclude(servidor_id__in=ids_atuais).delete()

    # Garante uma linha para cada servidor atual (mantém as existentes e seus dados).
    for servidor_id in ids_atuais:
        PrestacaoServidor.objects.get_or_create(
            prestacao=prestacao,
            servidor_id=servidor_id,
        )


def connect_signals():
    from oficios.models import Oficio

    @receiver(post_save, sender=Oficio, dispatch_uid="prestacoes_contas.criar_ao_gerar_oficio", weak=False)
    def criar_prestacoes_para_oficio_gerado(sender, instance, **kwargs):
        _sincronizar_prestacao_servidores(instance)

    @receiver(
        m2m_changed,
        sender=Oficio.servidores.through,
        dispatch_uid="prestacoes_contas.sincronizar_ao_alterar_servidores",
        weak=False,
    )
    def sincronizar_prestacoes_ao_alterar_servidores(sender, instance, action, **kwargs):
        # Reconcilia após qualquer alteração efetiva da equipe (adição, remoção ou
        # limpeza). ``.set()`` do ModelForm dispara post_remove e/ou post_add.
        if action in ("post_add", "post_remove", "post_clear"):
            _sincronizar_prestacao_servidores(instance)
