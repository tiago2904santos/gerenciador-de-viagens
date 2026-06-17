import argparse
from decimal import Decimal, InvalidOperation
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django
from django.core.management import call_command
from django.db import connection, transaction
from django.utils import timezone

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from cadastros.models import AssinaturaConfiguracao  # noqa: E402
from cadastros.models import Cargo  # noqa: E402
from cadastros.models import Cidade  # noqa: E402
from cadastros.models import Combustivel  # noqa: E402
from cadastros.models import ConfiguracaoSistema  # noqa: E402
from cadastros.models import Estado  # noqa: E402
from cadastros.models import Servidor  # noqa: E402
from cadastros.models import Unidade  # noqa: E402
from cadastros.models import Viatura  # noqa: E402
from justificativas.models import Justificativa  # noqa: E402
from justificativas.models import ModeloJustificativa  # noqa: E402
from oficios.models import ModeloMotivoOficio  # noqa: E402
from oficios.models import Oficio  # noqa: E402
from ordens_servico.models import OrdemServico  # noqa: E402
from planos_trabalho.models import AtividadePlanoTrabalho  # noqa: E402
from planos_trabalho.models import EfetivoPlano  # noqa: E402
from planos_trabalho.models import HorarioAtendimento  # noqa: E402
from planos_trabalho.models import PlanoDestino  # noqa: E402
from planos_trabalho.models import PlanoTrabalho  # noqa: E402
from planos_trabalho.models import ProgramaSolicitante  # noqa: E402
from roteiros.models import Roteiro  # noqa: E402
from roteiros.models import RoteiroDestino  # noqa: E402
from roteiros.models import RoteiroTrecho  # noqa: E402
from termos.models import TermoAutorizacao  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite_path", type=Path)
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def sqlite_rows(con, table):
    con.row_factory = sqlite3.Row
    return [dict(row) for row in con.execute(f'SELECT * FROM "{table}"')]


def ids(con, table):
    return {row["id"] for row in sqlite_rows(con, table)}


def fk(value, valid_ids):
    if value in ("", 0):
        return None
    return value if value in valid_ids else None


def text(value, default=""):
    return default if value is None else value


def clip(value, size, default=""):
    return text(value, default)[:size]


def int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def uf_ibge_or_none(value):
    value = int_or_none(value)
    if value is None or not 1 <= value <= 99:
        return None
    return value


def decimal_or_none(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float, Decimal)):
        return value
    cleaned = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def status_gerado(value):
    return "GERADO" if value == "FINALIZADO" else (value or "RASCUNHO")


def now():
    return timezone.now()


def touched(row):
    created = row.get("created_at") or row.get("criado_em") or row.get("data_criacao") or now()
    updated = row.get("updated_at") or row.get("atualizado_em") or created or now()
    return created, updated


def bulk(model, objects):
    if objects:
        model.objects.bulk_create(objects, batch_size=500)
    return len(objects)


def reset_sequences():
    tables = [
        model._meta.db_table
        for model in [
            get_user_model(),
            Unidade,
            Estado,
            Cidade,
            Cargo,
            Combustivel,
            Servidor,
            Viatura,
            ConfiguracaoSistema,
            AssinaturaConfiguracao,
            Roteiro,
            RoteiroDestino,
            RoteiroTrecho,
            Oficio,
            ModeloMotivoOficio,
            ModeloJustificativa,
            Justificativa,
            TermoAutorizacao,
            ProgramaSolicitante,
            HorarioAtendimento,
            AtividadePlanoTrabalho,
            PlanoTrabalho,
            PlanoDestino,
            EfetivoPlano,
            OrdemServico,
        ]
    ]
    m2m_tables = [
        Oficio.servidores.through._meta.db_table,
        Oficio.servidores_termo_autorizacao.through._meta.db_table,
        TermoAutorizacao.servidores.through._meta.db_table,
        OrdemServico.oficios.through._meta.db_table,
        OrdemServico.destinos.through._meta.db_table,
        OrdemServico.servidores.through._meta.db_table,
        PlanoTrabalho.atividades_selecionadas.through._meta.db_table,
    ]
    with connection.cursor() as cursor:
        for table in sorted(set(tables + m2m_tables)):
            cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", [table])
            sequence = cursor.fetchone()[0]
            if not sequence:
                continue
            cursor.execute(f'SELECT MAX(id) FROM "{table}"')
            max_id = cursor.fetchone()[0]
            if max_id is None:
                cursor.execute("SELECT setval(%s, 1, false)", [sequence])
            else:
                cursor.execute("SELECT setval(%s, %s, true)", [sequence, max_id])


