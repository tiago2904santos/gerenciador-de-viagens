"""Popula o sistema com dados de teste para exercitar a organização no Drive.

Cria 10 ofícios completos (2 servidores cada), 10 planos de trabalho, 10 ordens
de serviço, termos, justificativas e 5 convites — distribuídos em 4 eventos + o
resto avulso — e GERA todos os documentos, o que dispara a organização no Drive.

Modos::

    manage.py seed_drive_demo --preview   # cria os dados mas NÃO toca no Drive;
                                          # imprime a árvore que SERIA criada.
    manage.py seed_drive_demo             # cria + gera + envia ao Drive real
                                          # (respeita GOOGLE_DRIVE_MODO=ativo).
    manage.py seed_drive_demo --limpar    # remove os dados demo (não apaga o que
                                          # já foi para o Drive).

Tudo é marcado com ``[DRIVE DEMO]`` (ofícios/eventos) e ``sufixo_numero=DEMO``
(planos) para permitir limpeza posterior.
"""

from __future__ import annotations

from datetime import time as dtime
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

TAG = "[DRIVE DEMO]"
PLANO_TAG = "DEMO"
N_OFICIOS = 10
N_EVENTOS = 4
N_CONVITES = 5


def _pdf_generico(titulo: str) -> bytes:
    """Um PDF de 1 página (para convites). Usa reportlab; cai para bytes mínimos."""
    try:
        import io

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(80, 750, titulo)
        c.setFont("Helvetica", 12)
        c.drawString(80, 710, "Documento genérico de teste (seed_drive_demo).")
        c.showPage()
        c.save()
        return buf.getvalue()
    except Exception:
        return (
            b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF"
        )


