"""Forms da Central de Protocolos.

Reaproveitam validações e componentes existentes (CPF, protocolo, servidores).
Não introduzem inputs/CSS exclusivos — os templates usam os componentes do
design system.
"""

from __future__ import annotations

from django import forms

from core.utils.masks import normalize_protocolo, only_digits, validar_cpf_digitos


class VinculoManualForm(forms.Form):
    """Cadastro de um protocolo já existente no eProtocolo (externo/manual)."""

    numero = forms.CharField(
        label="Número do protocolo", max_length=30, required=False,
        help_text="Ex.: 24.123.456-7. Pode ficar vazio se ainda não houver número.",
    )
    assunto = forms.CharField(label="Assunto", max_length=255, required=False)
    descricao = forms.CharField(
        label="Descrição", required=False, widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_numero(self):
        return normalize_protocolo(self.cleaned_data.get("numero", ""))


class AnexarDocumentoForm(forms.Form):
    """Upload manual de um PDF para envio ao protocolo."""

    TIPO_CHOICES = [
        ("ANEXO", "Anexo manual"),
        ("OFICIO", "Ofício"),
        ("TERMO_AUTORIZACAO", "Termo de Autorização"),
        ("JUSTIFICATIVA", "Justificativa"),
        ("PLANO_TRABALHO", "Plano de Trabalho"),
        ("ORDEM_SERVICO", "Ordem de Serviço"),
    ]
    tipo_documento = forms.ChoiceField(label="Tipo de documento", choices=TIPO_CHOICES)
    arquivo = forms.FileField(label="Arquivo PDF")
    nome_arquivo = forms.CharField(label="Nome do arquivo", max_length=255, required=False)
    usar_documento_principal = forms.BooleanField(
        label="Gerar e enviar o documento vinculado automaticamente",
        required=False,
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        if not arquivo:
            return arquivo
        nome = (getattr(arquivo, "name", "") or "").lower()
        content_type = getattr(arquivo, "content_type", "") or ""
        if not (nome.endswith(".pdf") or content_type == "application/pdf"):
            raise forms.ValidationError("O documento oficial deve ser um arquivo PDF.")
        return arquivo


class SolicitarAssinaturaForm(forms.Form):
    """Solicitação de assinatura. Reaproveita o cadastro de servidores."""

    def __init__(self, *args, protocolo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocolo = protocolo
        if protocolo is not None:
            self.fields["documento"].queryset = protocolo.documentos.all()

    documento = forms.ModelChoiceField(
        label="Documento", queryset=None, required=False,
        help_text="Documento já enviado ao protocolo (opcional).",
    )
    servidor = forms.ModelChoiceField(
        label="Servidor (assinante)", queryset=None, required=False,
    )
    cpf = forms.CharField(label="CPF do assinante", max_length=14, required=False)
    nome = forms.CharField(label="Nome do assinante", max_length=200, required=False)
    observacao = forms.CharField(label="Observação", max_length=255, required=False)

    def _set_servidor_queryset(self):
        from cadastros.models import Servidor
        self.fields["servidor"].queryset = Servidor.objects.all().order_by("nome")

    def full_clean(self):
        # garante queryset de servidor antes da validação
        self._set_servidor_queryset()
        super().full_clean()

    def clean(self):
        cleaned = super().clean()
        servidor = cleaned.get("servidor")
        cpf = only_digits(cleaned.get("cpf", ""))
        nome = (cleaned.get("nome") or "").strip()

        if servidor is not None:
            cpf = cpf or only_digits(servidor.cpf or "")
            nome = nome or servidor.nome

        if not cpf:
            raise forms.ValidationError("Informe um servidor ou o CPF do assinante.")
        if len(cpf) != 11 or not validar_cpf_digitos(cpf):
            self.add_error("cpf", "CPF inválido.")
        cleaned["cpf"] = cpf
        cleaned["nome"] = nome
        return cleaned


class TramitarForm(forms.Form):
    """Tramitação do protocolo. Códigos de local são configuráveis, nunca fixos."""

    cod_local_para = forms.CharField(label="Código do local de destino", max_length=30)
    nome_local_para = forms.CharField(label="Nome do local de destino", max_length=200, required=False)
    cpf_destinatario = forms.CharField(label="CPF do destinatário", max_length=14, required=False)
    nome_destinatario = forms.CharField(label="Nome do destinatário", max_length=200, required=False)
    parecer = forms.CharField(
        label="Parecer", required=False, widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_cpf_destinatario(self):
        cpf = only_digits(self.cleaned_data.get("cpf_destinatario", ""))
        if cpf and (len(cpf) != 11 or not validar_cpf_digitos(cpf)):
            raise forms.ValidationError("CPF inválido.")
        return cpf
