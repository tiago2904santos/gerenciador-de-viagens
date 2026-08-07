import hashlib

from django.db import models

from core.constraints import periodo_ordenado
from core.constraints import positivo
from core.managers import AreaScopedManager
from django.db.models import Q
from django.core.validators import FileExtensionValidator

from cadastros.models import Servidor
from cadastros.models import Viatura
from oficios.models import Oficio
from roteiros.models import RoteiroTrecho
from core.db_fields import EncryptedTextField
from core.uploads import validate_private_document_upload


PRESTACAO_DOCUMENTO_EXTENSOES = ["pdf", "png", "jpg", "jpeg"]


def prestacao_documento_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.pk or 'nova'}/{filename}"


def prestacao_documento_anexo_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/{filename}"


def assinatura_origem_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/assinaturas/origem_{instance.tipo}_{filename}"


def assinatura_png_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/assinaturas/png_{instance.tipo}_{filename}"


def assinatura_assinado_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/assinaturas/assinado_{instance.tipo}_{filename}"


class PrestacaoContas(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_EM_PREENCHIMENTO = "em_preenchimento"
    STATUS_ENVIADA = "enviada"
    STATUS_APROVADA = "aprovada"
    STATUS_REPROVADA = "reprovada"

    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_EM_PREENCHIMENTO, "Em preenchimento"),
        (STATUS_ENVIADA, "Enviada"),
        (STATUS_APROVADA, "Aprovada"),
        (STATUS_REPROVADA, "Reprovada"),
    ]

    # Uma prestação por ofício. Os dados compartilhados por todos os servidores
    # (texto do RT, diário de bordo do motorista, despacho, número do ofício)
    # ficam aqui; o que é individual de cada servidor fica em ``PrestacaoServidor``.
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prestacoes_contas",
        verbose_name="Area de trabalho",
    )
    oficio = models.OneToOneField(
        Oficio,
        on_delete=models.CASCADE,
        related_name="prestacao_contas",
    )
    # Cópia editável do roteiro (o que realmente ocorreu na viagem). Quando
    # preenchida, substitui o roteiro do ofício no diário sem alterar o ofício.
    roteiro_ajustado = models.ForeignKey(
        "roteiros.Roteiro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    despacho_assinado = models.FileField(
        "Despacho assinado do ofício",
        upload_to=prestacao_documento_upload_to,
        blank=True,
        validators=[FileExtensionValidator(PRESTACAO_DOCUMENTO_EXTENSOES)],
    )
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["area", "-criado_em"], name="prestacoes_area_criado_idx"),
        ]
        verbose_name = "Prestação de Contas"
        verbose_name_plural = "Prestações de Contas"

    def __str__(self):
        return f"Prestação — Ofício {self.oficio.numero_formatado}"

    def save(self, *args, **kwargs):
        if self.area_id is None:
            if self.oficio_id and self.oficio and self.oficio.area_id:
                self.area = self.oficio.area
            else:
                from core.tenancy import get_current_area

                self.area = get_current_area()
        super().save(*args, **kwargs)


