"""Organizador da árvore de pastas/arquivos no Google Drive.

Estrutura-alvo (a partir da pasta raiz escolhida pelo usuário):

    Eventos/
      <Tipo - Cidade - Período>/
        <Ofício NN protocolo ... Servidores>/
          Ofício NN-AAAA ... (Cidade).pdf            (canônico)
          Plano de trabalho PP-AAAA ... (Cidade).pdf (canônico; PP = nº do plano)
          Ordem de serviço ...                       (canônico)
          Justificativa ...                          (canônico)
          Convite (Cidade).<ext>                     (EventoAnexo)
          Termos/ Termo de autorização ... Servidor (Cidade).pdf
          Prestação de contas/
            Anexo solicitação ... (Cidade).<ext>
            Prestação <Servidor>/ ... (RT, diário, despacho, comprovante)
    Ofícios/ Planos de trabalho/ Ordens de serviço/ Termos/ Justificativas/
        <- agregadoras globais por tipo (ATALHOS p/ os canônicos com evento)
    Prestações de contas/  <- atalhos de pasta p/ cada "Prestação <Servidor>"

Documentos SEM evento têm o canônico direto na pasta de tipo global
(``Planos de trabalho/<ofício>/arquivo``) — não existe mais "Avulsos".

Tudo é idempotente: reexecutar move/renomeia (e reusa atalhos) em vez de
duplicar (reusa ``get_or_create_pasta`` e os registros ``DriveArquivo`` /
``DriveArquivoExterno``).
"""

from __future__ import annotations

import logging
import mimetypes

from . import naming
from .services import get_client, is_mock, mimetype_para_formato

logger = logging.getLogger(__name__)

_SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


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

def _pasta_evento_folder(client, evento) -> str:
    raiz = _raiz()
    eventos = client.get_or_create_pasta(naming.PASTA_EVENTOS, raiz)
    return client.get_or_create_pasta(naming.pasta_evento(evento), eventos)


def _pasta_tipo_global(client, tipo: str) -> str:
    raiz = _raiz()
    return client.get_or_create_pasta(naming.pasta_tipo(tipo), raiz)


def _oficio_folder_no_evento(client, tipo: str, oficio, servidores) -> str:
    """Pasta de tipo global + subpasta do ofício (caso sem evento)."""
    tipo_folder = _pasta_tipo_global(client, tipo)
    if oficio is not None:
        return client.get_or_create_pasta(naming.pasta_oficio(oficio, servidores), tipo_folder)
    return tipo_folder


def _oficio_folder_com_evento(client, evento, oficio, servidores) -> str:
    ev = _pasta_evento_folder(client, evento)
    if oficio is not None:
        return client.get_or_create_pasta(naming.pasta_oficio(oficio, servidores), ev)
    return ev


def _oficio_base_folder(client, oficio, servidores) -> str:
    """Pasta canônica de um ofício (evento → Eventos/...; senão → Ofícios/...)."""
    evento = getattr(oficio, "evento", None)
    if evento is not None:
        return _oficio_folder_com_evento(client, evento, oficio, servidores)
    return _oficio_folder_no_evento(client, "oficio", oficio, servidores)


def _pasta_prestacao(client, oficio_folder: str) -> str:
    return client.get_or_create_pasta(naming.PASTA_PRESTACAO, oficio_folder)


def _pasta_termos(client, oficio_folder: str) -> str:
    return client.get_or_create_pasta(naming.PASTA_TERMOS, oficio_folder)


# ---------------------------------------------------------------------------
# Persistência: DocumentoArtefato (DriveArquivo) + atalho global por tipo
# ---------------------------------------------------------------------------

def _sync_atalho(client, reg, nome: str, target_id: str, atalho_pasta_id: str | None) -> None:
    if not atalho_pasta_id:
        return
    novo = client.criar_ou_atualizar_atalho(
        nome, target_id, atalho_pasta_id, existing_id=reg.atalho_id or None
    )
    reg.atalho_id = novo
    reg.atalho_pasta_id = atalho_pasta_id


