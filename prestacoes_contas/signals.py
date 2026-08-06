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

    ``DB-06``: "remover" aqui deixou de significar ``DELETE``. Quem sai levando
    trabalho junto — comprovante de saque, assinatura do RT, número da
    solicitação — é apenas marcado (``PrestacaoServidor.sair_da_equipe``), some
    das telas e volta inteiro se o servidor voltar para a equipe. Quem não tem
    nada coletado continua sendo apagado, senão a prestação voltaria a exibir a
    equipe de outro ofício, que é o defeito que este sinal resolve.
    """
    from .models import PrestacaoContas
    from .models import PrestacaoServidor

    if oficio.cancelado:
        return

    # `BE-09`: `all_objects` — a prestação pertence à área do **ofício**, na linha
    # de baixo e no `defaults`. Com `objects` e área do ofício diferente da ativa,
    # o `get` não acharia a prestação existente e o `create` duplicaria — este
    # signal roda a cada mudança de equipe do ofício.
    prestacao, _ = PrestacaoContas.all_objects.get_or_create(
        oficio=oficio,
        defaults={"area": oficio.area},
    )
    if prestacao.area_id is None and oficio.area_id:
        prestacao.area = oficio.area
        prestacao.save(update_fields=["area", "atualizado_em"])

    ids_atuais = set(oficio.servidores.values_list("pk", flat=True))

    # Tira da equipe corrente quem não faz mais parte do ofício. `DB-06`: o
    # `.delete()` que estava aqui levava junto, por cascata, o comprovante de
    # saque e a assinatura eletrônica do RT — e deixava o arquivo órfão no disco.
    # `todos` porque as já marcadas precisam ser vistas para não serem remarcadas.
    saindo = PrestacaoServidor.todos.filter(
        prestacao=prestacao, removida_em__isnull=True,
    ).exclude(servidor_id__in=ids_atuais)
    for servidor_prestacao in saindo:
        servidor_prestacao.sair_da_equipe()

    # Garante uma linha para cada servidor atual (mantém as existentes e seus dados).
    for servidor_id in ids_atuais:
        # `DB-06`: `todos` é obrigatório aqui. Com `objects`, o `get` não enxerga a
        # linha de um servidor que já saiu da equipe uma vez, o `create` roda e
        # `unique_servidor_por_prestacao` derruba a edição de equipe com 500.
        servidor_prestacao, criada = PrestacaoServidor.todos.get_or_create(
            prestacao=prestacao,
            servidor_id=servidor_id,
        )
        if not criada:
            servidor_prestacao.voltar_para_equipe()


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