class PrestacaoServidorAtivosManager(models.Manager):
    """Esconde as linhas removidas da equipe do ofício (`DB-06`).

    É o `_default_manager` **de propósito**. Django deriva o manager das relações
    reversas da classe do `_default_manager`
    (`django/db/models/fields/related_descriptors.py:641`), então
    `prestacao.servidores_prestacao.all()` e os `prefetch_related` **por string**
    (`view_common.py:257-262`, `views.py:730`, `selectors.py:100`) herdam o filtro
    sem que nenhum dos quinze pontos de leitura precise lembrar dele. A
    alternativa era espalhar `filter(removida_em__isnull=True)` à mão por seis
    apps — e os prefetch por string não teriam onde recebê-lo.

    É o oposto da escolha do `AreaScopedManager` (`core/managers.py`), e a
    diferença é o que decide: lá o `_default_manager` **precisa** ficar irrestrito,
    porque o recorte é do observador (a área ativa) e não pode vazar para o admin
    nem para `validate_unique`. Aqui o recorte é do próprio registro — a linha saiu
    da equipe, e isso é verdade para todo mundo que olhar.

    Quem precisa enxergar as removidas usa `PrestacaoServidor.todos`: o sinal que
    reconcilia a equipe e o comando `sincronizar_prestacao_servidores`. Fora
    desses dois, ver uma linha removida é bug, não necessidade.

    Duas consequências conhecidas e aceitas:

    - `UniqueConstraint.validate` sai do `_default_manager`, então um `ModelForm`
      que **criasse** `(prestacao, servidor)` não veria a linha removida e cairia
      em `IntegrityError` em vez de erro de formulário. Hoje não existe esse form
      — os dois de `forms.py` editam instância existente — e os `get_or_create` do
      par usam `todos`.
    - Em migração de dados este manager vira um `models.Manager()` puro
      (`db/migrations/state.py`, que só preserva `use_in_migrations`), então
      `PrestacaoServidor.objects` dentro de migração **não filtra**. É o que se
      quer: migração enxerga a tabela inteira.
    """

    def get_queryset(self):
        return super().get_queryset().filter(removida_em__isnull=True)