def _persistir_artefato(artefato, pasta_id: str, nome: str, *, atalho_pasta_id: str | None = None) -> tuple[str, str] | None:
    from .models import DriveArquivo

    client = get_client()
    mime = mimetype_para_formato(artefato.formato)
    reg = DriveArquivo.objects.filter(artefato=artefato).first()

    if reg and reg.file_id and not reg.mock:
        client.mover_renomear(reg.file_id, nome, pasta_id)
        reg.nome = nome
        _sync_atalho(client, reg, nome, reg.file_id, atalho_pasta_id)
        reg.save()
        return reg.file_id, reg.url

    conteudo = _ler_filefield(getattr(artefato, "arquivo", None))
    if conteudo is None:
        return None
    file_id, url = client.upload(nome, conteudo, mime, pasta_id=pasta_id)

    if not reg:
        reg = DriveArquivo(artefato=artefato)
    reg.file_id, reg.url, reg.nome = file_id, url, nome
    reg.mime_type, reg.mock = mime, is_mock()
    _sync_atalho(client, reg, nome, file_id, atalho_pasta_id)
    reg.save()
    return file_id, url


def _derivar_nome_artefato(tipo, formato, oficio, servidor, servidores, cidade) -> str:
    if oficio is None:
        suf = naming._suf_cidade(cidade)
        rotulo = {
            "plano_trabalho": "Plano de trabalho",
            "ordem_servico": "Ordem de serviço",
            "termo_autorizacao": "Termo de autorização",
            "justificativa": "Justificativa",
        }.get(tipo, "Ofício")
        return naming._arquivo(f"{rotulo}{suf}", formato)
    if tipo == "termo_autorizacao":
        return naming.nome_termo(oficio, servidor, cidade, formato)
    if tipo == "ordem_servico":
        return naming.nome_os(oficio, servidores, cidade, formato)
    if tipo == "justificativa":
        return naming.nome_justificativa(oficio, cidade, formato)
    if tipo == "plano_trabalho":
        # planos sempre têm nome_drive; fallback genérico caso falte.
        return naming._arquivo(f"Plano de trabalho{naming._suf_cidade(cidade)}", formato)
    return naming.nome_oficio(oficio, servidores, cidade, formato)


def organizar_artefato(artefato) -> tuple[str, str] | None:
    """Coloca um ``DocumentoArtefato`` na pasta certa (canônico + atalho global)."""
    client = get_client()
    tipo = artefato.tipo or "oficio"
    formato = artefato.formato or "pdf"
    oficio = getattr(artefato, "oficio", None)
    evento = getattr(artefato, "evento", None) or (getattr(oficio, "evento", None) if oficio else None)
    servidores = list(oficio.servidores.all()) if oficio is not None else []
    cidade = naming.cidade_evento(evento, oficio)

    nome = (artefato.nome_drive or "").strip() or _derivar_nome_artefato(
        tipo, formato, oficio, getattr(artefato, "servidor", None), servidores, cidade
    )

    if evento is not None:
        oficio_folder = _oficio_folder_com_evento(client, evento, oficio, servidores)
        if tipo == "termo_autorizacao":
            canonica = _pasta_termos(client, oficio_folder)
        else:
            canonica = oficio_folder
        atalho_pasta = _pasta_tipo_global(client, tipo)
    else:
        # Sem evento: canônico já vive na pasta de tipo global (sem atalho).
        if tipo == "termo_autorizacao":
            base = _oficio_folder_no_evento(client, tipo, oficio, servidores)
            canonica = base
        else:
            canonica = _oficio_folder_no_evento(client, tipo, oficio, servidores)
        atalho_pasta = None

    return _persistir_artefato(artefato, canonica, nome, atalho_pasta_id=atalho_pasta)


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


