"""Organizador da árvore de pastas/arquivos no Google Drive.

Estrutura-alvo (a partir da pasta raiz escolhida pelo usuário):

    Ofícios/ Planos de trabalho/ Ordens de serviço/ Termos/ Justificativas/
        Solicitações de Viagem/
        <ofício ou item>/arquivo.pdf                 <- CANÔNICO (arquivo real),
        sempre aqui, tenha o documento evento ou não.
    Prestação de contas dos ofícios sem evento seguem dentro da própria
    pasta do ofício (``Ofícios/<pasta_oficio>/Prestação de contas/...``).

    Eventos/
      <Tipo - Cidade - Período>/                    (Cidade em Title Case)
        <Ofício NN protocolo ... Servidores (Cidade)>/
          Ofício NN-AAAA ... (Cidade).pdf            (ATALHO -> Ofícios/...)
          Justificativa ...                          (ATALHO -> Justificativas/...)
          Termos/ Termo de autorização ... Servidor (Cidade).pdf  (ATALHO -> Termos/...)
          Prestação de contas/
            Prestação <Servidor>/ ... (RT, diário, despacho, comprovante)
        Ordem de serviço ...                    (ATALHO -> Ordens de serviço/...; nível do evento)
        Plano de trabalho PP-AAAA ... (Cidade).pdf  (ATALHO -> Planos de trabalho/...; nível do evento)
        Solicitação de Viagem - ... (ATALHO -> Solicitações de Viagem/...; nível do evento)
        Convite (Cidade).<ext>                       (EventoAnexo; nível do evento)
    Prestações de contas/  <- atalhos de pasta p/ cada "Prestação <Servidor>"

O canônico (arquivo real) vive SEMPRE na pasta global do tipo — dentro de
Eventos/ só existem ATALHOS, para facilitar a navegação por evento sem
duplicar conteúdo.

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

def _evento_cancelado(evento) -> bool:
    from eventos.models import Evento

    return getattr(evento, "status", None) == Evento.STATUS_CANCELADO


def _pasta_evento_folder(client, evento) -> str:
    """Pasta do evento — em ``Eventos/`` normalmente, ou em ``Eventos cancelados/``
    quando ``evento.status == CANCELADO``.

    Se a pasta já existir do lado ERRADO (evento acabou de ser cancelado e já
    tinha sido organizado antes, ou — mais raro — o cancelamento foi revertido
    manualmente editando o campo ``status``), move em vez de duplicar.
    """
    raiz = _raiz()
    nome_pasta = naming.pasta_evento(evento)
    cancelado = _evento_cancelado(evento)
    nome_pai_certo = naming.PASTA_EVENTOS_CANCELADOS if cancelado else naming.PASTA_EVENTOS
    nome_pai_errado = naming.PASTA_EVENTOS if cancelado else naming.PASTA_EVENTOS_CANCELADOS

    pai_errado = client.get_or_create_pasta(nome_pai_errado, raiz)
    existente_errado = client.buscar_pasta_por_nome(nome_pasta, pai_errado)
    pai_certo = client.get_or_create_pasta(nome_pai_certo, raiz)
    if existente_errado:
        client.mover_renomear(existente_errado, nome_pasta, pai_certo)
        return existente_errado

    return client.get_or_create_pasta(nome_pasta, pai_certo)


def _pasta_tipo_global(client, tipo: str) -> str:
    raiz = _raiz()
    return client.get_or_create_pasta(naming.pasta_tipo(tipo), raiz)


def _oficio_folder_no_evento(client, tipo: str, oficio, servidores) -> str:
    """Pasta de tipo global + subpasta do ofício (caso sem evento)."""
    tipo_folder = _pasta_tipo_global(client, tipo)
    if oficio is not None:
        cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
        return client.get_or_create_pasta(naming.pasta_oficio(oficio, servidores, cidade), tipo_folder)
    return tipo_folder


def _oficio_folder_com_evento(client, evento, oficio, servidores) -> str:
    ev = _pasta_evento_folder(client, evento)
    if oficio is not None:
        cidade = naming.cidade_evento(evento, oficio)
        return client.get_or_create_pasta(naming.pasta_oficio(oficio, servidores, cidade), ev)
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


def _localizar_artefato_anterior(artefato):
    """``DocumentoArtefato`` anterior mais recente na MESMA posição lógica (mesmo
    ofício/evento/servidor + tipo + formato) que já tem arquivo no Drive.

    ``DocumentoArtefato`` é um registro histórico imutável: cada edição do
    documento gera uma linha NOVA (hash diferente). Sem isso, cada edição
    criaria um segundo arquivo no Drive em vez de sobrescrever o já existente.
    """
    from documentos.models import DocumentoArtefato

    qs = (
        DocumentoArtefato.objects.filter(tipo=artefato.tipo, formato=artefato.formato)
        .exclude(pk=artefato.pk)
        .exclude(drive_arquivo__isnull=True)
    )
    if artefato.oficio_id:
        qs = qs.filter(oficio_id=artefato.oficio_id)
    else:
        qs = qs.filter(oficio__isnull=True, evento_id=artefato.evento_id)
    if artefato.servidor_id:
        qs = qs.filter(servidor_id=artefato.servidor_id)
    else:
        qs = qs.filter(servidor__isnull=True)
    return qs.order_by("-criado_em").first()


def _arquivo_inacessivel(exc) -> bool:
    """True quando o erro indica que não dá pra mexer no file_id atual — 404
    (apagado) ou 403 ``insufficientFilePermissions`` (o arquivo existe mas a
    conta conectada não tem permissão pra movê-lo/editá-lo — ex.: dono
    diferente, ou tentativa de mover entre Drives Compartilhados sem acesso
    de gerente num dos dois lados). Nos dois casos o tratamento é o mesmo:
    considerar o file_id perdido e criar um arquivo novo, que a conta
    conectada vai possuir de verdade — em vez de travar a sincronização.
    """
    status = getattr(exc.resp, "status", None)
    if status == 404:
        return True
    if status == 403:
        # HttpError.__str__ não inclui o corpo da resposta — o motivo
        # ("insufficientFilePermissions") só está em .content (bytes/JSON).
        conteudo = getattr(exc, "content", b"") or b""
        if isinstance(conteudo, bytes):
            conteudo = conteudo.decode("utf-8", errors="ignore")
        return "insufficientFilePermissions" in conteudo
    return False


def _persistir_artefato(artefato, pasta_id: str, nome: str, *, atalho_pasta_id: str | None = None) -> tuple[str, str] | None:
    from googleapiclient.errors import HttpError

    from .models import DriveArquivo

    client = get_client()
    mime = mimetype_para_formato(artefato.formato)
    reg = DriveArquivo.objects.filter(artefato=artefato).first()

    if reg and reg.file_id and not reg.mock:
        try:
            client.mover_renomear(reg.file_id, nome, pasta_id)
            reg.nome = nome
            _sync_atalho(client, reg, nome, reg.file_id, atalho_pasta_id)
            reg.save()
            return reg.file_id, reg.url
        except HttpError as exc:
            if not _arquivo_inacessivel(exc):
                raise
            # O arquivo foi apagado do Drive (fora do app, ou por uma limpeza
            # anterior) OU a conta conectada perdeu permissão sobre ele (dono
            # diferente, movido pra fora do alcance) — nos dois casos o
            # registro local não serve mais: trata como inexistente e recria
            # abaixo em vez de travar a sincronização.
            logger.warning(
                "[Drive] file_id %s do artefato %s inacessível (apagado ou sem permissão); recriando",
                reg.file_id, artefato.pk,
            )
            reg.file_id = ""

    conteudo = _ler_filefield(getattr(artefato, "arquivo", None))
    if conteudo is None:
        return None

    anterior = _localizar_artefato_anterior(artefato)
    if anterior is not None:
        reg_anterior = anterior.drive_arquivo
        if reg_anterior.file_id and not reg_anterior.mock:
            # Documento editado e regerado: sobrescreve o arquivo já existente no
            # Drive (mesmo file_id) em vez de duplicar.
            try:
                file_id, url = client.atualizar_conteudo(
                    reg_anterior.file_id, nome, conteudo, mime, pasta_id=pasta_id
                )
                reg_anterior.artefato = artefato
                reg_anterior.nome, reg_anterior.mock = nome, is_mock()
                _sync_atalho(client, reg_anterior, nome, file_id, atalho_pasta_id)
                reg_anterior.save()
                return file_id, url
            except HttpError as exc:
                if not _arquivo_inacessivel(exc):
                    raise
                logger.warning(
                    "[Drive] file_id %s do artefato anterior %s inacessível (apagado ou "
                    "sem permissão); criando arquivo novo para %s",
                    reg_anterior.file_id, anterior.pk, artefato.pk,
                )

    # Rede de segurança: antes de criar um arquivo novo, confere se já não existe
    # um com esse nome na pasta canônica (registro local perdido/dessincronizado,
    # execuções concorrentes de "Reorganizar" etc.) — evita duplicar.
    existente_id = client.buscar_arquivo_por_nome(nome, pasta_id)
    if existente_id:
        try:
            file_id, url = client.atualizar_conteudo(existente_id, nome, conteudo, mime, pasta_id=pasta_id)
        except HttpError as exc:
            if not _arquivo_inacessivel(exc):
                raise
            # Mesmo caso das outras recriações: o arquivo achado por nome não
            # está mais acessível de verdade (apagado ou sem permissão entre a
            # busca e a atualização).
            logger.warning(
                "[Drive] arquivo %s achado por nome ficou inacessível; criando novo para artefato %s",
                existente_id, artefato.pk,
            )
            file_id, url = client.upload(nome, conteudo, mime, pasta_id=pasta_id)
    else:
        file_id, url = client.upload(nome, conteudo, mime, pasta_id=pasta_id)

    if not reg:
        reg = DriveArquivo(artefato=artefato)
    reg.file_id, reg.url, reg.nome = file_id, url, nome
    reg.mime_type, reg.mock = mime, is_mock()
    _sync_atalho(client, reg, nome, file_id, atalho_pasta_id)
    reg.save()
    return file_id, url


def _cancelado(*, oficio=None, evento=None) -> bool:
    """``True`` quando o dono do documento está cancelado.

    ``DocumentoArtefato`` não tem FK direta pra ``OrdemServico``/``PlanoTrabalho``/
    ``TermoAutorizacao`` — mas ``oficio.cancelado`` já cobre ofício, termo e OS
    (os 3 são sempre cancelados juntos, seja via cancelamento direto do ofício,
    seja via cascata de ``Evento.cancelar()``). ``evento.status`` cobre plano de
    trabalho e anexos/solicitações do evento (que não têm ofício).
    """
    if oficio is not None and getattr(oficio, "cancelado", False):
        return True
    if evento is not None and _evento_cancelado(evento):
        return True
    return False


def _derivar_nome_artefato(tipo, formato, oficio, servidor, servidores, cidade) -> str:
    if oficio is None:
        suf = naming._suf_cidade(cidade)
        rotulo = {
            "plano_trabalho": "Plano de Trabalho",
            "ordem_servico": "Ordem de Serviço",
            "termo_autorizacao": "Termo de autorização",
            "justificativa": "Justificativa",
        }.get(tipo, "Ofício")
        return naming._arquivo(f"{rotulo}{suf}", formato)
    if tipo == "termo_autorizacao":
        return naming.nome_termo(oficio, servidor, cidade, formato)
    if tipo == "ordem_servico":
        # Fallback raríssimo: só ocorre pra um DocumentoArtefato antigo sem
        # nome_drive salvo (o caminho normal já grava nome_drive na criação,
        # ver ordens_servico.services._persistir_ordem_servico_artefato).
        ordem = oficio.ordens_servico.first()
        if ordem is not None:
            return naming.nome_os(ordem, formato)
        return naming._arquivo(f"Ordem de Serviço{naming._suf_cidade(cidade)}", formato)
    if tipo == "justificativa":
        return naming.nome_justificativa(oficio, cidade, formato)
    if tipo == "plano_trabalho":
        # Fallback raríssimo (nome_drive ausente e evento não localizável).
        return naming._arquivo(f"Plano de Trabalho{naming._suf_cidade(cidade)}", formato)
    return naming.nome_oficio(oficio, servidores, cidade, formato)


def organizar_artefato(artefato) -> tuple[str, str] | None:
    """Coloca um ``DocumentoArtefato`` na pasta certa (canônico + atalho global).

    Só o PDF sobe ao Drive — DOCX/XLSX gerados a partir do mesmo documento ficam
    só no sistema local (evita duplicidade de formato nas pastas do Drive).
    """
    if (artefato.formato or "pdf").lower() != "pdf":
        return None
    client = get_client()
    tipo = artefato.tipo or "oficio"
    formato = artefato.formato or "pdf"
    oficio = getattr(artefato, "oficio", None)
    evento = getattr(artefato, "evento", None) or (getattr(oficio, "evento", None) if oficio else None)
    servidores = list(oficio.servidores.all()) if oficio is not None else []
    cidade = naming.cidade_evento(evento, oficio)

    if tipo == "ordem_servico" and oficio is not None and oficio.ordens_servico.exists():
        # NUNCA confia no nome_drive salvo pra OS: ele é gravado uma vez, na
        # criação do artefato, e artefatos de OS são deduplicados por hash de
        # conteúdo (_persistir_ordem_servico_artefato) — então uma OS gerada
        # há semanas, antes de qualquer ajuste no formato do nome (ou antes de
        # um novo ofício ser vinculado à mesma OS, mudando destino/período/
        # servidores), fica com o nome ERRADO pra sempre, porque reorganizar
        # de novo nunca recalcula, só reusa o que já está no banco. A OS
        # recalcula sempre, a partir do estado ATUAL da própria OrdemServico.
        ordem = oficio.ordens_servico.first()
        nome = naming.nome_os(ordem, formato)
    elif tipo == "plano_trabalho" and evento is not None and evento.planos_trabalho.count() == 1:
        # Mesmo raciocínio da OS acima: nome_drive do plano é gravado uma vez
        # na criação (planos_trabalho.services._persistir_plano_artefato,
        # deduplicado por hash) e nunca recalculado ao reorganizar. Só dá pra
        # fazer isso com segurança quando o evento tem EXATAMENTE 1 plano —
        # com mais de um não tem como saber, só pelo artefato (sem FK direta
        # pra PlanoTrabalho), qual plano corresponde a qual artefato.
        nome = naming.nome_plano(evento.planos_trabalho.first(), formato)
    else:
        nome = (artefato.nome_drive or "").strip() or _derivar_nome_artefato(
            tipo, formato, oficio, getattr(artefato, "servidor", None), servidores, cidade
        )
    if _cancelado(oficio=oficio, evento=evento):
        nome = naming.com_sufixo_cancelado(nome)

    # Canônico: SEMPRE direto na pasta global do tipo (Ofícios/Termos/Planos de
    # trabalho/Ordens de serviço/Justificativas), sem subpasta — cada arquivo já
    # tem nome único o bastante (número, protocolo, servidores, cidade).
    canonica = _pasta_tipo_global(client, tipo)

    atalho_pasta = None
    if evento is not None:
        # Dentro de Eventos/, tudo é ATALHO apontando para o canônico acima.
        oficio_folder_evento = _oficio_folder_com_evento(client, evento, oficio, servidores)
        if tipo == "termo_autorizacao":
            atalho_pasta = _pasta_termos(client, oficio_folder_evento)
        elif tipo in ("ordem_servico", "plano_trabalho"):
            # OS e plano ficam diretamente na pasta do evento (não dentro do ofício).
            atalho_pasta = _pasta_evento_folder(client, evento)
        else:
            atalho_pasta = oficio_folder_evento

    return _persistir_artefato(artefato, canonica, nome, atalho_pasta_id=atalho_pasta)


# ---------------------------------------------------------------------------
# Persistência: arquivos externos (DriveArquivoExterno)
# ---------------------------------------------------------------------------

def _persistir_conteudo_externo(
    obj, conteudo: bytes, *, campo: str, pasta_id: str, nome: str, mime: str
) -> tuple[str, str] | None:
    """Miolo de ``colocar_arquivo_externo``, sem depender de um ``FileField``.

    Usada tanto pra arquivos locais (``colocar_arquivo_externo``) quanto pra
    conteúdo gerado na hora (ex.: a nota de motivo do cancelamento).
    """
    from googleapiclient.errors import HttpError

    from django.contrib.contenttypes.models import ContentType

    from .models import DriveArquivoExterno

    client = get_client()
    ct = ContentType.objects.get_for_model(obj.__class__)
    reg = DriveArquivoExterno.objects.filter(
        content_type=ct, object_id=obj.pk, campo=campo
    ).first()

    if reg and reg.file_id and not reg.mock:
        try:
            file_id, url = client.atualizar_conteudo(reg.file_id, nome, conteudo, mime, pasta_id=pasta_id)
            reg.url, reg.nome, reg.pasta_id = url, nome, pasta_id
            reg.mime_type, reg.mock = mime, is_mock()
            reg.save()
            return file_id, url
        except HttpError as exc:
            if not _arquivo_inacessivel(exc):
                raise
            # Mesmo caso de _persistir_artefato: o arquivo foi apagado do Drive,
            # ou a conta conectada perdeu permissão sobre ele — recria abaixo em
            # vez de travar a sincronização deste campo.
            logger.warning(
                "[Drive] file_id %s do arquivo externo %s#%s (%s) inacessível (apagado ou sem "
                "permissão); recriando",
                reg.file_id, obj.__class__.__name__, obj.pk, campo,
            )
            reg.file_id = ""

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


def colocar_arquivo_externo(obj, ff, *, campo: str, pasta_id: str, nome: str) -> tuple[str, str] | None:
    """Envia um ``FileField`` que não é ``DocumentoArtefato``, sempre com o conteúdo atual.

    Idempotente via ``DriveArquivoExterno`` (content_type + object_id + campo): um
    registro já existente tem seu CONTEÚDO sobrescrito (o arquivo local pode ter
    sido substituído), nunca um segundo arquivo criado para o mesmo campo.
    """
    if not ff:
        return None
    conteudo = _ler_filefield(ff)
    if conteudo is None:
        return None
    mime = _mime_por_nome(nome)
    return _persistir_conteudo_externo(obj, conteudo, campo=campo, pasta_id=pasta_id, nome=nome, mime=mime)


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
    # Convite/ofício solicitante ficam diretamente na pasta do evento.
    pasta_id = _pasta_evento_folder(client, evento)

    cidade = naming.cidade_evento(evento, oficio)
    ext = naming.extensao(anexo.arquivo.name)
    if anexo.tipo == "convite":
        nome = naming.nome_convite(cidade, ext, titulo=anexo.titulo)
    else:
        titulo = (anexo.titulo or anexo.get_tipo_display()).strip()
        nome = naming._arquivo(f"{titulo}{naming._suf_cidade(cidade)}", ext)
    if _cancelado(evento=evento):
        nome = naming.com_sufixo_cancelado(nome)
    colocar_arquivo_externo(anexo, anexo.arquivo, campo="arquivo", pasta_id=pasta_id, nome=nome)


def organizar_solicitacao_evento(doc) -> None:
    """``EventoDocumentoSolicitacao`` (ofício/documento solicitando a viagem) →
    pasta global "Solicitações de Viagem" (canônico) + atalho na pasta do
    evento, no mesmo nível de Ordem de Serviço/Plano de Trabalho — não é um
    anexo de prestação de contas.
    """
    evento = getattr(doc, "evento", None)
    if evento is None or not getattr(doc, "arquivo", None):
        return
    client = get_client()
    oficio = evento.oficios.first()
    cidade = naming.cidade_evento(evento, oficio)
    ext = naming.extensao(doc.arquivo.name)
    nome = naming.nome_solicitacao_viagem(evento, cidade, ext)
    if _cancelado(evento=evento):
        nome = naming.com_sufixo_cancelado(nome)

    canonica = _pasta_tipo_global(client, "solicitacao_viagem")
    resultado = colocar_arquivo_externo(doc, doc.arquivo, campo="arquivo", pasta_id=canonica, nome=nome)
    if resultado is None:
        return
    file_id, _url = resultado

    evento_folder = _pasta_evento_folder(client, evento)
    _atalho_pasta_externo(
        doc, campo="atalho_evento", nome=nome, target_id=file_id, pasta_id=evento_folder,
    )


def _prestacao_tem_conteudo(prestacao) -> bool:
    """True se há algo de fato para organizar no Drive.

    A ``PrestacaoContas`` é criada automaticamente (vazia, status pendente)
    assim que o ofício é salvo ou ganha servidores — antes de qualquer
    documento de prestação existir. Sem este filtro, todo save do ofício
    dispara chamadas ao Drive (criar pastas) só para não ter nada a enviar,
    e uma falha nessas chamadas aparece como erro de "prestação de contas"
    no meio do wizard do ofício, o que não faz sentido para quem só está
    editando o ofício.
    """
    if getattr(prestacao, "despacho_assinado", None):
        return True
    if getattr(prestacao, "comprovante_saque_transferencia", None):
        return True
    if prestacao.documentos_anexos.exists():
        return True
    if prestacao.assinaturas.exists():
        return True
    return False


def organizar_prestacao(prestacao) -> None:
    """Arquivos da ``PrestacaoContas`` na pasta do servidor + atalho global."""
    oficio = getattr(prestacao, "oficio", None)
    servidor = getattr(prestacao, "servidor", None)
    if oficio is None:
        return
    if not _prestacao_tem_conteudo(prestacao):
        return
    client = get_client()
    servidores = list(oficio.servidores.all())
    cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
    oficio_folder = _oficio_base_folder(client, oficio, servidores)
    prestacao_folder = _pasta_prestacao(client, oficio_folder)
    serv_folder = client.get_or_create_pasta(
        naming.pasta_prestacao_servidor(servidor), prestacao_folder
    )
    cancelado = _cancelado(oficio=oficio, evento=getattr(oficio, "evento", None))

    def _nome(builder, *args):
        nome = builder(*args)
        return naming.com_sufixo_cancelado(nome) if cancelado else nome

    if getattr(prestacao, "despacho_assinado", None):
        ext = naming.extensao(prestacao.despacho_assinado.name)
        colocar_arquivo_externo(
            prestacao, prestacao.despacho_assinado, campo="despacho_assinado",
            pasta_id=serv_folder, nome=_nome(naming.nome_despacho, oficio, servidor, cidade, ext),
        )
    if getattr(prestacao, "comprovante_saque_transferencia", None):
        ext = naming.extensao(prestacao.comprovante_saque_transferencia.name)
        colocar_arquivo_externo(
            prestacao, prestacao.comprovante_saque_transferencia,
            campo="comprovante_saque_transferencia",
            pasta_id=serv_folder, nome=_nome(naming.nome_comprovante, oficio, servidor, cidade, ext),
        )

    for anexo in prestacao.documentos_anexos.all():
        if not getattr(anexo, "arquivo", None):
            continue
        ext = naming.extensao(anexo.arquivo.name)
        if anexo.tipo == "comprovante":
            nome = _nome(naming.nome_comprovante, oficio, servidor, cidade, ext)
        else:
            nome = _nome(naming.nome_despacho, oficio, servidor, cidade, ext)
        colocar_arquivo_externo(anexo, anexo.arquivo, campo="arquivo", pasta_id=serv_folder, nome=nome)

    for assinatura in prestacao.assinaturas.all():
        if not getattr(assinatura, "arquivo_assinado", None):
            continue
        ext = naming.extensao(assinatura.arquivo_assinado.name) or "pdf"
        if assinatura.tipo == "rt":
            nome = _nome(naming.nome_relatorio_tecnico, oficio, servidor, cidade, ext)
        elif assinatura.tipo == "db":
            nome = _nome(naming.nome_diario_bordo, oficio, servidor, cidade, ext)
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


def organizar_motivo_cancelamento(evento) -> None:
    """Nota com o motivo do cancelamento, dentro da pasta do evento (já movida
    pra "Eventos cancelados/" por ``_pasta_evento_folder``). Não faz nada se o
    evento não estiver cancelado."""
    if not _evento_cancelado(evento):
        return
    client = get_client()
    pasta_id = _pasta_evento_folder(client, evento)
    quando = evento.cancelado_em.strftime("%d/%m/%Y %H:%M") if evento.cancelado_em else ""
    motivo = (evento.motivo_cancelamento or "").strip() or "(não informado)"
    linhas = [
        f"Evento cancelado em {quando}." if quando else "Evento cancelado.",
        "",
        "Motivo:",
        motivo,
    ]
    conteudo = "\n".join(linhas).encode("utf-8")
    _persistir_conteudo_externo(
        evento, conteudo, campo="motivo_cancelamento",
        pasta_id=pasta_id, nome=naming.NOME_MOTIVO_CANCELAMENTO, mime="text/plain",
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


def _garantir_ordens_servico(oficio) -> None:
    """Regenera (e persiste) a Ordem de Serviço vinculada ao ofício, se faltar.

    Usa ``gerar_os_pdf_response`` (contexto real da ``OrdemServico``, com os
    servidores efetivamente designados) — NUNCA ``gerar_resposta_ordem_servico_documento``,
    que gera uma versão RASCUNHO em branco (``em_elaboracao=True``, sem saber
    qual servidor foi designado) e não deve ir para o Drive.

    Só o "ofício âncora" (primeiro vinculado à OS) dispara a geração, evitando
    persistir a mesma OS várias vezes quando ela cobre vários ofícios.
    """
    try:
        from ordens_servico.services import gerar_os_pdf_response
    except Exception:
        return

    try:
        ordens = list(oficio.ordens_servico.all())
    except Exception:
        return
    for ordem in ordens:
        oficio_ancora = ordem.oficios.first()
        if oficio_ancora is None or oficio_ancora.pk != oficio.pk:
            continue
        if oficio.documentos_gerados.filter(tipo="ordem_servico").exists():
            continue
        try:
            gerar_os_pdf_response(ordem)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Drive] backfill ordem de serviço (OS %s) falhou: %s", ordem.pk, exc)


def _garantir_documento_oficio(oficio) -> None:
    """Regenera (e persiste) o ofício canônico e, se aplicável, a justificativa.

    A justificativa só é gerada quando é EXIGIDA e já está FINALIZADA — caso
    contrário o documento sairia com o texto em branco.
    """
    from documentos.services.types import DocumentoFormato

    if not oficio.documentos_gerados.filter(tipo="oficio").exists():
        try:
            from oficios.services import gerar_resposta_documento_oficio

            gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Drive] backfill ofício (oficio %s) falhou: %s", oficio.pk, exc)

    if not oficio.documentos_gerados.filter(tipo="justificativa").exists():
        try:
            from justificativas.models import Justificativa
            from justificativas.services import oficio_exige_justificativa

            justificativa = getattr(oficio, "justificativa", None)
            pronta = (
                justificativa is not None
                and justificativa.status == Justificativa.STATUS_FINALIZADA
                and (justificativa.texto or "").strip()
            )
            if oficio_exige_justificativa(oficio) and pronta:
                from oficios.services import gerar_resposta_justificativa_documento

                gerar_resposta_justificativa_documento(oficio, DocumentoFormato.PDF)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Drive] backfill justificativa (oficio %s) falhou: %s", oficio.pk, exc)


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

    for plano in planos:
        nome = naming.nome_plano(plano)
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

def _artefatos_mais_recentes(qs):
    """Deduplica ``DocumentoArtefato`` por (tipo, formato, servidor), mantendo só
    o mais recente de cada posição lógica.

    ``DocumentoArtefato`` é um histórico imutável (cada edição gera uma linha
    nova) e alguns registros antigos — de antes da deduplicação existir —
    ainda têm seu PRÓPRIO ``DriveArquivo`` (arquivo real independente). Sem
    este filtro, ``organizar_artefato`` reprocessaria TODOS eles e cada um
    renomearia seu próprio arquivo para o mesmo nome/pasta canônica,
    resultando em várias cópias do "mesmo" documento no Drive.
    """
    vistos = set()
    mais_recentes = []
    for artefato in qs:  # Meta.ordering = ["-criado_em"]: já vem do mais novo pro mais velho.
        chave = (artefato.tipo, artefato.formato, artefato.servidor_id)
        if chave in vistos:
            continue
        vistos.add(chave)
        mais_recentes.append(artefato)
    return mais_recentes


def organizar_oficio(oficio) -> None:
    """Organiza todos os artefatos e prestações de um ofício (+ backfill)."""
    from . import status

    _garantir_documento_oficio(oficio)
    _garantir_termos(oficio)
    _garantir_ordens_servico(oficio)
    for artefato in _artefatos_mais_recentes(oficio.documentos_gerados.all()):
        try:
            status.executar_e_rastrear(organizar_artefato, artefato)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar artefato %s: %s", artefato.pk, exc, exc_info=True)
    for prestacao in oficio.prestacoes_contas.all():
        try:
            status.executar_e_rastrear(organizar_prestacao, prestacao)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar prestação %s: %s", prestacao.pk, exc, exc_info=True)


def organizar_evento(evento) -> None:
    """Organiza ofícios, planos, anexos e solicitações de um evento."""
    from . import status

    _garantir_planos(evento)
    try:
        organizar_motivo_cancelamento(evento)
    except Exception as exc:
        logger.error("[Drive] erro ao gravar motivo de cancelamento do evento %s: %s", evento.pk, exc, exc_info=True)
    for oficio in evento.oficios.all():
        organizar_oficio(oficio)
    # Planos do evento sem ofício (não cobertos por organizar_oficio).
    for artefato in _artefatos_mais_recentes(evento.documentos_gerados.filter(oficio__isnull=True)):
        try:
            status.executar_e_rastrear(organizar_artefato, artefato)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar artefato %s: %s", artefato.pk, exc, exc_info=True)
    for anexo in evento.anexos.all():
        try:
            status.executar_e_rastrear(organizar_evento_anexo, anexo)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar anexo %s: %s", anexo.pk, exc, exc_info=True)
    for doc in evento.documentos_solicitacao.all():
        try:
            status.executar_e_rastrear(organizar_solicitacao_evento, doc)
        except Exception as exc:
            logger.error("[Drive] erro ao organizar solicitação %s: %s", doc.pk, exc, exc_info=True)


# ---------------------------------------------------------------------------
# Planejamento (dry-run): computa os caminhos sem tocar no Drive
# ---------------------------------------------------------------------------

def _caminho_base_oficio(oficio, servidores) -> str:
    evento = getattr(oficio, "evento", None)
    cidade = naming.cidade_evento(evento, oficio)
    if evento is not None:
        return f"{naming.PASTA_EVENTOS}/{naming.pasta_evento(evento)}/{naming.pasta_oficio(oficio, servidores, cidade)}"
    return f"{naming.pasta_tipo('oficio')}/{naming.pasta_oficio(oficio, servidores, cidade)}"


def _caminho_artefato(artefato, oficio, servidores, cidade) -> str:
    """Caminho do CANÔNICO (arquivo real) — sempre direto na pasta global do
    tipo, sem subpasta (dentro de Eventos/ existe só um atalho)."""
    tipo = artefato.tipo or "oficio"
    formato = artefato.formato or "pdf"
    nome = (artefato.nome_drive or "").strip() or _derivar_nome_artefato(
        tipo, formato, oficio, getattr(artefato, "servidor", None), servidores, cidade
    )
    return f"{naming.pasta_tipo(tipo)}/{nome}"


def planejar_oficio(oficio) -> list[str]:
    """Lista ``pasta/arquivo`` que seriam criados/movidos para o ofício (sem I/O)."""
    servidores = list(oficio.servidores.all())
    cidade = naming.cidade_evento(getattr(oficio, "evento", None), oficio)
    base = _caminho_base_oficio(oficio, servidores)
    linhas: list[str] = []

    for art in _artefatos_mais_recentes(oficio.documentos_gerados.all()):
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

def reorganizar_tudo(evento_id: int | None = None, progress=None) -> dict:
    """Reorganiza todos os eventos (+ ofícios sem evento) no Drive.

    ``progress`` (opcional) é chamado como ``progress(eventos_processados, total)``
    após cada evento, para acompanhamento em segundo plano.

    Retorna contagens: ``{"eventos", "avulsos", "erros"}``.
    """
    from eventos.models import Evento
    from oficios.models import Oficio

    resumo = {"eventos": 0, "avulsos": 0, "erros": 0}

    eventos = Evento.objects.all()
    if evento_id is not None:
        eventos = eventos.filter(pk=evento_id)
    total = eventos.count()
    processados = 0
    if progress:
        progress(0, total)
    for evento in eventos.iterator():
        try:
            organizar_evento(evento)
            resumo["eventos"] += 1
        except Exception as exc:  # noqa: BLE001
            resumo["erros"] += 1
            logger.error("[Drive] erro ao reorganizar evento %s: %s", evento.pk, exc, exc_info=True)
        processados += 1
        if progress:
            progress(processados, total)

    if evento_id is None:
        for oficio in Oficio.objects.filter(evento__isnull=True).iterator():
            try:
                organizar_oficio(oficio)
                resumo["avulsos"] += 1
            except Exception as exc:  # noqa: BLE001
                resumo["erros"] += 1
                logger.error("[Drive] erro ao reorganizar ofício avulso %s: %s", oficio.pk, exc, exc_info=True)

    return resumo