class PrestacaoServidor(models.Model):
    """Parte individual da prestação de um servidor dentro do ofício.

    Guarda o acompanhamento e o que muda de servidor para servidor: status,
    arquivamento/finalização, número da solicitação, comprovante de saque/
    transferência (via ``PrestacaoDocumentoAnexo``) e a assinatura do relatório
    técnico (via ``AssinaturaDocumento``). O texto do RT e o diário de bordo são
    compartilhados e ficam em ``PrestacaoContas``.
    """

    STATUS_PENDENTE = PrestacaoContas.STATUS_PENDENTE
    STATUS_EM_PREENCHIMENTO = PrestacaoContas.STATUS_EM_PREENCHIMENTO
    STATUS_ENVIADA = PrestacaoContas.STATUS_ENVIADA
    STATUS_APROVADA = PrestacaoContas.STATUS_APROVADA
    STATUS_REPROVADA = PrestacaoContas.STATUS_REPROVADA
    STATUS_CHOICES = PrestacaoContas.STATUS_CHOICES

    prestacao = models.ForeignKey(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="servidores_prestacao",
    )
    servidor = models.ForeignKey(
        Servidor,
        on_delete=models.CASCADE,
        related_name="prestacoes_servidor",
    )
    numero_solicitacao = models.CharField(
        "Número da solicitação",
        max_length=60,
        blank=True,
        default="",
    )
    # Sobrescreve, só para este servidor, o valor de diária exibido no RT dele
    # (ex.: quando ele recebeu por saque em vez de transferência e o valor
    # ficou diferente do padrão calculado para o ofício). Em branco usa o
    # valor compartilhado (``RelatorioTecnico.diaria``).
    # Valor que o servidor efetivamente recebeu, quando difere do liberado.
    # O caso típico é o saque: o caixa não entrega centavos, então de R$ 87,17
    # liberados o servidor saca R$ 87,00. Nunca mais do que o liberado — essa
    # é a regra que a validação protege (NOVO-10).
    diaria_valor_override = models.DecimalField(
        "Diária recebida por este servidor",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # Por que o valor difere ("(saque)", "(devolução parcial)"). Fica ao lado
    # do número no documento, como sempre esteve — antes os dois dividiam um
    # CharField só, e por isso "abc" chegava ao RT assinado.
    diaria_valor_override_observacao = models.CharField(
        "Observação sobre o valor recebido",
        max_length=255,
        blank=True,
        default="",
    )
    # Período em que as diárias ficam disponíveis para este servidor. As datas
    # são individuais porque a liberação pode ocorrer em dias diferentes.
    data_liberacao_diarias = models.DateField(
        "Data de liberação das diárias",
        null=True,
        blank=True,
    )
    prazo_limite_saque = models.DateField(
        "Prazo limite para saque",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    # Arquivar tira este servidor da lista de pendentes sem concluí-lo (aba
    # "Arquivados"); finalizar marca a prestação deste servidor como concluída
    # (aba "Finalizados"). São flags independentes do fluxo em ``status``.
    arquivada = models.BooleanField(default=False)
    arquivada_em = models.DateTimeField(null=True, blank=True)
    finalizada = models.BooleanField(default=False)
    finalizada_em = models.DateTimeField(null=True, blank=True)
    # `DB-06`: o servidor saiu da equipe do ofício mas já tinha entregue alguma
    # coisa — comprovante de saque, assinatura do RT, número da solicitação. A
    # linha some das telas (é o `objects` que decide isso) e nada é apagado; se
    # ele voltar para a equipe, a marca cai e tudo reaparece. Nulo = na equipe.
    removida_em = models.DateTimeField("Removida da equipe em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    #: Ordem importa: o primeiro declarado vira o `_default_manager`, e é dele que
    #: saem as relações reversas. `default_manager_name` abaixo torna isso
    #: explícito em vez de acidental — ver `PrestacaoServidorAtivosManager`.
    objects = PrestacaoServidorAtivosManager()
    todos = models.Manager()

    class Meta:
        default_manager_name = "objects"
        ordering = ["prestacao", "pk"]
        verbose_name = "Servidor da prestação"
        verbose_name_plural = "Servidores da prestação"
        indexes = [
            models.Index(fields=["arquivada", "finalizada", "data_liberacao_diarias"], name="prest_serv_aba_idx"),
            models.Index(fields=["status"], name="prest_serv_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["prestacao", "servidor"],
                name="unique_servidor_por_prestacao",
            ),
            # O teto (não passar do liberado) depende do roteiro e fica no
            # serviço. O piso não depende de nada: dinheiro recebido é
            # positivo, e disso o banco dá conta.
            #
            # `DB-07`: era `check=`, depreciado desde o Django 5.1 e removido no
            # 6.0 — o import do modelo já emitia `RemovedInDjango60Warning`. A
            # fábrica de `core/constraints.py` produz exatamente a mesma condição,
            # então a migração que renomeia isto não toca em dado nenhum.
            positivo("diaria_valor_override", name="prest_serv_diaria_recebida_positiva"),
            # `DB-07`: o prazo de saque é calculado a partir da liberação. Data
            # limite anterior à liberação deixa o servidor com prazo negativo e
            # some da aba de pendentes sem nunca ter sido pago.
            periodo_ordenado(
                "data_liberacao_diarias",
                "prazo_limite_saque",
                name="prest_serv_prazo_apos_liberacao",
            ),
        ]

    def __str__(self):
        return f"{self.servidor} — Ofício {self.prestacao.oficio.numero_formatado}"

    @property
    def oficio(self):
        return self.prestacao.oficio

    @property
    def is_motorista(self) -> bool:
        return bool(
            self.prestacao.oficio.motorista_id
            and self.servidor_id == self.prestacao.oficio.motorista_id
        )

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def status_variant(self):
        return {
            self.STATUS_PENDENTE: "pending",
            self.STATUS_EM_PREENCHIMENTO: "warning",
            self.STATUS_ENVIADA: "info",
            self.STATUS_APROVADA: "success",
            self.STATUS_REPROVADA: "danger",
        }.get(self.status, "muted")

    def definir_arquivada(self, arquivada: bool):
        """Arquiva/desarquiva este servidor, registrando o momento do arquivamento."""
        from django.utils import timezone as _tz

        self.arquivada = arquivada
        self.arquivada_em = _tz.now() if arquivada else None
        self.save(update_fields=["arquivada", "arquivada_em", "atualizado_em"])

    def definir_finalizada(self, finalizada: bool):
        """Conclui/reabre a prestação deste servidor, registrando o momento."""
        from django.utils import timezone as _tz

        self.finalizada = finalizada
        self.finalizada_em = _tz.now() if finalizada else None
        self.save(update_fields=["finalizada", "finalizada_em", "atualizado_em"])

    def marcar_em_preenchimento(self):
        if self.status == self.STATUS_PENDENTE:
            self.status = self.STATUS_EM_PREENCHIMENTO
            self.save(update_fields=["status", "atualizado_em"])

    def tem_dados_coletados(self) -> bool:
        """Há trabalho de usuário nesta linha que uma exclusão destruiria (`DB-06`).

        A lista é exaustiva contra os campos editáveis do modelo, e
        `CamposConhecidosDoServidorDaPrestacaoTests` reprova quando aparece um
        campo novo — é a única forma de um campo futuro não voltar a ser apagado
        em silêncio pela troca de equipe.
        """
        return bool(
            self.numero_solicitacao.strip()
            or self.diaria_valor_override is not None
            or self.diaria_valor_override_observacao.strip()
            or self.data_liberacao_diarias
            or self.prazo_limite_saque
            or self.status != self.STATUS_PENDENTE
            or self.arquivada
            or self.finalizada
            # Comprovante de saque e assinatura eletrônica do RT: os dois que a
            # cascata levava junto, e os dois que ninguém consegue refazer.
            or self.documentos_anexos.exists()
            or self.assinaturas.exists()
        )

    def sair_da_equipe(self) -> bool:
        """Tira este servidor da equipe corrente. Devolve `True` se preservou a linha.

        Sem nada coletado não há o que preservar, e a linha some de vez — que é o
        comportamento de sempre e o que impede a prestação de exibir servidores
        semeados pelo wizard e depois retirados. Com dados, a linha fica marcada.
        """
        from django.utils import timezone as _tz

        if not self.tem_dados_coletados():
            self.delete()
            return False
        if self.removida_em is None:
            self.removida_em = _tz.now()
            self.save(update_fields=["removida_em", "atualizado_em"])
        return True

    def voltar_para_equipe(self) -> None:
        """Desfaz `sair_da_equipe`, e com ela reaparecem anexos e assinaturas."""
        if self.removida_em is None:
            return
        self.removida_em = None
        self.save(update_fields=["removida_em", "atualizado_em"])


class PrestacaoDocumentoAnexo(models.Model):
    TIPO_DESPACHO = "despacho"
    TIPO_OFICIO_ASSINADO = "oficio_assinado"
    TIPO_COMPROVANTE = "comprovante"
    TIPO_RT_ASSINADO = "rt_assinado"
    TIPO_DB_ASSINADO = "db_assinado"

    TIPO_CHOICES = [
        (TIPO_DESPACHO, "Despacho assinado do ofício"),
        (TIPO_OFICIO_ASSINADO, "Ofício assinado"),
        (TIPO_COMPROVANTE, "Comprovante de saque/transferência"),
        (TIPO_RT_ASSINADO, "Relatório técnico assinado"),
        (TIPO_DB_ASSINADO, "Diário de bordo assinado"),
    ]

    prestacao = models.ForeignKey(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="documentos_anexos",
    )
    # Comprovante e RT assinado (individual) apontam para o servidor; despacho,
    # ofício e diário assinados são compartilhados → ficam nulos (referenciam
    # apenas a prestação do ofício).
    servidor_prestacao = models.ForeignKey(
        PrestacaoServidor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documentos_anexos",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    arquivo = models.FileField(
        upload_to=prestacao_documento_anexo_upload_to,
        validators=[validate_private_document_upload],
    )
    nome_original = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "criado_em", "pk"]
        verbose_name = "Anexo da prestação de contas"
        verbose_name_plural = "Anexos da prestação de contas"

    def __str__(self):
        return self.nome_original or self.arquivo.name


class RelatorioTecnico(models.Model):
    prestacao = models.OneToOneField(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="relatorio_tecnico",
    )
    motivo = models.TextField(blank=True, default="")
    diaria = models.CharField(max_length=255, blank=True, default="")
    translado = models.CharField(max_length=255, blank=True, default="")
    combustivel = models.CharField(max_length=255, blank=True, default="")
    passagem = models.CharField(max_length=255, blank=True, default="")
    atividade = models.TextField(blank=True, default="")
    conclusao = models.TextField(blank=True, default="")
    medidas = models.TextField(blank=True, default="")
    info_complementares = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Relatório Técnico"
        verbose_name_plural = "Relatórios Técnicos"

    def __str__(self):
        return f"RT — {self.prestacao}"


class DiarioBordo(models.Model):
    """Diário de bordo do veículo gerado a partir do roteiro do ofício da prestação.

    Os dados de cabeçalho (motorista, viatura, ofício, e-protocolo) vêm do ofício;
    os trechos vêm do roteiro. O usuário complementa KM inicial/final e a
    necessidade de abastecimento de cada trecho (ver ``DiarioBordoTrecho``).
    """

    # Motorista do diário. Por padrão vem do ofício (modo OFICIO); pode ser
    # trocado só para esta prestação (outro servidor do mesmo ofício ou um
    # motorista de outro ofício) sem alterar o ofício original.
    MOTORISTA_MODO_OFICIO = "OFICIO"
    MOTORISTA_MODO_SERVIDOR = "SERVIDOR"
    MOTORISTA_MODO_OUTRO = "OUTRO_OFICIO"
    MOTORISTA_MODO_CHOICES = [
        (MOTORISTA_MODO_OFICIO, "Manter motorista do ofício"),
        (MOTORISTA_MODO_SERVIDOR, "Outro servidor deste ofício"),
        (MOTORISTA_MODO_OUTRO, "Motorista de outro ofício"),
    ]

    # Viatura do diário. Por padrão vem do ofício (modo OFICIO); pode ser trocada
    # só para este diário — escolhendo uma viatura do cadastro (BANCO) ou
    # preenchendo os dados manualmente (MANUAL) — sem alterar o ofício original.
    VIATURA_MODO_OFICIO = "OFICIO"
    VIATURA_MODO_BANCO = "BANCO"
    VIATURA_MODO_MANUAL = "MANUAL"
    VIATURA_MODO_CHOICES = [
        (VIATURA_MODO_OFICIO, "Manter a viatura do ofício"),
        (VIATURA_MODO_BANCO, "Selecionar do cadastro"),
        (VIATURA_MODO_MANUAL, "Preencher manualmente"),
    ]

    prestacao = models.OneToOneField(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="diario_bordo",
    )
    motorista_modo = models.CharField(
        max_length=16,
        choices=MOTORISTA_MODO_CHOICES,
        default=MOTORISTA_MODO_OFICIO,
    )
    motorista_servidor = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Motorista (servidor do ofício)",
    )
    motorista_manual_nome = models.CharField(max_length=255, blank=True, default="")
    motorista_manual_cpf = models.CharField(max_length=11, blank=True, default="")
    motorista_oficio_referencia = models.CharField(
        max_length=16,
        blank=True,
        default="",
        verbose_name="Ofício do motorista",
        help_text="Referência no formato número/ano (ex.: 15/2026).",
    )
    motorista_protocolo_ref = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Protocolo do motorista",
    )

    # ── Override da viatura (independente do motorista) ──
    viatura_modo = models.CharField(
        max_length=10,
        choices=VIATURA_MODO_CHOICES,
        default=VIATURA_MODO_OFICIO,
    )
    viatura = models.ForeignKey(
        "cadastros.Viatura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Viatura (cadastro)",
    )
    viatura_manual_modelo = models.CharField(max_length=120, blank=True, default="")
    viatura_manual_placa = models.CharField(max_length=8, blank=True, default="")
    viatura_manual_tipo = models.CharField(
        max_length=20,
        choices=Viatura.TIPO_CHOICES,
        blank=True,
        default="",
    )
    viatura_manual_combustivel = models.CharField(max_length=60, blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Diário de Bordo"
        verbose_name_plural = "Diários de Bordo"

    def __str__(self):
        return f"Diário de bordo — {self.prestacao}"

    @property
    def motorista_alterado(self) -> bool:
        """True quando o motorista foi trocado em relação ao do ofício."""
        return self.motorista_modo != self.MOTORISTA_MODO_OFICIO

    @property
    def viatura_alterada(self) -> bool:
        """True quando a viatura foi trocada em relação à do ofício."""
        return self.viatura_modo != self.VIATURA_MODO_OFICIO


class DiarioBordoTrecho(models.Model):
    """Linha do diário de bordo, espelhando um trecho do roteiro do ofício."""

    diario = models.ForeignKey(
        DiarioBordo,
        on_delete=models.CASCADE,
        related_name="trechos",
    )
    trecho = models.ForeignKey(
        RoteiroTrecho,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diario_bordo_trechos",
    )
    ordem = models.PositiveIntegerField(default=0)
    km_inicial = models.PositiveIntegerField(null=True, blank=True)
    km_final = models.PositiveIntegerField(null=True, blank=True)
    abastecimento = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["diario", "ordem", "pk"]
        verbose_name = "Trecho do diário de bordo"
        verbose_name_plural = "Trechos do diário de bordo"
        constraints = [
            # `DB-07`: km final antes do inicial dá rodagem negativa no diário de
            # bordo assinado — que é peça de prestação de contas de combustível.
            # `gte`, não `gt`: trecho sem deslocamento tem os dois iguais.
            periodo_ordenado("km_inicial", "km_final", name="diario_trecho_km_ordenado"),
        ]

    def __str__(self):
        return f"Trecho {self.ordem} — {self.diario_id}"


class AssinaturaDocumento(models.Model):
    """Assinatura eletrônica de um documento da prestação (RT ou Diário de Bordo).

    Registro canônico — há no máximo um por ``(prestacao, tipo)``. O "link" enviado
    ao signatário é representado por ``link_token`` (compartilhado entre RT e DB quando
    se gera um link único). O signatário confirma identidade (CPF completo + nome),
    posiciona a assinatura e envia; o PDF carimbado fica em ``arquivo_assinado`` e passa
    a ser usado pelo sistema. O campo ``hash_documento`` armazena o SHA-256 do PDF
    original no momento da assinatura, garantindo integridade do documento.
    """

    TIPO_RT = "rt"
    TIPO_DB = "db"
    TIPO_CHOICES = [
        (TIPO_RT, "Relatório Técnico"),
        (TIPO_DB, "Diário de Bordo"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_ASSINADA = "assinada"
    STATUS_CANCELADA = "cancelada"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ASSINADA, "Assinada"),
        (STATUS_CANCELADA, "Cancelada"),
    ]

    MODO_FONTE = "fonte"
    MODO_DESENHO = "desenho"
    MODO_CHOICES = [
        (MODO_FONTE, "Fonte"),
        (MODO_DESENHO, "Desenho"),
    ]

    prestacao = models.ForeignKey(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="assinaturas",
    )
    # RT é assinado por servidor → aponta para o ``PrestacaoServidor``; o Diário
    # é assinado uma vez pelo motorista → fica nulo (nível ofício/prestação).
    servidor_prestacao = models.ForeignKey(
        PrestacaoServidor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assinaturas",
    )
    tipo = models.CharField(max_length=4, choices=TIPO_CHOICES, db_index=True)
    signer = models.ForeignKey(
        Servidor,
        on_delete=models.PROTECT,
        related_name="assinaturas_documentos",
    )
    nome_esperado = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDENTE)

    # Link enviado ao signatário (token compartilhado entre RT/DB no "link único").
    link_token = EncryptedTextField(blank=True, default="")
    link_token_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    link_criado_em = models.DateTimeField(null=True, blank=True)
    link_expira_em = models.DateTimeField(null=True, blank=True)

    # Verificação de identidade.
    identidade_confirmada_em = models.DateTimeField(null=True, blank=True)

    # Snapshot do PDF não assinado (garante que o carimbo bate com o que foi exibido).
    arquivo_origem = models.FileField(upload_to=assinatura_origem_upload_to, blank=True)

    # Resultado da assinatura.
    modo = models.CharField(max_length=10, choices=MODO_CHOICES, blank=True, default="")
    fonte = models.CharField(max_length=60, blank=True, default="")
    assinatura_png = models.FileField(upload_to=assinatura_png_upload_to, blank=True)
    pagina = models.PositiveIntegerField(default=0)
    pos_x = models.FloatField(null=True, blank=True)
    pos_y = models.FloatField(null=True, blank=True)
    largura = models.FloatField(null=True, blank=True)
    altura = models.FloatField(null=True, blank=True)
    arquivo_assinado = models.FileField(upload_to=assinatura_assinado_upload_to, blank=True)
    assinado_em = models.DateTimeField(null=True, blank=True)
    assinado_ip = models.CharField(max_length=64, blank=True, default="")
    codigo_verificacao = models.CharField(max_length=12, blank=True, default="")
    hash_documento = models.CharField(max_length=64, blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["prestacao", "tipo"]
        verbose_name = "Assinatura de documento"
        verbose_name_plural = "Assinaturas de documentos"
        constraints = [
            # Documentos de nível ofício (ex.: Diário de Bordo): um por prestação/tipo.
            models.UniqueConstraint(
                fields=["prestacao", "tipo"],
                condition=Q(servidor_prestacao__isnull=True),
                name="uniq_assinatura_prestacao_tipo",
            ),
            # Documentos individuais (ex.: Relatório Técnico): um por servidor/tipo.
            models.UniqueConstraint(
                fields=["servidor_prestacao", "tipo"],
                condition=Q(servidor_prestacao__isnull=False),
                name="uniq_assinatura_servidor_tipo",
            ),
        ]

    def __str__(self):
        return f"Assinatura {self.get_tipo_display()} — {self.prestacao_id}"

    def save(self, *args, **kwargs):
        self.link_token_hash = (
            hashlib.sha256(self.link_token.encode("utf-8")).hexdigest()
            if self.link_token
            else ""
        )
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "link_token" in update_fields:
            kwargs["update_fields"] = [*set(update_fields), "link_token_hash"]
        return super().save(*args, **kwargs)

    @property
    def assinada(self) -> bool:
        return self.status == self.STATUS_ASSINADA and bool(self.arquivo_assinado)

    @property
    def link_expirado(self) -> bool:
        from django.utils import timezone as _tz

        return bool(self.link_expira_em and self.link_expira_em < _tz.now())

    @property
    def link_ativo(self) -> bool:
        return bool(self.link_token) and not self.link_expirado and not self.assinada

    @property
    def cpf_esperado(self) -> str:
        cpf = (self.signer.cpf or "").strip() if self.signer_id else ""
        return "".join(ch for ch in cpf if ch.isdigit())[:11]


class ModeloTextoRelatorioTecnico(models.Model):
    """Textos reutilizáveis para preencher rapidamente os campos do RT."""

    CAMPO_MOTIVO = "motivo"
    CAMPO_ATIVIDADE = "atividade"
    CAMPO_CONCLUSAO = "conclusao"
    CAMPO_MEDIDAS = "medidas"
    CAMPO_INFO = "info_complementares"

    CAMPO_CHOICES = [
        (CAMPO_MOTIVO, "Descrição do evento"),
        (CAMPO_ATIVIDADE, "Objetivo da participação"),
        (CAMPO_CONCLUSAO, "Conclusão"),
        (CAMPO_MEDIDAS, "Medidas a serem adotadas pelo órgão"),
        (CAMPO_INFO, "Informações complementares"),
    ]

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="modelos_texto_relatorio_tecnico",
        verbose_name="Area de trabalho",
    )
    campo = models.CharField(max_length=30, choices=CAMPO_CHOICES, db_index=True)
    nome = models.CharField(max_length=120)
    texto = models.TextField()
    ordem = models.PositiveIntegerField(default=100)

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["campo", "ordem", "nome"]
        verbose_name = "Modelo de texto do RT"
        verbose_name_plural = "Modelos de texto do RT"
        indexes = [
            models.Index(fields=["area", "campo", "ordem", "nome"], name="prest_rt_txt_area_campo_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["campo", "nome"],
                condition=Q(area__isnull=True),
                name="unique_modelo_texto_rt_campo_nome",
            ),
            models.UniqueConstraint(
                fields=["area", "campo", "nome"],
                condition=Q(area__isnull=False),
                name="prest_rt_texto_area_campo_nome_unique",
            ),
        ]

    def __str__(self):
        return f"{self.get_campo_display()} — {self.nome}"