def _atalho_pasta_externo(obj, *, campo: str, nome: str, target_id: str, pasta_id: str) -> str | None:
    """Cria/atualiza um atalho (de pasta) rastreado em ``DriveArquivoExterno``."""
    from django.contrib.contenttypes.models import ContentType

    from .models import DriveArquivoExterno

    client = get_client()
    ct = ContentType.objects.get_for_model(obj.__class__)
    reg = DriveArquivoExterno.objects.filter(
        content_type=ct, object_id=obj.pk, campo=campo
    ).first()
    atalho_id = client.criar_ou_atualizar_atalho(
        nome, target_id, pasta_id, existing_id=(reg.file_id if reg and reg.file_id else None)
    )
    if reg:
        reg.file_id, reg.nome, reg.pasta_id, reg.mock = atalho_id, nome, pasta_id, is_mock()
        reg.save()
    else:
        DriveArquivoExterno.objects.create(
            content_type=ct, object_id=obj.pk, campo=campo,
            file_id=atalho_id, nome=nome, pasta_id=pasta_id,
            mime_type=_SHORTCUT_MIME, mock=is_mock(),
        )
    return atalho_id


# ---------------------------------------------------------------------------
# Anexos de evento / prestação
# ---------------------------------------------------------------------------

def organizar_evento_anexo(anexo) -> None:
    """``EventoAnexo`` (convite, ofício solicitante, comprovante) → pasta do ofício."""
    evento = getattr(anexo, "evento", None)
    if evento is None or not getattr(anexo, "arquivo", None):
        return
    client = get_client()
    oficio = evento.oficios.first()
    pasta_id = _oficio_folder_com_evento(client, evento, oficio, list(oficio.servidores.all()) if oficio else [])

    cidade = naming.cidade_evento(evento, oficio)
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
    oficio_folder = _oficio_base_folder(client, oficio, servidores)
    prestacao_folder = _pasta_prestacao(client, oficio_folder)
    cidade = naming.cidade_evento(evento, oficio)
    ext = naming.extensao(doc.arquivo.name)

    prestacoes = list(oficio.prestacoes_contas.all())
    if len(prestacoes) == 1:
        p = prestacoes[0]
        nome = naming.nome_anexo_solicitacao(oficio, p.servidor, p.numero_solicitacao, cidade, ext)
    else:
        base = f"Anexo solicitação Ofício {naming.num_doc(oficio.numero, oficio.ano)}".strip()
        nome = naming._arquivo(f"{base}{naming._suf_cidade(cidade)}", ext)
    colocar_arquivo_externo(doc, doc.arquivo, campo="arquivo", pasta_id=prestacao_folder, nome=nome)


def organizar_prestacao(prestacao) -> None:
    """Arquivos da ``PrestacaoContas`` na pasta do servidor + atalho global."""
    oficio = getattr(prestacao, "oficio", None)
    servidor = getattr(prestacao, "servidor", None)
    if oficio is None:
        return
    client = get_client()
    servidores = list(oficio.servidores.all())
    cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
    oficio_folder = _oficio_base_folder(client, oficio, servidores)
    prestacao_folder = _pasta_prestacao(client, oficio_folder)
    serv_folder = client.get_or_create_pasta(
        naming.pasta_prestacao_servidor(servidor), prestacao_folder
    )

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

    for anexo in prestacao.documentos_anexos.all():
        if not getattr(anexo, "arquivo", None):
            continue
        ext = naming.extensao(anexo.arquivo.name)
        if anexo.tipo == "comprovante":
            nome = naming.nome_comprovante(oficio, servidor, cidade, ext)
        else:
            nome = naming.nome_despacho(oficio, servidor, cidade, ext)
        colocar_arquivo_externo(anexo, anexo.arquivo, campo="arquivo", pasta_id=serv_folder, nome=nome)

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

    # Atalho de pasta na agregadora global "Prestações de contas".
    raiz = _raiz()
    global_folder = client.get_or_create_pasta(naming.PASTA_PRESTACOES_GLOBAL, raiz)
    _atalho_pasta_externo(
        prestacao, campo="atalho_prestacao",
        nome=naming.nome_atalho_prestacao(oficio, servidor, cidade),
        target_id=serv_folder, pasta_id=global_folder,
    )


# ---------------------------------------------------------------------------
# Backfill: regera termos/planos que nunca foram persistidos
# ---------------------------------------------------------------------------

