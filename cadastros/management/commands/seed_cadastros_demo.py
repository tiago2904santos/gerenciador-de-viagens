"""
Cria dados de demonstração: cadastros (5 cada), modelos de motivo/justificativa (5 cada),
roteiros completos e ofícios já preenchidos para testes e documentos.

Remove apenas registos marcados por este comando (prefixos ``[DEMO]``, ``[DEMO MOTIVO]``, etc.).
Atualiza a configuração do sistema com cidade sede Curitiba/PR quando a geografia IBGE existe.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Combustivel
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura

from justificativas.models import Justificativa
from justificativas.models import ModeloJustificativa
from justificativas.services import get_or_create_justificativa_oficio

from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio

from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroTrecho


DEMO_TAG = "[DEMO]"
DEMO_MOTIVO = "[DEMO MOTIVO]"
DEMO_JUST = "[DEMO JUST]"
DEMO_OFICIO_ASSUNTO = "[DEMO OFICIO]"
N = 5

_MOTIVOS_SEED = [
    ("AUDIÊNCIA JUDICIAL", "Deslocamento para participação em audiência ou ato judicial designado.", 10, True),
    ("CAPACITAÇÃO", "Participação em curso ou treinamento institucional.", 20, False),
    ("MISSÃO INSTITUCIONAL", "Representação em evento ou missão externa.", 30, False),
    ("PERÍCIA / CAMPO", "Atividade técnica em local diverso da sede.", 40, False),
    ("REUNIÃO INTERINSTITUCIONAL", "Reunião com outros órgãos ou parceiros.", 50, False),
]

_JUST_SEED = [
    ("ANTECEDÊNCIA REGULAMENTAR", "Fundamentação por cadastro com prazo inferior ao mínimo normativo.", 10, True),
    ("URGÊNCIA OPERACIONAL", "Demanda prioritária com prazo externo crítico.", 20, False),
    ("REMARCAÇÃO DE DATAS", "Alteração de agenda mantendo o objeto da viagem.", 30, False),
    ("EVENTO DE CALENDÁRIO FIXO", "Evento com data definida por órgão externo.", 40, False),
    ("EQUIPE MÍNIMA", "Presença física necessária para atividade inadiável.", 50, False),
]


class Command(BaseCommand):
    help = (
        "Cria 5 unidades, cargos, combustíveis, servidores, viaturas; 5 modelos de motivo e de justificativa; "
        "5 ofícios com roteiro (Curitiba–Londrina), transporte e justificativa preenchida."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-config",
            action="store_true",
            help="Não atualizar ConfiguracaoSistema (cidade sede Curitiba).",
        )

    def handle(self, *args, **options):
        skip_config: bool = options["skip_config"]

        with transaction.atomic():
            self._limpar_demo_anterior()

            unidades: list[Unidade] = []
            for i in range(1, N + 1):
                unidades.append(
                    Unidade.objects.create(
                        nome=f"{DEMO_TAG} UNIDADE {i:02d}",
                        sigla=f"DU{i:02d}",
                    ),
                )

            cargos: list[Cargo] = []
            for i in range(1, N + 1):
                cargos.append(
                    Cargo.objects.create(
                        nome=f"{DEMO_TAG} CARGO {i:02d}",
                        is_padrao=(i == 1),
                    ),
                )

            combustiveis: list[Combustivel] = []
            for i in range(1, N + 1):
                combustiveis.append(
                    Combustivel.objects.create(
                        nome=f"{DEMO_TAG} COMBUSTIVEL {i:02d}",
                        is_padrao=(i == 1),
                    ),
                )

            servidores: list[Servidor] = []
            for i in range(1, N + 1):
                cpf = f"{i:011d}"
                servidores.append(
                    Servidor.objects.create(
                        nome=f"{DEMO_TAG} SERVIDOR {i:02d}",
                        cargo=cargos[i - 1],
                        cpf=cpf,
                        sem_rg=True,
                        telefone=f"4199999000{i}",
                        unidade=unidades[i - 1],
                    ),
                )

            placas = [f"XZD{i:04d}" for i in range(1001, 1001 + N)]
            viaturas: list[Viatura] = []
            for i in range(N):
                v = Viatura.objects.create(
                    placa=placas[i],
                    modelo=f"{DEMO_TAG} MODELO {i + 1:02d}",
                    combustivel=combustiveis[i],
                    tipo=Viatura.TIPO_CARACTERIZADA,
                    unidade=unidades[i],
                )
                v.motoristas.add(servidores[i])
                viaturas.append(v)

            if not skip_config:
                self._atualizar_config_curitiba()

            modelos_motivo = self._seed_modelos_motivo()
            modelos_just = self._seed_modelos_justificativa()

            pr = Estado.objects.filter(sigla="PR").first()
            cur = Cidade.objects.filter(estado=pr, nome="CURITIBA").first() if pr else None
            lon = Cidade.objects.filter(estado=pr, nome="LONDRINA").first() if pr else None
            if not (pr and cur and lon):
                self.stdout.write(
                    self.style.WARNING(
                        "CURITIBA/LONDRINA/PR em falta: ofícios de demo sem roteiro geográfico completo.",
                    ),
                )
            else:
                self._seed_oficios_com_roteiro(
                    unidades,
                    servidores,
                    viaturas,
                    pr,
                    cur,
                    lon,
                    modelos_motivo,
                    modelos_just,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Criados {N} unidades, {N} cargos, {N} combustíveis, {N} servidores, {N} viaturas; "
                f"{N} modelos de motivo e {N} de justificativa; ofícios/roteiros {DEMO_OFICIO_ASSUNTO}.*",
            ),
        )

    def _limpar_demo_anterior(self):
        roteiro_ids = list(
            Oficio.objects.filter(assunto__startswith=DEMO_OFICIO_ASSUNTO).values_list("roteiro_id", flat=True),
        )
        Oficio.objects.filter(assunto__startswith=DEMO_OFICIO_ASSUNTO).delete()
        Roteiro.objects.filter(pk__in=[rid for rid in roteiro_ids if rid]).delete()

        ModeloMotivoOficio.objects.filter(nome__startswith=DEMO_MOTIVO).delete()
        ModeloJustificativa.objects.filter(nome__startswith=DEMO_JUST).delete()

        Viatura.objects.filter(placa__startswith="XZD").delete()
        Servidor.objects.filter(nome__contains=DEMO_TAG).delete()
        Combustivel.objects.filter(nome__contains=DEMO_TAG).delete()
        Cargo.objects.filter(nome__contains=DEMO_TAG).delete()
        Unidade.objects.filter(nome__contains=DEMO_TAG).delete()

    def _atualizar_config_curitiba(self):
        est = Estado.objects.filter(sigla="PR").first()
        if not est:
            self.stdout.write(self.style.WARNING("PR não encontrado: configure cidade sede manualmente."))
            return
        cidade = Cidade.objects.filter(estado=est, nome="CURITIBA").first()
        if not cidade:
            self.stdout.write(
                self.style.WARNING("CURITIBA/PR não encontrada: importe a geografia IBGE ou configure manualmente."),
            )
            return
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.cidade_sede_padrao = cidade
        cfg.uf = "PR"
        cfg.cidade_endereco = "CURITIBA"
        cfg.save()
        self.stdout.write(self.style.NOTICE("Configuração: cidade sede padrão = CURITIBA/PR."))

    def _seed_modelos_motivo(self) -> list[ModeloMotivoOficio]:
        out: list[ModeloMotivoOficio] = []
        for titulo, texto, ordem, is_padrao in _MOTIVOS_SEED:
            nome = f"{DEMO_MOTIVO} {titulo}"
            m = ModeloMotivoOficio.objects.create(
                nome=nome,
                texto=texto,
                ativo=True,
                ordem=ordem,
                is_padrao=is_padrao,
            )
            out.append(m)
        return out

    def _seed_modelos_justificativa(self) -> list[ModeloJustificativa]:
        out: list[ModeloJustificativa] = []
        for titulo, texto, ordem, is_padrao in _JUST_SEED:
            nome = f"{DEMO_JUST} {titulo}"
            m = ModeloJustificativa.objects.create(
                nome=nome,
                texto=texto,
                ativo=True,
                ordem=ordem,
                is_padrao=is_padrao,
            )
            out.append(m)
        return out

    def _seed_oficios_com_roteiro(
        self,
        unidades: list[Unidade],
        servidores: list[Servidor],
        viaturas: list[Viatura],
        pr: Estado,
        cur: Cidade,
        lon: Cidade,
        modelos_motivo: list[ModeloMotivoOficio],
        modelos_just: list[ModeloJustificativa],
    ) -> None:
        ano = timezone.localdate().year
        base_d0 = timezone.localdate() - timedelta(days=25)
        t0 = timezone.now().replace(microsecond=0) + timedelta(days=14)
        numeros_ocupados = set(
            Oficio.objects.filter(ano=ano).exclude(numero__isnull=True).values_list("numero", flat=True),
        )
        cand = 930
        while any(cand + k in numeros_ocupados for k in range(1, N + 1)):
            cand += 10

        for i in range(N):
            idx = i + 1
            numero_oficio = cand + idx
            saida_ida = t0 + timedelta(days=i)
            cheg_ida = saida_ida + timedelta(hours=5)
            saida_volta = cheg_ida + timedelta(days=2)
            cheg_volta = saida_volta + timedelta(hours=5)

            roteiro = Roteiro.objects.create(
                tipo=Roteiro.TIPO_AVULSO,
                status=Roteiro.STATUS_RASCUNHO,
                origem_estado=pr,
                origem_cidade=cur,
                saida_dt=saida_ida,
                chegada_dt=cheg_volta,
                retorno_saida_dt=saida_volta,
                retorno_chegada_dt=cheg_volta,
                quantidade_diarias="2",
                valor_diarias=Decimal("150.00"),
                valor_diarias_extenso="CENTO E CINQUENTA REAIS",
                observacoes=f"{DEMO_TAG} roteiro seed {idx}",
                rota_status=Roteiro.ROTA_STATUS_MANUAL,
                rota_fonte=Roteiro.ROTA_FONTE_MANUAL,
            )
            RoteiroDestino.objects.create(roteiro=roteiro, estado=pr, cidade=lon, ordem=1)

            RoteiroTrecho.objects.create(
                roteiro=roteiro,
                ordem=1,
                tipo=RoteiroTrecho.TIPO_IDA,
                origem_estado=pr,
                origem_cidade=cur,
                destino_estado=pr,
                destino_cidade=lon,
                saida_dt=saida_ida,
                chegada_dt=cheg_ida,
                distancia_km=Decimal("380.00"),
                duracao_estimada_min=300,
            )
            RoteiroTrecho.objects.create(
                roteiro=roteiro,
                ordem=2,
                tipo=RoteiroTrecho.TIPO_RETORNO,
                origem_estado=pr,
                origem_cidade=lon,
                destino_estado=pr,
                destino_cidade=cur,
                saida_dt=saida_volta,
                chegada_dt=cheg_volta,
                distancia_km=Decimal("380.00"),
                duracao_estimada_min=300,
            )

            mm = modelos_motivo[i]
            mj = modelos_just[i]

            oficio = Oficio.objects.create(
                numero=numero_oficio,
                ano=ano,
                data_criacao=base_d0,
                protocolo=f"10000000{idx}",
                assunto=f"{DEMO_OFICIO_ASSUNTO} {idx:02d} — DESLOCAMENTO INSTITUCIONAL",
                motivo=mm.texto,
                status=Oficio.STATUS_GERADO,
                roteiro=roteiro,
                solicitante=unidades[i],
                custeio=Oficio.CUSTEIO_UNIDADE_DPC,
                viatura=viaturas[i],
                motorista=servidores[i],
                motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
                porte_transporte_armas=False,
            )
            oficio.servidores.add(servidores[i])

            j = get_or_create_justificativa_oficio(oficio)
            j.modelo = mj
            j.texto = (
                f"{mj.texto} Texto complementar do ofício demo {idx}, com referência ao roteiro "
                f"Curitiba/Londrina e à finalidade administrativa."
            )
            j.status = Justificativa.STATUS_FINALIZADA
            j.save()
