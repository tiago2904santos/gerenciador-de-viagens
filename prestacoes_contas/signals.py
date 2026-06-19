from django.db.models.signals import post_save
from django.dispatch import receiver


def _criar_prestacoes(oficio):
    from .models import PrestacaoContas

    servidores = oficio.servidores.all()
    for servidor in servidores:
        PrestacaoContas.objects.get_or_create(
            oficio=oficio,
            servidor=servidor,
            defaults={"status": PrestacaoContas.STATUS_PENDENTE},
        )


def connect_signals():
    from oficios.models import Oficio

    @receiver(post_save, sender=Oficio, dispatch_uid="prestacoes_contas.criar_ao_gerar_oficio")
    def criar_prestacoes_para_oficio_gerado(sender, instance, **kwargs):
        if instance.status not in (Oficio.STATUS_GERADO, Oficio.STATUS_FINALIZADO):
            return
        _criar_prestacoes(instance)