def _garantir_termos(oficio) -> None:
    """Regenera (e persiste) termos de servidores que ainda não têm artefato.

    A persistência acontece dentro de ``gerar_termo_um`` (dedupe por hash).
    """
    from documentos.services.types import DocumentoFormato

    try:
        from termos.services import gerar_termo_um, listar_servidores_com_termo
    except Exception:
        return

    existentes = set(
        oficio.documentos_gerados.filter(tipo="termo_autorizacao").values_list("servidor_id", flat=True)
    )
    for servidor in listar_servidores_com_termo(oficio):
        if servidor.pk in existentes:
            continue
        try:
            gerar_termo_um(oficio, servidor, DocumentoFormato.PDF)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Drive] backfill termo (oficio %s, serv %s) falhou: %s", oficio.pk, servidor.pk, exc)


def _garantir_planos(evento) -> None:
    """Regenera (e persiste) planos do evento que ainda não têm artefato.

    A persistência acontece dentro de ``gerar_plano_documento`` (dedupe por hash).
    """
    from documentos.models import DocumentoArtefato
    from documentos.services.types import DocumentoFormato

    try:
        from planos_trabalho.services import gerar_plano_documento
    except Exception:
        return

    try:
        planos = list(evento.planos_trabalho.all())
    except Exception:
        return

    oficio = evento.oficios.first()
    cidade = naming.cidade_evento(evento, oficio)
    for plano in planos:
        nome = naming.nome_plano(plano, cidade, oficio=oficio)
        if DocumentoArtefato.objects.filter(
            evento=evento, tipo="plano_trabalho", nome_drive=nome
        ).exists():
            continue
        try:
            gerar_plano_documento(plano, DocumentoFormato.PDF)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Drive] backfill plano %s falhou: %s", getattr(plano, "pk", "?"), exc)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def organizar_oficio(oficio) -> None:
    """Organiza todos os artefatos e prestações de um ofício (+ backfill de termos)."""
    _garantir_termos(oficio)
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
    """Organiza ofícios, planos, anexos e solicitações de um evento."""
    _garantir_planos(evento)
    for oficio in evento.oficios.all():
        organizar_oficio(oficio)
    # Planos do evento sem ofício (não cobertos por organizar_oficio).
    for artefato in evento.documentos_gerados.filter(oficio__isnull=True):
        try:
            organizar_artefato(artefato)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar artefato %s: %s", artefato.pk, exc, exc_info=True)
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
        return f"{naming.PASTA_EVENTOS}/{naming.pasta_evento(evento)}/{naming.pasta_oficio(oficio, servidores)}"
    return f"{naming.pasta_tipo('oficio')}/{naming.pasta_oficio(oficio, servidores)}"


def _caminho_artefato(artefato, oficio, servidores, cidade) -> str:
    tipo = artefato.tipo or "oficio"
    formato = artefato.formato or "pdf"
    nome = (artefato.nome_drive or "").strip() or _derivar_nome_artefato(
        tipo, formato, oficio, getattr(artefato, "servidor", None), servidores, cidade
    )
    evento = getattr(artefato, "evento", None) or getattr(oficio, "evento", None)
    if evento is not None:
        base = f"{naming.PASTA_EVENTOS}/{naming.pasta_evento(evento)}/{naming.pasta_oficio(oficio, servidores)}"
        if tipo == "termo_autorizacao":
            return f"{base}/{naming.PASTA_TERMOS}/{nome}"
        return f"{base}/{nome}"
    base = naming.pasta_tipo(tipo)
    if oficio is not None:
        return f"{base}/{naming.pasta_oficio(oficio, servidores)}/{nome}"
    return f"{base}/{nome}"


def planejar_oficio(oficio) -> list[str]:
    """Lista ``pasta/arquivo`` que seriam criados/movidos para o ofício (sem I/O)."""
    servidores = list(oficio.servidores.all())
    cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
    base = _caminho_base_oficio(oficio, servidores)
    linhas: list[str] = []

    for art in oficio.documentos_gerados.all():
        linhas.append(_caminho_artefato(art, oficio, servidores, cidade))

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
    """Reorganiza todos os eventos (+ ofícios sem evento) no Drive.

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
