from __future__ import annotations

from datetime import time
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
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
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio
from planos_trabalho.models import AtividadePlanoTrabalho
from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import HorarioAtendimento
from planos_trabalho.models import PlanoDestino
from planos_trabalho.models import PlanoTrabalho
from planos_trabalho.models import ProgramaSolicitante
from planos_trabalho.services import sincronizar_atividades
from planos_trabalho.services import sincronizar_textos_padrao
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroTrecho


class Command(BaseCommand):
    help = "Zera o banco atual e recria dados demo realistas para cadastros, oficios e planos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-flush",
            action="store_true",
            help="Nao zera o banco antes de criar os dados. Use apenas para diagnostico.",
        )

    def handle(self, *args, **options):
        if not options["no_flush"]:
            self.stdout.write(self.style.WARNING("Zerando todas as tabelas do banco configurado..."))
            call_command("flush", interactive=False, verbosity=0)

        with transaction.atomic():
            dados = self._seed_cadastros()
            programas = self._seed_planos_catalogos()
            modelos_motivo, modelos_justificativa = self._seed_modelos_documentais()
            roteiros = self._seed_roteiros(
                dados["estado_pr"],
                dados["curitiba"],
                dados["cidades_destino"],
            )
            self._seed_oficios(
                dados["unidades"],
                dados["servidores"],
                dados["viaturas"],
                roteiros,
                modelos_motivo,
                modelos_justificativa,
            )
            self._seed_planos(
                dados["estado_pr"],
                dados["cidades_destino"],
                dados["unidades"],
                dados["cargos"],
                dados["servidores"],
                programas,
                dados["atividades"],
            )

        self.stdout.write(self.style.SUCCESS("Banco zerado e preenchido com dados demo realistas."))

    def _seed_cadastros(self) -> dict:
        estado_pr = Estado.objects.create(nome="PARANA", sigla="PR", codigo_ibge=41)
        cidades = [
            Cidade.objects.create(
                estado=estado_pr,
                nome="CURITIBA",
                uf="PR",
                codigo_ibge=4106902,
                capital=True,
                latitude=Decimal("-25.4290000"),
                longitude=Decimal("-49.2671000"),
            ),
            Cidade.objects.create(
                estado=estado_pr,
                nome="LONDRINA",
                uf="PR",
                codigo_ibge=4113700,
                latitude=Decimal("-23.3045000"),
                longitude=Decimal("-51.1696000"),
            ),
            Cidade.objects.create(
                estado=estado_pr,
                nome="MARINGA",
                uf="PR",
                codigo_ibge=4115200,
                latitude=Decimal("-23.4205000"),
                longitude=Decimal("-51.9333000"),
            ),
            Cidade.objects.create(
                estado=estado_pr,
                nome="CASCAVEL",
                uf="PR",
                codigo_ibge=4104808,
                latitude=Decimal("-24.9555000"),
                longitude=Decimal("-53.4552000"),
            ),
            Cidade.objects.create(
                estado=estado_pr,
                nome="GUARAPUAVA",
                uf="PR",
                codigo_ibge=4109401,
                latitude=Decimal("-25.3902000"),
                longitude=Decimal("-51.4623000"),
            ),
        ]

        unidades_data = [
            ("DELEGACIA DE ATENDIMENTO AO CIDADAO - CURITIBA", "DAC/CTBA"),
            ("NUCLEO DE OPERACOES COMUNITARIAS", "NOC"),
            ("SECAO DE IDENTIFICACAO CIVIL", "SIC"),
            ("DIVISAO DE APOIO ADMINISTRATIVO", "DAA"),
            ("COORDENACAO DE PROGRAMAS ITINERANTES", "CPI"),
        ]
        unidades = [Unidade.objects.create(nome=nome, sigla=sigla) for nome, sigla in unidades_data]

        cargos_data = [
            "DELEGADO DE POLICIA",
            "INVESTIGADOR DE POLICIA",
            "ESCRIVAO DE POLICIA",
            "PAPILOSCOPISTA POLICIAL",
            "AGENTE ADMINISTRATIVO",
        ]
        cargos = [Cargo.objects.create(nome=nome, is_padrao=(i == 0)) for i, nome in enumerate(cargos_data)]

        combustiveis_data = ["GASOLINA", "ETANOL", "FLEX", "DIESEL S10", "HIBRIDO"]
        combustiveis = [
            Combustivel.objects.create(nome=nome, is_padrao=(i == 2))
            for i, nome in enumerate(combustiveis_data)
        ]

        servidores_data = [
            ("MARIANA LOPES FERREIRA", "23145678901", "1234567PR", "41998451234"),
            ("RAFAEL HENRIQUE MORAES", "34256789012", "2345678PR", "41997562345"),
            ("CAMILA ROCHA ALMEIDA", "45367890123", "3456789PR", "41996673456"),
            ("BRUNO CESAR TEIXEIRA", "56478901234", "4567890PR", "41995784567"),
            ("JULIANA MARTINS PEREIRA", "67589012345", "5678901PR", "41994895678"),
        ]
        servidores = []
        for i, (nome, cpf, rg, telefone) in enumerate(servidores_data):
            servidores.append(
                Servidor.objects.create(
                    nome=nome,
                    cargo=cargos[i],
                    cpf=cpf,
                    rg=rg,
                    telefone=telefone,
                    unidade=unidades[i],
                ),
            )

        viaturas_data = [
            ("BCD1E23", "TOYOTA COROLLA XEI", combustiveis[2], Viatura.TIPO_DESCARACTERIZADA),
            ("FGH2J45", "CHEVROLET TRAILBLAZER LTZ", combustiveis[3], Viatura.TIPO_CARACTERIZADA),
            ("JKL3M67", "RENAULT DUSTER INTENSE", combustiveis[2], Viatura.TIPO_CARACTERIZADA),
            ("NPQ4R89", "FIAT TORO FREEDOM", combustiveis[3], Viatura.TIPO_DESCARACTERIZADA),
            ("STU5V01", "VOLKSWAGEN AMAROK HIGHLINE", combustiveis[3], Viatura.TIPO_CARACTERIZADA),
        ]
        viaturas = []
        for i, (placa, modelo, combustivel, tipo) in enumerate(viaturas_data):
            viatura = Viatura.objects.create(
                placa=placa,
                modelo=modelo,
                combustivel=combustivel,
                tipo=tipo,
                unidade=unidades[i],
            )
            viatura.motoristas.add(servidores[i])
            viaturas.append(viatura)

        cfg = ConfiguracaoSistema.get_singleton()
        cfg.cidade_sede_padrao = cidades[0]
        cfg.nome_orgao = "POLICIA CIVIL DO PARANA"
        cfg.sigla_orgao = "PCPR"
        cfg.divisao = "ASSESSORIA DE COMUNICACAO SOCIAL"
        cfg.unidade = "PROGRAMAS ITINERANTES"
        cfg.cep = "80010000"
        cfg.logradouro = "RUA JOSE LOUREIRO"
        cfg.numero = "540"
        cfg.bairro = "CENTRO"
        cfg.cidade_endereco = "CURITIBA"
        cfg.uf = "PR"
        cfg.telefone = "4133000000"
        cfg.email = "ascom.demo@pcpr.pr.gov.br"
        cfg.nome_chefia = "ANA PAULA RIBEIRO COSTA"
        cfg.cargo_chefia = "DELEGADA DE POLICIA"
        cfg.coordenador_adm_plano_trabalho = servidores[0]
        cfg.pt_ano = timezone.localdate().year
        cfg.pt_ultimo_numero = 5
        cfg.pt_sufixo_numero = "ASCOM"
        cfg.save()

        atividades = self._seed_atividades()

        return {
            "estado_pr": estado_pr,
            "curitiba": cidades[0],
            "cidades_destino": cidades[1:],
            "unidades": unidades,
            "cargos": cargos,
            "servidores": servidores,
            "viaturas": viaturas,
            "atividades": atividades,
        }

    def _seed_atividades(self) -> list[AtividadePlanoTrabalho]:
        atividades_data = [
            (
                "CIN",
                "Confeccao da Carteira de Identidade Nacional",
                "Emitir documentos de identificacao civil para a populacao atendida.",
                "Kit biometrico, notebook, impressora e conectividade segura.",
            ),
            (
                "BO",
                "Registro de boletins de ocorrencia",
                "Formalizar demandas policiais apresentadas durante o atendimento itinerante.",
                "Estacao de atendimento, acesso aos sistemas e equipe de triagem.",
            ),
            (
                "AAC",
                "Emissao de atestado de antecedentes criminais",
                "Facilitar a emissao de certidoes necessarias para fins civis e trabalhistas.",
                "Terminal com acesso institucional e impressora.",
            ),
            (
                "ORIENTACOES",
                "Orientacoes preventivas a comunidade",
                "Promover informacao qualificada sobre seguranca publica e cidadania.",
                "Material informativo, espaco para atendimento e equipe de apoio.",
            ),
            (
                "UNIDADE_MOVEL",
                "Operacao de unidade movel institucional",
                "Garantir estrutura adequada para atendimento descentralizado.",
                "Unidade movel, energia, internet, mobiliario e suporte operacional.",
            ),
        ]
        atividades = []
        for i, (codigo, nome, meta, recurso) in enumerate(atividades_data, start=1):
            atividades.append(
                AtividadePlanoTrabalho.objects.create(
                    codigo=codigo,
                    nome=nome,
                    meta=meta,
                    recurso_necessario=recurso,
                    ordem=i * 10,
                    ativo=True,
                ),
            )
        return atividades

    def _seed_planos_catalogos(self) -> list[ProgramaSolicitante]:
        programas_data = [
            "PCPR NA COMUNIDADE",
            "PROGRAMA PARANA EM ACAO",
            "JUSTICA NO BAIRRO",
            "MUTIRAO DA CIDADANIA",
            "ESCOLA SEGURA",
        ]
        programas = [
            ProgramaSolicitante.objects.create(nome=nome, ordem=i * 10, ativo=True)
            for i, nome in enumerate(programas_data, start=1)
        ]

        horarios_data = [
            "08:00 ate 12:00",
            "09:00 ate 17:00",
            "10:00 ate 18:00",
            "13:00 ate 19:00",
            "08:30 ate 16:30",
        ]
        for i, faixa in enumerate(horarios_data, start=1):
            HorarioAtendimento.objects.create(faixa=faixa, ordem=i * 10, ativo=True)

        return programas

    def _seed_modelos_documentais(self) -> tuple[list[ModeloMotivoOficio], list[ModeloJustificativa]]:
        motivos_data = [
            ("AUTORIZACAO PARA DESLOCAMENTO", "Solicita-se autorizacao para deslocamento de equipe em acao institucional."),
            ("APOIO OPERACIONAL EM EVENTO", "Solicita-se apoio operacional para atendimento descentralizado ao cidadao."),
            ("PARTICIPACAO EM REUNIAO TECNICA", "Solicita-se deslocamento para alinhamento tecnico com parceiros locais."),
            ("ACAO DE IDENTIFICACAO CIVIL", "Solicita-se autorizacao para execucao de servicos de identificacao civil."),
            ("ATENDIMENTO ITINERANTE", "Solicita-se deslocamento para atendimento itinerante previamente programado."),
        ]
        motivos = [
            ModeloMotivoOficio.objects.create(
                nome=nome,
                texto=texto,
                ativo=True,
                ordem=i * 10,
                is_padrao=(i == 1),
            )
            for i, (nome, texto) in enumerate(motivos_data, start=1)
        ]

        justificativas_data = [
            ("PRAZO EXTERNO", "A demanda decorre de agenda definida por orgao parceiro, com prazo operacional restrito."),
            ("INTERESSE PUBLICO", "A acao atende interesse publico relevante e amplia acesso a servicos essenciais."),
            ("AGENDA ITINERANTE", "O deslocamento integra calendario itinerante previamente pactuado com o municipio."),
            ("EQUIPE MINIMA", "A equipe indicada corresponde ao efetivo minimo necessario para execucao segura da atividade."),
            ("CONTINUIDADE DO SERVICO", "A viagem assegura continuidade de atendimento institucional ja iniciado."),
        ]
        justificativas = [
            ModeloJustificativa.objects.create(
                nome=nome,
                texto=texto,
                ativo=True,
                ordem=i * 10,
                is_padrao=(i == 1),
            )
            for i, (nome, texto) in enumerate(justificativas_data, start=1)
        ]
        return motivos, justificativas

    def _seed_roteiros(
        self,
        estado_pr: Estado,
        curitiba: Cidade,
        destinos: list[Cidade],
    ) -> list[Roteiro]:
        base_saida = timezone.now().replace(hour=7, minute=30, second=0, microsecond=0) + timedelta(days=14)
        distancias = [Decimal("381.20"), Decimal("425.80"), Decimal("491.40"), Decimal("256.70"), Decimal("162.30")]
        duracoes = [310, 345, 390, 230, 155]
        roteiros = []
        for i in range(5):
            destino = destinos[i % len(destinos)]
            saida = base_saida + timedelta(days=i * 3)
            chegada = saida + timedelta(minutes=duracoes[i])
            retorno_saida = chegada + timedelta(days=1, hours=6)
            retorno_chegada = retorno_saida + timedelta(minutes=duracoes[i])
            roteiro = Roteiro.objects.create(
                tipo=Roteiro.TIPO_AVULSO,
                status=Roteiro.STATUS_FINALIZADO,
                origem_estado=estado_pr,
                origem_cidade=curitiba,
                saida_dt=saida,
                duracao_min=duracoes[i],
                chegada_dt=chegada,
                retorno_saida_dt=retorno_saida,
                retorno_duracao_min=duracoes[i],
                retorno_chegada_dt=retorno_chegada,
                quantidade_diarias="1,5",
                valor_diarias=Decimal("420.00"),
                valor_diarias_extenso="quatrocentos e vinte reais",
                observacoes=f"Roteiro demo Curitiba/{destino.nome.title()} com pernoite operacional.",
                rota_status=Roteiro.ROTA_STATUS_MANUAL,
                rota_fonte=Roteiro.ROTA_FONTE_MANUAL,
                rota_distancia_manual_km=distancias[i],
                rota_duracao_manual_min=duracoes[i],
            )
            RoteiroDestino.objects.create(roteiro=roteiro, estado=estado_pr, cidade=destino, ordem=1)
            RoteiroTrecho.objects.create(
                roteiro=roteiro,
                ordem=1,
                tipo=RoteiroTrecho.TIPO_IDA,
                origem_estado=estado_pr,
                origem_cidade=curitiba,
                destino_estado=estado_pr,
                destino_cidade=destino,
                saida_dt=saida,
                chegada_dt=chegada,
                distancia_km=distancias[i],
                duracao_estimada_min=duracoes[i],
                rota_fonte=Roteiro.ROTA_FONTE_MANUAL,
            )
            RoteiroTrecho.objects.create(
                roteiro=roteiro,
                ordem=2,
                tipo=RoteiroTrecho.TIPO_RETORNO,
                origem_estado=estado_pr,
                origem_cidade=destino,
                destino_estado=estado_pr,
                destino_cidade=curitiba,
                saida_dt=retorno_saida,
                chegada_dt=retorno_chegada,
                distancia_km=distancias[i],
                duracao_estimada_min=duracoes[i],
                rota_fonte=Roteiro.ROTA_FONTE_MANUAL,
            )
            roteiros.append(roteiro)
        return roteiros

    def _seed_oficios(
        self,
        unidades: list[Unidade],
        servidores: list[Servidor],
        viaturas: list[Viatura],
        roteiros: list[Roteiro],
        modelos_motivo: list[ModeloMotivoOficio],
        modelos_justificativa: list[ModeloJustificativa],
    ) -> None:
        ano = timezone.localdate().year
        assuntos = [
            "Deslocamento para acao integrada de cidadania",
            "Apoio operacional em atendimento itinerante",
            "Equipe para emissao de documentos civis",
            "Participacao em reuniao tecnica regional",
            "Atendimento preventivo em evento comunitario",
        ]
        for i in range(5):
            oficio = Oficio.objects.create(
                numero=i + 1,
                ano=ano,
                data_criacao=timezone.localdate() - timedelta(days=5 - i),
                protocolo=f"22.{100000 + i}/2026",
                assunto=assuntos[i],
                motivo=modelos_motivo[i].texto,
                status=Oficio.STATUS_GERADO,
                roteiro=roteiros[i],
                solicitante=unidades[i],
                custeio=Oficio.CUSTEIO_UNIDADE_DPC,
                viatura=viaturas[i],
                motorista=servidores[i],
                motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
                porte_transporte_armas=(i % 2 == 0),
            )
            oficio.servidores.add(servidores[i], servidores[(i + 1) % 5])
            oficio.servidores_termo_autorizacao.add(servidores[i])
            Justificativa.objects.create(
                oficio=oficio,
                modelo=modelos_justificativa[i],
                texto=modelos_justificativa[i].texto,
                obrigatoria=True,
                dias_antecedencia=7 + i,
                prazo_dias=10,
                primeira_saida_dt=roteiros[i].saida_dt,
                status=Justificativa.STATUS_FINALIZADA,
            )

    def _seed_planos(
        self,
        estado_pr: Estado,
        destinos: list[Cidade],
        unidades: list[Unidade],
        cargos: list[Cargo],
        servidores: list[Servidor],
        programas: list[ProgramaSolicitante],
        atividades: list[AtividadePlanoTrabalho],
    ) -> None:
        ano = timezone.localdate().year
        for i in range(5):
            destino = destinos[i % len(destinos)]
            data_evento = timezone.localdate() + timedelta(days=21 + i * 4)
            plano = PlanoTrabalho.objects.create(
                numero=i + 1,
                ano=ano,
                sufixo_numero="ASCOM",
                data_criacao=timezone.localdate() - timedelta(days=i),
                status=PlanoTrabalho.STATUS_GERADO,
                programa=programas[i],
                destino_estado=estado_pr,
                destino_cidade=destino,
                data_evento_inicio=data_evento,
                data_evento_fim=data_evento + timedelta(days=1),
                horario_atendimento="09:00 ate 17:00",
                coordenador_adm=servidores[0],
                coordenador_op=servidores[(i + 1) % 5],
                saida_sede_data=data_evento - timedelta(days=1),
                saida_sede_hora=time(8, 0),
                chegada_sede_data=data_evento + timedelta(days=1),
                chegada_sede_hora=time(19, 0),
                diarias_composicao="1,5 diaria por servidor",
                diarias_valor_unitario=Decimal("420.00"),
                diarias_valor_total=Decimal(str(840 + i * 210)),
            )
            PlanoDestino.objects.create(plano=plano, estado=estado_pr, cidade=destino, ordem=1)
            EfetivoPlano.objects.create(
                plano=plano,
                unidade=unidades[i],
                cargo=cargos[1],
                quantidade=2 + (i % 2),
            )
            EfetivoPlano.objects.create(
                plano=plano,
                unidade=unidades[i],
                cargo=cargos[3],
                quantidade=1,
            )
            selecionadas = [atividades[i], atividades[(i + 1) % 5], atividades[-1]]
            plano.atividades_selecionadas.set(selecionadas)
            sincronizar_atividades(plano)
            sincronizar_textos_padrao(plano)
            plano.save(
                update_fields=[
                    "contextualizacao",
                    "coordenacao",
                    "consideracao_final",
                    "updated_at",
                ],
            )