def import_auth(con):
    User = get_user_model()
    count = 0
    for row in sqlite_rows(con, "auth_user"):
        User.objects.create(
            id=row["id"],
            password=row["password"],
            last_login=row["last_login"],
            is_superuser=row["is_superuser"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            is_staff=row["is_staff"],
            is_active=row["is_active"],
            date_joined=row["date_joined"],
        )
        count += 1
    return {"auth_user": count}


def import_cadastros(con):
    counts = {}
    estado_rows = sqlite_rows(con, "cadastros_estado")
    estado_siglas = {row["id"]: row["sigla"] for row in estado_rows}
    estado_ids = {row["id"] for row in estado_rows}
    cidade_ids = ids(con, "cadastros_cidade")
    cargo_ids = ids(con, "cadastros_cargo")
    unidade_ids = ids(con, "cadastros_unidadelotacao")
    combustivel_ids = ids(con, "cadastros_combustivelveiculo")
    servidor_ids = ids(con, "cadastros_viajante")
    viatura_ids = ids(con, "cadastros_veiculo")

    counts["cadastros_estado"] = bulk(
        Estado,
        [
            Estado(
                id=row["id"],
                nome=row["nome"],
                sigla=row["sigla"],
                codigo_ibge=uf_ibge_or_none(row["codigo_ibge"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in estado_rows
        ],
    )
    counts["cadastros_cidade"] = bulk(
        Cidade,
        [
            Cidade(
                id=row["id"],
                estado_id=row["estado_id"],
                nome=row["nome"],
                uf=estado_siglas.get(row["estado_id"], "")[:2],
                codigo_ibge=int_or_none(row["codigo_ibge"]),
                capital=False,
                latitude=row.get("latitude"),
                longitude=row.get("longitude"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_cidade")
        ],
    )
    counts["cadastros_cargo"] = bulk(
        Cargo,
        [
            Cargo(
                id=row["id"],
                nome=row["nome"],
                is_padrao=bool(row["is_padrao"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_cargo")
        ],
    )
    counts["cadastros_unidade"] = bulk(
        Unidade,
        [
            Unidade(
                id=row["id"],
                nome=row["nome"],
                sigla="",
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_unidadelotacao")
        ],
    )
    counts["cadastros_combustivel"] = bulk(
        Combustivel,
        [
            Combustivel(
                id=row["id"],
                nome=row["nome"],
                is_padrao=bool(row["is_padrao"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_combustivelveiculo")
        ],
    )
    counts["cadastros_servidor"] = bulk(
        Servidor,
        [
            Servidor(
                id=row["id"],
                nome=row["nome"],
                cargo_id=fk(row["cargo_id"], cargo_ids),
                cpf=text(row["cpf"]),
                rg=text(row["rg"]),
                sem_rg=bool(row["sem_rg"]),
                telefone=text(row["telefone"]),
                unidade_id=fk(row["unidade_lotacao_id"], unidade_ids),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_viajante")
        ],
    )
    counts["cadastros_viatura"] = bulk(
        Viatura,
        [
            Viatura(
                id=row["id"],
                placa=clip(row["placa"], 7),
                modelo=row["modelo"],
                combustivel_id=fk(row["combustivel_id"], combustivel_ids),
                tipo=text(row["tipo"]),
                unidade_id=None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_veiculo")
        ],
    )
    counts["cadastros_configuracaosistema"] = bulk(
        ConfiguracaoSistema,
        [
            ConfiguracaoSistema(
                id=row["id"],
                cidade_sede_padrao_id=fk(row["cidade_sede_padrao_id"], cidade_ids),
                prazo_justificativa_dias=row["prazo_justificativa_dias"],
                nome_orgao=row["nome_orgao"],
                sigla_orgao=row["sigla_orgao"],
                divisao=row["divisao"],
                unidade=row["unidade"],
                cep=row["cep"],
                logradouro=row["logradouro"],
                bairro=row["bairro"],
                cidade_endereco=row["cidade_endereco"],
                uf=row["uf"],
                numero=row["numero"],
                telefone=row["telefone"],
                email=row["email"],
                sede=row["sede"],
                nome_chefia=row["nome_chefia"],
                cargo_chefia=row["cargo_chefia"],
                coordenador_adm_plano_trabalho_id=fk(row["coordenador_adm_plano_trabalho_id"], servidor_ids),
                pt_ultimo_numero=row["pt_ultimo_numero"],
                pt_ano=row["pt_ano"],
                pt_sufixo_numero="ASCOM",
                created_at=now(),
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_configuracaosistema")
        ],
    )
    counts["cadastros_assinaturaconfiguracao"] = bulk(
        AssinaturaConfiguracao,
        [
            AssinaturaConfiguracao(
                id=row["id"],
                configuracao_id=row["configuracao_id"],
                tipo=row["tipo"],
                servidor_id=fk(row["viajante_id"], servidor_ids),
                ordem=row.get("ordem") or 100,
                ativo=bool(row["ativo"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "cadastros_assinaturaconfiguracao")
        ],
    )
    return counts


def import_roteiros(con):
    counts = {}
    estado_ids = ids(con, "cadastros_estado")
    cidade_ids = ids(con, "cadastros_cidade")
    roteiro_ids = ids(con, "eventos_roteiroevento")
    counts["roteiros_roteiro"] = bulk(
        Roteiro,
        [
            Roteiro(
                id=row["id"],
                origem_estado_id=fk(row["origem_estado_id"], estado_ids),
                origem_cidade_id=fk(row["origem_cidade_id"], cidade_ids),
                saida_dt=row["saida_dt"],
                duracao_min=row["duracao_min"],
                chegada_dt=row["chegada_dt"],
                retorno_saida_dt=row["retorno_saida_dt"],
                retorno_duracao_min=row["retorno_duracao_min"],
                retorno_chegada_dt=row["retorno_chegada_dt"],
                quantidade_diarias=text(row["quantidade_diarias"]),
                valor_diarias=row["valor_diarias"],
                valor_diarias_extenso=text(row["valor_diarias_extenso"]),
                observacoes=text(row["observacoes"]),
                status=row["status"] or Roteiro.STATUS_RASCUNHO,
                tipo=row["tipo"] or Roteiro.TIPO_AVULSO,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_roteiroevento")
        ],
    )
    counts["roteiros_roteirodestino"] = bulk(
        RoteiroDestino,
        [
            RoteiroDestino(
                id=row["id"],
                roteiro_id=fk(row["roteiro_id"], roteiro_ids),
                estado_id=fk(row["estado_id"], estado_ids),
                cidade_id=fk(row["cidade_id"], cidade_ids),
                ordem=row["ordem"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_roteiroeventodestino")
            if fk(row["roteiro_id"], roteiro_ids) and fk(row["estado_id"], estado_ids) and fk(row["cidade_id"], cidade_ids)
        ],
    )
    counts["roteiros_roteirotrecho"] = bulk(
        RoteiroTrecho,
        [
            RoteiroTrecho(
                id=row["id"],
                roteiro_id=fk(row["roteiro_id"], roteiro_ids),
                ordem=row["ordem"],
                tipo=row["tipo"] or RoteiroTrecho.TIPO_IDA,
                origem_estado_id=fk(row["origem_estado_id"], estado_ids),
                origem_cidade_id=fk(row["origem_cidade_id"], cidade_ids),
                destino_estado_id=fk(row["destino_estado_id"], estado_ids),
                destino_cidade_id=fk(row["destino_cidade_id"], cidade_ids),
                saida_dt=row["saida_dt"],
                chegada_dt=row["chegada_dt"],
                distancia_km=row["distancia_km"],
                duracao_estimada_min=row["duracao_estimada_min"],
                tempo_cru_estimado_min=row["tempo_cru_estimado_min"],
                tempo_adicional_min=row["tempo_adicional_min"],
                rota_fonte=text(row["rota_fonte"]),
                rota_calculada_em=row["rota_calculada_em"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_roteiroeventotrecho")
            if fk(row["roteiro_id"], roteiro_ids)
        ],
    )
    return counts


def import_oficios(con):
    counts = {}
    servidor_ids = ids(con, "cadastros_viajante")
    combustivel_ids = ids(con, "cadastros_combustivelveiculo")
    viatura_ids = ids(con, "cadastros_veiculo")
    roteiro_ids = ids(con, "eventos_roteiroevento")
    oficio_ids = ids(con, "eventos_oficio")
    counts["oficios_modelomotivooficio"] = bulk(
        ModeloMotivoOficio,
        [
            ModeloMotivoOficio(
                id=row["id"],
                nome=row["nome"],
                texto=row["texto"],
                ativo=bool(row["ativo"]),
                ordem=row.get("ordem") or 100,
                is_padrao=bool(row["padrao"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_modelomotivoviagem")
        ],
    )
    oficio_objs = []
    for row in sqlite_rows(con, "eventos_oficio"):
        motorista_ref = ""
        if row["motorista_oficio_numero"] and row["motorista_oficio_ano"]:
            motorista_ref = f'{row["motorista_oficio_numero"]}/{row["motorista_oficio_ano"]}'
        oficio_objs.append(
            Oficio(
                id=row["id"],
                numero=row["numero"],
                ano=row["ano"],
                data_criacao=row["data_criacao"] or now().date(),
                protocolo=text(row["protocolo"]),
                assunto=text(row["assunto_tipo"]),
                motivo=text(row["motivo"]),
                status=row["status"] or Oficio.STATUS_RASCUNHO,
                roteiro_id=fk(row["roteiro_evento_id"], roteiro_ids),
                solicitante_id=None,
                custeio="UNIDADE_DPC" if row["custeio_tipo"] == "UNIDADE" else (row["custeio_tipo"] or "UNIDADE_DPC"),
                custeio_observacao=text(row["nome_instituicao_custeio"]),
                viatura_id=fk(row["veiculo_id"], viatura_ids),
                motorista_id=fk(row["motorista_viajante_id"], servidor_ids),
                porte_transporte_armas=bool(row["porte_transporte_armas"]),
                transporte_placa_manual=text(row["placa"]),
                transporte_modelo_manual=text(row["modelo"]),
                transporte_combustivel_manual_id=None,
                transporte_tipo_manual=text(row["tipo_viatura"]),
                motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR if fk(row["motorista_viajante_id"], servidor_ids) else Oficio.MOTORISTA_MODO_MANUAL,
                motorista_manual_nome=text(row["motorista"]),
                motorista_oficio_referencia=motorista_ref,
                motorista_protocolo_ref=text(row["motorista_protocolo"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    counts["oficios_oficio"] = bulk(Oficio, oficio_objs)
    through = Oficio.servidores.through
    counts["oficios_oficio_servidores"] = bulk(
        through,
        [
            through(id=row["id"], oficio_id=fk(row["oficio_id"], oficio_ids), servidor_id=fk(row["viajante_id"], servidor_ids))
            for row in sqlite_rows(con, "eventos_oficio_viajantes")
            if fk(row["oficio_id"], oficio_ids) and fk(row["viajante_id"], servidor_ids)
        ],
    )
    return counts


def import_documentos_domain(con):
    counts = {}
    oficio_ids = ids(con, "eventos_oficio")
    servidor_ids = ids(con, "cadastros_viajante")
    modelo_just_ids = ids(con, "eventos_modelojustificativa")
    viatura_ids = ids(con, "cadastros_veiculo")

    counts["justificativas_modelojustificativa"] = bulk(
        ModeloJustificativa,
        [
            ModeloJustificativa(
                id=row["id"],
                nome=row["nome"],
                texto=row["texto"],
                ativo=bool(row["ativo"]),
                ordem=row.get("ordem") or 100,
                is_padrao=bool(row["padrao"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_modelojustificativa")
        ],
    )
    seen_oficios = set()
    justificativas = []
    for row in sqlite_rows(con, "eventos_justificativa"):
        oficio_id = fk(row["oficio_id"], oficio_ids)
        if not oficio_id or oficio_id in seen_oficios:
            continue
        seen_oficios.add(oficio_id)
        justificativas.append(
            Justificativa(
                id=row["id"],
                oficio_id=oficio_id,
                modelo_id=fk(row["modelo_id"], modelo_just_ids),
                texto=text(row["texto"]),
                status=Justificativa.STATUS_FINALIZADA,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    counts["justificativas_justificativa"] = bulk(Justificativa, justificativas)

    termo_objs = []
    for row in sqlite_rows(con, "eventos_termoautorizacao"):
        termo_objs.append(
            TermoAutorizacao(
                id=row["id"],
                oficio_id=fk(row["oficio_id"], oficio_ids),
                data_evento_inicio=row["data_evento"],
                data_evento_fim=row["data_evento_fim"],
                viatura_id=fk(row["veiculo_id"], viatura_ids),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    counts["termos_termoautorizacao"] = bulk(TermoAutorizacao, termo_objs)
    through = TermoAutorizacao.servidores.through
    counts["termos_termoautorizacao_servidores"] = bulk(
        through,
        [
            through(id=row["id"], termoautorizacao_id=row["id"], servidor_id=fk(row["viajante_id"], servidor_ids))
            for row in sqlite_rows(con, "eventos_termoautorizacao")
            if fk(row["viajante_id"], servidor_ids)
        ],
    )
    oficio_termo = Oficio.servidores_termo_autorizacao.through
    old_pairs = {}
    for row in sqlite_rows(con, "eventos_termoautorizacao"):
        oficio_id = fk(row["oficio_id"], oficio_ids)
        servidor_id = fk(row["viajante_id"], servidor_ids)
        if oficio_id and servidor_id:
            old_pairs[(oficio_id, servidor_id)] = True
    counts["oficios_oficio_servidores_termo_autorizacao"] = bulk(
        oficio_termo,
        [
            oficio_termo(oficio_id=oficio_id, servidor_id=servidor_id)
            for oficio_id, servidor_id in old_pairs
        ],
    )
    return counts


def import_planos(con):
    counts = {}
    programa_ids = ids(con, "eventos_solicitanteplanotrabalho")
    cargo_ids = ids(con, "cadastros_cargo")
    servidor_ids = ids(con, "cadastros_viajante")
    cidade_ids = ids(con, "cadastros_cidade")
    estado_ids = ids(con, "cadastros_estado")
    atividade_ids = ids(con, "eventos_atividadeplanotrabalho")

    counts["planos_trabalho_programasolicitante"] = bulk(
        ProgramaSolicitante,
        [
            ProgramaSolicitante(
                id=row["id"],
                nome=row["nome"],
                ativo=bool(row["ativo"]),
                ordem=row["ordem"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_solicitanteplanotrabalho")
        ],
    )
    counts["planos_trabalho_horarioatendimento"] = bulk(
        HorarioAtendimento,
        [
            HorarioAtendimento(
                id=row["id"],
                faixa=row["descricao"],
                ativo=bool(row["ativo"]),
                ordem=row["ordem"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_horarioatendimentoplanotrabalho")
        ],
    )
    counts["planos_trabalho_atividadeplanotrabalho"] = bulk(
        AtividadePlanoTrabalho,
        [
            AtividadePlanoTrabalho(
                id=row["id"],
                codigo=row["codigo"],
                nome=row["nome"],
                meta=row["meta"],
                recurso_necessario=row["recurso_necessario"],
                ordem=row["ordem"],
                ativo=bool(row["ativo"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_atividadeplanotrabalho")
        ],
    )
    plano_objs = []
    for row in sqlite_rows(con, "eventos_planotrabalho"):
        plano_objs.append(
            PlanoTrabalho(
                id=row["id"],
                numero=row["numero"],
                ano=row["ano"],
                data_criacao=row["data_criacao"],
                status=status_gerado(row["status"]),
                contextualizacao=text(row["observacoes"]),
                programa_id=fk(row["solicitante_id"], programa_ids),
                programa_outros=text(row["solicitante_outros"]),
                data_evento_inicio=row["evento_data_inicio"],
                data_evento_fim=row["evento_data_fim"],
                horario_atendimento=text(row["horario_atendimento"], "09:00 ate 17:00"),
                coordenacao=text(row["coordenador_municipal"]),
                coordenador_adm_id=fk(row["coordenador_administrativo_id"], servidor_ids),
                coordenador_op_id=fk(row["coordenador_operacional_id"], servidor_ids),
                saida_sede_data=row["data_saida_sede"],
                saida_sede_hora=row["hora_saida_sede"],
                chegada_sede_data=row["data_chegada_sede"],
                chegada_sede_hora=row["hora_chegada_sede"],
                diarias_composicao=text(row["diarias_quantidade"] or row["quantidade_diarias"]),
                diarias_valor_unitario=decimal_or_none(row["diarias_valor_unitario"]),
                diarias_valor_total=decimal_or_none(row["diarias_valor_total"] or row["valor_diarias"]),
                metas=text(row["metas_formatadas"]),
                atividades=text(row["atividades_codigos"]),
                recursos_necessarios=text(row["recursos_texto"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    counts["planos_trabalho_planotrabalho"] = bulk(PlanoTrabalho, plano_objs)
    plano_ids = ids(con, "eventos_planotrabalho")
    counts["planos_trabalho_efetivoplano"] = bulk(
        EfetivoPlano,
        [
            EfetivoPlano(
                id=row["id"],
                plano_id=fk(row["plano_trabalho_id"], plano_ids),
                cargo_id=fk(row["cargo_id"], cargo_ids),
                quantidade=row["quantidade"],
                created_at=now(),
                updated_at=now(),
            )
            for row in sqlite_rows(con, "eventos_efetivoplanotrabalhodocumento")
            if fk(row["plano_trabalho_id"], plano_ids) and fk(row["cargo_id"], cargo_ids)
        ],
    )
    through = PlanoTrabalho.atividades_selecionadas.through
    rels = []
    seen = set()
    for row in sqlite_rows(con, "eventos_planotrabalho"):
        codigos = [c.strip().upper() for c in text(row["atividades_codigos"]).replace(";", ",").split(",") if c.strip()]
        if not codigos:
            continue
        by_codigo = {
            a["codigo"].upper(): a["id"]
            for a in sqlite_rows(con, "eventos_atividadeplanotrabalho")
        }
        for codigo in codigos:
            atividade_id = by_codigo.get(codigo)
            key = (row["id"], atividade_id)
            if atividade_id in atividade_ids and key not in seen:
                seen.add(key)
                rels.append(through(planotrabalho_id=row["id"], atividadeplanotrabalho_id=atividade_id))
    counts["planos_trabalho_planotrabalho_atividades_selecionadas"] = bulk(through, rels)
    return counts


def import_ordens(con):
    counts = {}
    oficio_ids = ids(con, "eventos_oficio")
    servidor_ids = ids(con, "cadastros_viajante")
    ordem_ids = ids(con, "eventos_ordemservico")
    counts["ordens_servico_ordemservico"] = bulk(
        OrdemServico,
        [
            OrdemServico(
                id=row["id"],
                numero=row["numero"],
                ano=row["ano"],
                data_evento_inicio=row["data_deslocamento"],
                data_evento_fim=row["data_deslocamento_fim"],
                motivo=text(row["motivo_texto"] or row["finalidade"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in sqlite_rows(con, "eventos_ordemservico")
        ],
    )
    ordem_oficios = OrdemServico.oficios.through
    counts["ordens_servico_ordemservico_oficios"] = bulk(
        ordem_oficios,
        [
            ordem_oficios(ordemservico_id=row["id"], oficio_id=fk(row["oficio_id"], oficio_ids))
            for row in sqlite_rows(con, "eventos_ordemservico")
            if fk(row["oficio_id"], oficio_ids)
        ],
    )
    ordem_servidores = OrdemServico.servidores.through
    counts["ordens_servico_ordemservico_servidores"] = bulk(
        ordem_servidores,
        [
            ordem_servidores(id=row["id"], ordemservico_id=fk(row["ordemservico_id"], ordem_ids), servidor_id=fk(row["viajante_id"], servidor_ids))
            for row in sqlite_rows(con, "eventos_ordemservico_viajantes")
            if fk(row["ordemservico_id"], ordem_ids) and fk(row["viajante_id"], servidor_ids)
        ],
    )
    return counts


def main():
    args = parse_args()
    if not args.sqlite_path.exists():
        raise SystemExit(f"SQLite not found: {args.sqlite_path}")
    if args.reset:
        call_command("flush", interactive=False, verbosity=0)
    con = sqlite3.connect(args.sqlite_path)
    con.row_factory = sqlite3.Row
    summary = {}
    with transaction.atomic():
        for importer in [
            import_auth,
            import_cadastros,
            import_roteiros,
            import_oficios,
            import_documentos_domain,
            import_planos,
            import_ordens,
        ]:
            summary.update(importer(con))
        reset_sequences()
    for table, count in sorted(summary.items()):
        print(f"{table}: {count}")
    print("IGNORED_LEGACY_TABLES: assinaturas_*, documentos_assinatura*, documentos_* legacy CRUD, eventos_* not represented by current models, prestacao_contas_*, diario_bordo_*, integracoes_*")


if __name__ == "__main__":
    main()