class Command(BaseCommand):
    help = (
        "Cria 10 ofícios (2 servidores cada), 10 planos, 10 OS, termos, "
        "justificativas e 5 convites em 4 eventos + avulsos, e gera os documentos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Não envia ao Drive; imprime a árvore planejada (planejar_*).",
        )
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove os dados demo criados por este comando.",
        )

    def handle(self, *args, **options):
        if options["limpar"]:
            self._limpar()
            return

        preview: bool = options["preview"]
        if preview:
            self._forcar_mock()
            self.stdout.write(self.style.NOTICE("PREVIEW: Drive não será tocado."))

        with transaction.atomic():
            dados = self._criar_dominio()

        # Geração dos documentos (fora da transação para que cada push ao Drive
        # aconteça com o objeto já commitado).
        self._gerar_documentos(dados)

        if preview:
            self._imprimir_arvore(dados)
        self.stdout.write(self.style.SUCCESS("Concluído."))

    # ------------------------------------------------------------------ setup
    def _forcar_mock(self):
        from django.conf import settings

        from integracoes.google_drive import services

        settings.GOOGLE_DRIVE = {**settings.GOOGLE_DRIVE, "MODO": "mock", "UPLOAD_EM_MOCK": False}
        services._reset_client()

    def _cadastros_base(self):
        from cadastros.models import ConfiguracaoSistema, Servidor, Viatura

        cfg = ConfiguracaoSistema.get_singleton()
        sede = cfg.cidade_sede_padrao
        if sede is None:
            raise SystemExit("Configure a cidade sede padrão antes de rodar o seed.")

        servidores = list(
            Servidor.objects.filter(cargo__isnull=False).order_by("pk")[: N_OFICIOS * 2]
        )
        if len(servidores) < N_OFICIOS * 2:
            raise SystemExit(
                f"Preciso de {N_OFICIOS * 2} servidores com cargo; achei {len(servidores)}."
            )
        viaturas = list(Viatura.objects.all()[:6])
        if not viaturas:
            raise SystemExit("Nenhuma viatura cadastrada.")

        from cadastros.models import Cidade

        destinos = list(
            Cidade.objects.exclude(pk=sede.pk).select_related("estado").order_by("nome")[:N_OFICIOS]
        )
        return cfg, sede, servidores, viaturas, destinos

    # --------------------------------------------------------------- domínio
    def _criar_dominio(self) -> dict:
        from eventos.models import Evento, TipoEvento

        cfg, sede, servidores, viaturas, destinos = self._cadastros_base()

        tipos = list(TipoEvento.objects.filter(ativo=True)[:N_EVENTOS]) or list(
            TipoEvento.objects.all()[:N_EVENTOS]
        )
        hoje = timezone.localdate()

        # 4 eventos
        eventos = []
        for i in range(N_EVENTOS):
            destino = destinos[i % len(destinos)]
            di = hoje + timedelta(days=20 + i * 3)
            ev = Evento.objects.create(
                titulo=f"{TAG} Evento {i + 1:02d}",
                destino_cidade=destino.nome,
                destino_uf=destino.uf,
                data_inicio=di,
                data_fim=di + timedelta(days=1),
                status=Evento.STATUS_EM_PREPARACAO,
            )
            if tipos:
                ev.tipos.add(tipos[i % len(tipos)])
            eventos.append(ev)

        # ofício i vai para evento (i//2) enquanto houver evento; resto avulso.
        # -> eventos 0..3 recebem ofícios 0..5 (2,2,1,1); ofícios 6..9 avulsos.
        mapa_evento = {0: eventos[0], 1: eventos[0], 2: eventos[1], 3: eventos[1],
                       4: eventos[2], 5: eventos[3]}

        oficios = []
        for i in range(N_OFICIOS):
            evento = mapa_evento.get(i)
            destino = destinos[i % len(destinos)]
            par = servidores[i * 2 : i * 2 + 2]
            oficio = self._criar_oficio(cfg, sede, destino, par, viaturas[i % len(viaturas)], evento, i)
            oficios.append(oficio)

        # 10 planos (um por ofício); segue o evento do ofício quando houver.
        planos = []
        for i, oficio in enumerate(oficios):
            par = servidores[i * 2 : i * 2 + 2]
            planos.append(
                self._criar_plano(oficio.evento, destinos[i % len(destinos)], par, i)
            )

        # 5 convites como anexos de evento (genérico).
        convites = self._criar_convites(eventos)

        self.stdout.write(
            f"Domínio: {len(eventos)} eventos, {len(oficios)} ofícios, "
            f"{len(planos)} planos, {len(convites)} convites."
        )
        return {"eventos": eventos, "oficios": oficios, "planos": planos}

    def _criar_oficio(self, cfg, sede, destino, par, viatura, evento, i):
        from oficios.models import Oficio
        from justificativas.models import Justificativa
        from justificativas.services import get_or_create_justificativa_oficio

        roteiro = self._criar_roteiro(sede, destino, i)
        ano = timezone.localdate().year
        numero = Oficio.get_next_available_numero(ano)

        oficio = Oficio.objects.create(
            numero=numero,
            ano=ano,
            protocolo=f"{15000000 + i}",
            assunto=f"{TAG} Ofício {i + 1:02d} — deslocamento institucional",
            motivo="Deslocamento para atividade institucional de teste.",
            status=Oficio.STATUS_GERADO,
            roteiro=roteiro,
            solicitante=par[0].unidade,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
            viatura=viatura,
            motorista=par[0],
            motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
            evento=evento,
        )
        oficio.servidores.set(par)
        oficio.servidores_termo_autorizacao.set(par)

        j = get_or_create_justificativa_oficio(oficio)
        j.texto = f"Justificativa de teste do ofício demo {i + 1}."
        j.status = Justificativa.STATUS_FINALIZADA
        j.save()
        return oficio

    def _criar_roteiro(self, sede, destino, i):
        from roteiros.models import Roteiro, RoteiroDestino, RoteiroTrecho

        pr = sede.estado
        saida_ida = timezone.now().replace(microsecond=0) + timedelta(days=14 + i)
        cheg_ida = saida_ida + timedelta(hours=5)
        saida_volta = cheg_ida + timedelta(days=1)
        cheg_volta = saida_volta + timedelta(hours=5)

        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
            origem_estado=pr,
            origem_cidade=sede,
            saida_dt=saida_ida,
            chegada_dt=cheg_volta,
            retorno_saida_dt=saida_volta,
            retorno_chegada_dt=cheg_volta,
            quantidade_diarias="2",
            valor_diarias=Decimal("150.00"),
            valor_diarias_extenso="CENTO E CINQUENTA REAIS",
            observacoes=f"{TAG} roteiro {i + 1}",
            rota_status=Roteiro.ROTA_STATUS_MANUAL,
            rota_fonte=Roteiro.ROTA_FONTE_MANUAL,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=destino.estado, cidade=destino, ordem=1
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro, ordem=1, tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=pr, origem_cidade=sede,
            destino_estado=destino.estado, destino_cidade=destino,
            saida_dt=saida_ida, chegada_dt=cheg_ida,
            distancia_km=Decimal("200.00"), duracao_estimada_min=300,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro, ordem=2, tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=destino.estado, origem_cidade=destino,
            destino_estado=pr, destino_cidade=sede,
            saida_dt=saida_volta, chegada_dt=cheg_volta,
            distancia_km=Decimal("200.00"), duracao_estimada_min=300,
        )
        return roteiro

    def _criar_plano(self, evento, destino, servidores, i):
        """Cria o plano E completa tudo que ``build_plano_docxtpl_context`` exige:

        coordenadores, saída/chegada da sede, efetivo, diárias e atividades/metas/
        recursos. Sem isso o rascunho (``criar_plano_rascunho``) fica praticamente
        vazio — só numeração, status e (quando há evento) destino/data.
        """
        from cadastros.models import Cargo
        from planos_trabalho.models import AtividadePlanoTrabalho, EfetivoPlano
        from planos_trabalho.services import (
            atualizar_snapshot_diarias,
            criar_plano_rascunho,
            sincronizar_atividades,
            sincronizar_textos_padrao,
        )

        plano = criar_plano_rascunho(evento)
        plano.sufixo_numero = PLANO_TAG

        if not plano.destino_cidade_id:
            plano.destino_cidade = destino
            plano.destino_estado = destino.estado
        if not plano.data_evento_inicio:
            hoje = timezone.localdate()
            plano.data_evento_inicio = hoje + timedelta(days=30 + i)
            plano.data_evento_fim = plano.data_evento_inicio + timedelta(days=1)
        if not plano.programa_display:
            plano.programa_outros = f"{TAG} Programa demo {i + 1}"

        # Coordenadores (servidores reais do próprio ofício).
        if not plano.coordenador_adm_id and servidores:
            plano.coordenador_adm = servidores[0]
        if not plano.coordenador_op_id and len(servidores) > 1:
            plano.coordenador_op = servidores[1]

        # Deslocamento sede→destino (saída véspera, chegada no fim do evento).
        plano.saida_sede_data = plano.data_evento_inicio - timedelta(days=1)
        plano.saida_sede_hora = plano.saida_sede_hora or dtime(6, 0)
        plano.chegada_sede_data = plano.data_evento_fim
        plano.chegada_sede_hora = plano.chegada_sede_hora or dtime(20, 0)

        plano.save()

        # Efetivo (obrigatório para calcular diárias: total_efetivo > 0).
        cargos = list(Cargo.objects.all()[:2]) or None
        if cargos:
            for idx, cargo in enumerate(cargos):
                EfetivoPlano.objects.create(
                    plano=plano,
                    cargo=cargo,
                    unidade=servidores[idx].unidade if idx < len(servidores) else None,
                    quantidade=1,
                )

        # Atividades/metas/recursos (catálogo gerenciável).
        atividades = list(AtividadePlanoTrabalho.objects.filter(ativo=True)[:3])
        if atividades:
            plano.atividades_selecionadas.set(atividades)
            sincronizar_atividades(plano, save=True)

        # Diárias calculadas pelo motor real (precisa efetivo + saída/chegada + destino).
        atualizar_snapshot_diarias(plano, save=True)

        # Contextualização/coordenação/considerações finais (textos padrão).
        alterados = sincronizar_textos_padrao(plano)
        if alterados:
            plano.save(update_fields=[*alterados, "updated_at"])
        return plano

    def _criar_convites(self, eventos):
        from eventos.models import EventoAnexo

        convites = []
        for k in range(N_CONVITES):
            evento = eventos[k % len(eventos)]
            anexo = EventoAnexo(
                evento=evento,
                tipo=EventoAnexo.TIPO_CONVITE,
                titulo=f"{TAG} Convite {k + 1}",
            )
            anexo.arquivo.save(
                f"convite_demo_{k + 1}.pdf",
                ContentFile(_pdf_generico(f"Convite {k + 1}")),
                save=False,
            )
            anexo.save()  # dispara o signal de organização
            convites.append(anexo)
        return convites

    # ------------------------------------------------------------- documentos
    def _gerar_documentos(self, dados):
        from documentos.services.types import DocumentoFormato
        from oficios.services import (
            gerar_resposta_documento_oficio,
            gerar_resposta_justificativa_documento,
        )
        from ordens_servico.services import gerar_resposta_ordem_servico_documento
        from planos_trabalho.services import gerar_plano_documento
        from termos.services import gerar_termo_lote

        pdf = DocumentoFormato.PDF
        ok, err = 0, 0

        def _try(desc, fn):
            nonlocal ok, err
            try:
                fn()
                ok += 1
            except Exception as exc:  # noqa: BLE001
                err += 1
                self.stderr.write(self.style.ERROR(f"  falhou {desc}: {exc}"))

        for oficio in dados["oficios"]:
            n = oficio.numero_formatado
            _try(f"ofício {n}", lambda o=oficio: gerar_resposta_documento_oficio(o, pdf))
            _try(f"justificativa {n}", lambda o=oficio: gerar_resposta_justificativa_documento(o, pdf))
            _try(f"termos {n}", lambda o=oficio: gerar_termo_lote(o, pdf))
            _try(f"OS {n}", lambda o=oficio: gerar_resposta_ordem_servico_documento(o, pdf))

        for plano in dados["planos"]:
            _try(f"plano {plano.pk}", lambda p=plano: gerar_plano_documento(p, pdf))

        self.stdout.write(f"Documentos gerados: {ok} ok, {err} erro(s).")

    # ----------------------------------------------------------------- árvore
    def _imprimir_arvore(self, dados):
        from integracoes.google_drive import organizer

        self.stdout.write(self.style.MIGRATE_HEADING("\nÁrvore planejada (preview):"))
        for evento in dados["eventos"]:
            self.stdout.write(self.style.HTTP_INFO(f"\n# Evento: {evento.titulo}"))
            for linha in organizer.planejar_evento(evento):
                self.stdout.write(f"  {linha}")
        avulsos = [o for o in dados["oficios"] if o.evento_id is None]
        if avulsos:
            self.stdout.write(self.style.HTTP_INFO("\n# Ofícios avulsos"))
            for oficio in avulsos:
                for linha in organizer.planejar_oficio(oficio):
                    self.stdout.write(f"  {linha}")

    # ----------------------------------------------------------------- limpeza
    def _limpar(self):
        from documentos.models import DocumentoArtefato
        from eventos.models import Evento
        from oficios.models import Oficio
        from planos_trabalho.models import PlanoTrabalho
        from roteiros.models import Roteiro

        oficios = Oficio.objects.filter(assunto__startswith=TAG)
        eventos = Evento.objects.filter(titulo__startswith=TAG)
        roteiro_ids = [r for r in oficios.values_list("roteiro_id", flat=True) if r]

        n_art = DocumentoArtefato.objects.filter(
            oficio__in=oficios
        ).count() + DocumentoArtefato.objects.filter(evento__in=eventos).count()
        DocumentoArtefato.objects.filter(oficio__in=oficios).delete()
        DocumentoArtefato.objects.filter(evento__in=eventos).delete()

        n_plan, _ = PlanoTrabalho.objects.filter(sufixo_numero=PLANO_TAG).delete()
        n_of, _ = oficios.delete()
        Roteiro.objects.filter(pk__in=roteiro_ids).delete()
        n_ev, _ = eventos.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Removidos: ~{n_art} artefatos, {n_plan} obj de plano, "
                f"{n_of} obj de ofício, {n_ev} obj de evento."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Atenção: arquivos já enviados ao Google Drive NÃO foram apagados de lá."
            )
        )
