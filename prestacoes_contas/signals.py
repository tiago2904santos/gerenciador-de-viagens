from django.db.models.signals import m2m_changed
from django.db.models.signals import post_save
from django.dispatch import receiver


def _criar_prestacoes(oficio, servidor_ids=None):
    from .models import PrestacaoContas
    from .models import PrestacaoServidor

    if oficio.cancelado:
        return

    prestacao, _ = PrestacaoContas.objects.get_or_create(
        oficio=oficio,
        defaults={"status": PrestacaoContas.STATUS_PENDENTE},
    )

    servidores = oficio.servidores.all()
    if servidor_ids is not None:
        servidores = servidores.filter(pk__in=servidor_ids)

    for servidor in servidores:
        PrestacaoServidor.objects.get_or_create(
            prestacao=prestacao,
            servidor=servidor,
        )


def connect_signals():
    from oficios.models import Oficio

    @receiver(post_save, sender=Oficio, dispatch_uid="prestacoes_contas.criar_ao_gerar_oficio", weak=False)
    def criar_prestacoes_para_oficio_gerado(sender, instance, **kwargs):
        _criar_prestacoes(instance)

    @receiver(
        m2m_changed,
        sender=Oficio.servidores.through,
        dispatch_uid="prestacoes_contas.criar_ao_adicionar_servidores",
        weak=False,
    )
    def criar_prestacoes_para_servidores_adicionados(sender, instance, action, pk_set, **kwargs):
        if action != "post_add" or not pk_set:
            return
        _criar_prestacoes(instance, servidor_ids=pk_set)
