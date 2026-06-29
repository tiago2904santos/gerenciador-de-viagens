"""Organizador da árvore de pastas/arquivos no Google Drive.

Estrutura-alvo (a partir da pasta raiz escolhida pelo usuário):

    Eventos/
      <Tipo - Cidade - Período>/
        <Ofício NN protocolo ... Servidores>/
          Ofício NN-AAAA ... (Cidade).pdf
          Ordem de serviço ...                 (arquivo solto)
          Plano de trabalho ...                (arquivo solto)
          Convite (Cidade).<ext>               (EventoAnexo)
          Termos/                              (só se houver termos)
            Termo de autorização ... Servidor (Cidade).pdf
          Prestação de contas/
            Anexo solicitação ... (Cidade).<ext>     (EventoDocumentoSolicitacao)
            Prestação <Servidor>/
              Relatório técnico ...            (AssinaturaDocumento rt)
              Diário de bordo ...              (AssinaturaDocumento db)
              Despacho ...                     (despacho assinado)
              Comprovante de saque ...         (comprovante)

Documentos sem evento caem em ``Avulsos/<Ofício…>`` (ou ``Avulsos/Ano/Mês`` se
nem ofício houver). Tudo é idempotente: reexecutar move/renomeia ao invés de
duplicar (reusa ``get_or_create_pasta`` e os registros ``DriveArquivo`` /
``DriveArquivoExterno``).
"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime

from . import naming
from .services import get_client, is_mock, mimetype_para_formato

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de leitura / mime
# ---------------------------------------------------------------------------

def _ler_filefield(ff) -> bytes | None:
    if not ff:
        return None
    try:
        ff.open("rb")
        try:
            return ff.read()
        finally:
            ff.close()
    except Exception as exc:  # arquivo ausente no storage, etc.
        logger.warning("[Drive] não foi possível ler %s: %s", getattr(ff, "name", "?"), exc)
        return None


def _mime_por_nome(nome: str) -> str:
    ext = naming.extensao(nome)
    if ext:
        por_formato = mimetype_para_formato(ext)
        if por_formato != "application/octet-stream":
            return por_formato
        adivinhado = mimetypes.guess_type(nome)[0]
        if adivinhado:
            return adivinhado
    return "application/octet-stream"


def _raiz() -> str | None:
    from .services import get_pasta_raiz_id

    return get_pasta_raiz_id() or None


# ---------------------------------------------------------------------------
# Pastas
# ---------------------------------------------------------------------------

def pasta_do_oficio(client, oficio, servidores) -> str:
    """Cria/retorna a pasta do ofício (sob Eventos/<evento> ou Avulsos)."""
    raiz = _raiz()
    evento = getattr(oficio, "evento", None)
    if evento is not None:
        eventos = client.get_or_create_pasta(naming.PASTA_EVENTOS, raiz)
        ev = client.get_or_create_pasta(naming.pasta_evento(evento), eventos)
        return client.get_or_create_pasta(naming.pasta_oficio(oficio, servidores), ev)
    avulsos = client.get_or_create_pasta(naming.PASTA_AVULSOS, raiz)
    return client.get_or_create_pasta(naming.pasta_oficio(oficio, servidores), avulsos)


def _pasta_avulsa_por_data(client, dt: datetime) -> str:
    raiz = _raiz()
    avulsos = client.get_or_create_pasta(naming.PASTA_AVULSOS, raiz)
    ano = client.get_or_create_pasta(str(dt.year), avulsos)
    return client.get_or_create_pasta(f"{dt.month:02d}", ano)


def _pasta_prestacao(client, oficio_folder: str) -> str:
    return client.get_or_create_pasta(naming.PASTA_PRESTACAO, oficio_folder)


def _pasta_termos(client, oficio_folder: str) -> str:
    return client.get_or_create_pasta(naming.PASTA_TERMOS, oficio_folder)


# ---------------------------------------------------------------------------
# Persistência: DocumentoArtefato (DriveArquivo)
# ---------------------------------------------------------------------------

def _persistir_artefato(artefato, pasta_id: str, nome: str) -> tuple[str, str] | None:
    from .models import DriveArquivo

    client = get_client()
    mime = mimetype_para_formato(artefato.formato)
    reg = DriveArquivo.objects.filter(artefato=artefato).first()

    if reg and reg.file_id and not reg.mock:
        client.mover_renomear(reg.file_id, nome, pasta_id)
        if reg.nome != nome:
            reg.nome = nome
            reg.save(update_fields=["nome"])
        return reg.file_id, reg.url

    conteudo = _ler_filefield(getattr(artefato, "arquivo", None))
    if conteudo is None:
        return None
    file_id, url = client.upload(nome, conteudo, mime, pasta_id=pasta_id)

    if reg:
        reg.file_id, reg.url, reg.nome = file_id, url, nome
        reg.mime_type, reg.mock = mime, is_mock()
        reg.save()
    else:
        DriveArquivo.objects.create(
            artefato=artefato,
            file_id=file_id,
            url=url,
            nome=nome,
            mime_type=mime,
            mock=is_mock(),
        )
    return file_id, url


def organizar_artefato(artefato) -> tuple[str, str] | None:
    """Coloca um ``DocumentoArtefato`` gerado na pasta certa, com nome bonito.

    Usado tanto no disparo automático (signal) quanto na reorganização em massa.
    """
    client = get_client()
    oficio = getattr(artefato, "oficio", None)

    if oficio is None:
        pasta_id = _pasta_avulsa_por_data(client, getattr(artefato, "criado_em", None) or datetime.now())
        nome = f"{naming.sanitize_drive_name(artefato.tipo or 'documento')}.{(artefato.formato or 'pdf').lower()}"
        return _persistir_artefato(artefato, pasta_id, nome)

    servidores = list(oficio.servidores.all())
    cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
    oficio_folder = pasta_do_oficio(client, oficio, servidores)
    tipo = artefato.tipo or "oficio"
    formato = artefato.formato or "pdf"

    if tipo == "termo_autorizacao":
        pasta_id = _pasta_termos(client, oficio_folder)
        nome = naming.nome_termo(oficio, artefato.servidor, cidade, formato)
    elif tipo == "ordem_servico":
        pasta_id = oficio_folder
        nome = naming.nome_os(oficio, servidores, cidade, formato)
    elif tipo == "plano_trabalho":
        pasta_id = oficio_folder
        nome = naming.nome_plano(oficio, cidade, formato)
    elif tipo == "justificativa":
        pasta_id = oficio_folder
        nome = naming.nome_justificativa(oficio, cidade, formato)
    else:  # oficio
        pasta_id = oficio_folder
        nome = naming.nome_oficio(oficio, servidores, cidade, formato)

    return _persistir_artefato(artefato, pasta_id, nome)


# ---------------------------------------------------------------------------
# Persistência: arquivos externos (DriveArquivoExterno)
# ---------------------------------------------------------------------------

def colocar_arquivo_externo(obj, ff, *, campo: str, pasta_id: str, nome: str) -> tuple[str, str] | None:
    """Envia/move um ``FileField`` que não é ``DocumentoArtefato``.

    Idempotente via ``DriveArquivoExterno`` (content_type + object_id + campo).
    """
    if not ff:
        return None

    from django.contrib.contenttypes.models import ContentType

    from .models import DriveArquivoExterno

    client = get_client()
    ct = ContentType.objects.get_for_model(obj.__class__)
    reg = DriveArquivoExterno.objects.filter(
        content_type=ct, object_id=obj.pk, campo=campo
    ).first()
    mime = _mime_por_nome(nome)

    if reg and reg.file_id and not reg.mock:
        client.mover_renomear(reg.file_id, nome, pasta_id)
        if reg.nome != nome or reg.pasta_id != pasta_id:
            reg.nome, reg.pasta_id = nome, pasta_id
            reg.save(update_fields=["nome", "pasta_id", "atualizado_em"])
        return reg.file_id, reg.url

    conteudo = _ler_filefield(ff)
    if conteudo is None:
        return None
    file_id, url = client.upload(nome, conteudo, mime, pasta_id=pasta_id)

    if reg:
        reg.file_id, reg.url, reg.nome = file_id, url, nome
        reg.pasta_id, reg.mime_type, reg.mock = pasta_id, mime, is_mock()
        reg.save()
    else:
        DriveArquivoExterno.objects.create(
            content_type=ct,
            object_id=obj.pk,
            campo=campo,
            file_id=file_id,
            url=url,
            nome=nome,
            pasta_id=pasta_id,
            mime_type=mime,
            mock=is_mock(),
        )
    return file_id, url


# ---------------------------------------------------------------------------
# Anexos de evento / prestação — colocados pela reorganização e pelos signals
# ---------------------------------------------------------------------------

def organizar_evento_anexo(anexo) -> None:
    """``EventoAnexo`` (convite, ofício solicitante, comprovante) → pasta do ofício."""
    evento = getattr(anexo, "evento", None)
    if evento is None or not getattr(anexo, "arquivo", None):
        return
    client = get_client()
    oficio = evento.oficios.first()
    if oficio is None:
        # Sem ofício ainda: guarda na pasta do evento.
        raiz = _raiz()
        eventos = client.get_or_create_pasta(naming.PASTA_EVENTOS, raiz)
        pasta_id = client.get_or_create_pasta(naming.pasta_evento(evento), eventos)
    else:
        pasta_id = pasta_do_oficio(client, oficio, list(oficio.servidores.all()))

    cidade = naming.cidade_evento(evento)
    ext = naming.extensao(anexo.arquivo.name)
    if anexo.tipo == "convite":
        nome = naming.nome_convite(cidade, ext, titulo=anexo.titulo)
    else:
        titulo = (anexo.titulo or anexo.get_tipo_display()).strip()
        nome = naming._arquivo(f"{titulo}{naming._suf_cidade(cidade)}", ext)
    colocar_arquivo_externo(anexo, anexo.arquivo, campo="arquivo", pasta_id=pasta_id, nome=nome)


def organizar_solicitacao_evento(doc) -> None:
    """``EventoDocumentoSolicitacao`` → ``Prestação de contas`` do (primeiro) ofício."""
    evento = getattr(doc, "evento", None)
    if evento is None or not getattr(doc, "arquivo", None):
        return
    client = get_client()
    oficio = evento.oficios.first()
    if oficio is None:
        return
    servidores = list(oficio.servidores.all())
    oficio_folder = pasta_do_oficio(client, oficio, servidores)
    prestacao_folder = _pasta_prestacao(client, oficio_folder)
    cidade = naming.cidade_evento(evento, oficio)
    ext = naming.extensao(doc.arquivo.name)

    # Quando há uma única prestação no ofício conseguimos o nº da solicitação e o
    # servidor; senão usamos um nome genérico de anexo de solicitação.
    prestacoes = list(oficio.prestacoes_contas.all())
    if len(prestacoes) == 1:
        p = prestacoes[0]
        nome = naming.nome_anexo_solicitacao(oficio, p.servidor, p.numero_solicitacao, cidade, ext)
    else:
        base = f"Anexo solicitação Ofício {naming.num_doc(oficio.numero, oficio.ano)}".strip()
        nome = naming._arquivo(f"{base}{naming._suf_cidade(cidade)}", ext)
    colocar_arquivo_externo(doc, doc.arquivo, campo="arquivo", pasta_id=prestacao_folder, nome=nome)


def organizar_prestacao(prestacao) -> None:
    """Coloca todos os arquivos de uma ``PrestacaoContas`` na pasta do servidor."""
    oficio = getattr(prestacao, "oficio", None)
    servidor = getattr(prestacao, "servidor", None)
    if oficio is None:
        return
    client = get_client()
    servidores = list(oficio.servidores.all())
    cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
    oficio_folder = pasta_do_oficio(client, oficio, servidores)
    prestacao_folder = _pasta_prestacao(client, oficio_folder)
    serv_folder = client.get_or_create_pasta(
        naming.pasta_prestacao_servidor(servidor), prestacao_folder
    )

    # Despacho assinado / comprovante (campos diretos da prestação)
    if getattr(prestacao, "despacho_assinado", None):
        ext = naming.extensao(prestacao.despacho_assinado.name)
        colocar_arquivo_externo(
            prestacao, prestacao.despacho_assinado, campo="despacho_assinado",
            pasta_id=serv_folder, nome=naming.nome_despacho(oficio, servidor, cidade, ext),
        )
    if getattr(prestacao, "comprovante_saque_transferencia", None):
        ext = naming.extensao(prestacao.comprovante_saque_transferencia.name)
        colocar_arquivo_externo(
            prestacao, prestacao.comprovante_saque_transferencia,
            campo="comprovante_saque_transferencia",
            pasta_id=serv_folder, nome=naming.nome_comprovante(oficio, servidor, cidade, ext),
        )

    # Anexos extras (despacho/comprovante adicionais)
    for anexo in prestacao.documentos_anexos.all():
        if not getattr(anexo, "arquivo", None):
            continue
        ext = naming.extensao(anexo.arquivo.name)
        if anexo.tipo == "comprovante":
            nome = naming.nome_comprovante(oficio, servidor, cidade, ext)
        else:
            nome = naming.nome_despacho(oficio, servidor, cidade, ext)
        colocar_arquivo_externo(anexo, anexo.arquivo, campo="arquivo", pasta_id=serv_folder, nome=nome)

    # Relatório técnico / diário de bordo assinados
    for assinatura in prestacao.assinaturas.all():
        if not getattr(assinatura, "arquivo_assinado", None):
            continue
        ext = naming.extensao(assinatura.arquivo_assinado.name) or "pdf"
        if assinatura.tipo == "rt":
            nome = naming.nome_relatorio_tecnico(oficio, servidor, cidade, ext)
        elif assinatura.tipo == "db":
            nome = naming.nome_diario_bordo(oficio, servidor, cidade, ext)
        else:
            continue
        colocar_arquivo_externo(
            assinatura, assinatura.arquivo_assinado, campo="arquivo_assinado",
            pasta_id=serv_folder, nome=nome,
        )


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def organizar_oficio(oficio) -> None:
    """Organiza todos os artefatos e prestações de um ofício."""
    for artefato in oficio.documentos_gerados.all():
        try:
            organizar_artefato(artefato)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar artefato %s: %s", artefato.pk, exc, exc_info=True)
    for prestacao in oficio.prestacoes_contas.all():
        try:
            organizar_prestacao(prestacao)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar prestação %s: %s", prestacao.pk, exc, exc_info=True)


def organizar_evento(evento) -> None:
    """Organiza todos os ofícios, anexos e solicitações de um evento."""
    for oficio in evento.oficios.all():
        organizar_oficio(oficio)
    for anexo in evento.anexos.all():
        try:
            organizar_evento_anexo(anexo)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar anexo %s: %s", anexo.pk, exc, exc_info=True)
    for doc in evento.documentos_solicitacao.all():
        try:
            organizar_solicitacao_evento(doc)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar solicitação %s: %s", doc.pk, exc, exc_info=True)


# ---------------------------------------------------------------------------
# Planejamento (dry-run): computa os caminhos sem tocar no Drive
# ---------------------------------------------------------------------------

def _caminho_base_oficio(oficio, servidores) -> str:
    evento = getattr(oficio, "evento", None)
    if evento is not None:
        base = f"{naming.PASTA_EVENTOS}/{naming.pasta_evento(evento)}"
    else:
        base = naming.PASTA_AVULSOS
    return f"{base}/{naming.pasta_oficio(oficio, servidores)}"


def planejar_oficio(oficio) -> list[str]:
    """Lista ``pasta/arquivo`` que seriam criados/movidos para o ofício (sem I/O)."""
    servidores = list(oficio.servidores.all())
    cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
    base = _caminho_base_oficio(oficio, servidores)
    linhas: list[str] = []

    for art in oficio.documentos_gerados.all():
        tipo, fmt = (art.tipo or "oficio"), (art.formato or "pdf")
        if tipo == "termo_autorizacao":
            linhas.append(f"{base}/{naming.PASTA_TERMOS}/{naming.nome_termo(oficio, art.servidor, cidade, fmt)}")
        elif tipo == "ordem_servico":
            linhas.append(f"{base}/{naming.nome_os(oficio, servidores, cidade, fmt)}")
        elif tipo == "plano_trabalho":
            linhas.append(f"{base}/{naming.nome_plano(oficio, cidade, fmt)}")
        elif tipo == "justificativa":
            linhas.append(f"{base}/{naming.nome_justificativa(oficio, cidade, fmt)}")
        else:
            linhas.append(f"{base}/{naming.nome_oficio(oficio, servidores, cidade, fmt)}")

    for p in oficio.prestacoes_contas.all():
        servf = f"{base}/{naming.PASTA_PRESTACAO}/{naming.pasta_prestacao_servidor(p.servidor)}"
        if getattr(p, "despacho_assinado", None):
            linhas.append(f"{servf}/{naming.nome_despacho(oficio, p.servidor, cidade, naming.extensao(p.despacho_assinado.name))}")
        if getattr(p, "comprovante_saque_transferencia", None):
            linhas.append(f"{servf}/{naming.nome_comprovante(oficio, p.servidor, cidade, naming.extensao(p.comprovante_saque_transferencia.name))}")
        for a in p.documentos_anexos.all():
            if not getattr(a, "arquivo", None):
                continue
            ext = naming.extensao(a.arquivo.name)
            nome = naming.nome_comprovante(oficio, p.servidor, cidade, ext) if a.tipo == "comprovante" else naming.nome_despacho(oficio, p.servidor, cidade, ext)
            linhas.append(f"{servf}/{nome}")
        for s in p.assinaturas.all():
            if not getattr(s, "arquivo_assinado", None):
                continue
            ext = naming.extensao(s.arquivo_assinado.name) or "pdf"
            if s.tipo == "rt":
                linhas.append(f"{servf}/{naming.nome_relatorio_tecnico(oficio, p.servidor, cidade, ext)}")
            elif s.tipo == "db":
                linhas.append(f"{servf}/{naming.nome_diario_bordo(oficio, p.servidor, cidade, ext)}")

    return linhas


def planejar_evento(evento) -> list[str]:
    linhas: list[str] = []
    for oficio in evento.oficios.all():
        linhas.extend(planejar_oficio(oficio))
    return linhas


# ---------------------------------------------------------------------------
# Reorganização em massa (usada pelo comando e pelo botão da UI)
# ---------------------------------------------------------------------------

def reorganizar_tudo(evento_id: int | None = None) -> dict:
    """Reorganiza todos os eventos (+ ofícios avulsos) no Drive.

    Retorna contagens: ``{"eventos", "avulsos", "erros"}``.
    """
    from eventos.models import Evento
    from oficios.models import Oficio

    resumo = {"eventos": 0, "avulsos": 0, "erros": 0}

    eventos = Evento.objects.all()
    if evento_id is not None:
        eventos = eventos.filter(pk=evento_id)
    for evento in eventos.iterator():
        try:
            organizar_evento(evento)
            resumo["eventos"] += 1
        except Exception as exc:  # noqa: BLE001
            resumo["erros"] += 1
            logger.error("[Drive] erro ao reorganizar evento %s: %s", evento.pk, exc, exc_info=True)

    if evento_id is None:
        for oficio in Oficio.objects.filter(evento__isnull=True).iterator():
            try:
                organizar_oficio(oficio)
                resumo["avulsos"] += 1
            except Exception as exc:  # noqa: BLE001
                resumo["erros"] += 1
                logger.error("[Drive] erro ao reorganizar ofício avulso %s: %s", oficio.pk, exc, exc_info=True)

    return resumo
