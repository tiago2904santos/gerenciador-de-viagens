"""Navegação de wizard — o dono único da leitura da ação do rodapé (BE-01).

Havia duas cópias desta função, uma em `oficios/view_helpers.py` e outra em
`planos_trabalho/view_helpers.py`, e elas divergiram. A de planos lia só
`post.get("action")`, enquanto os rodapés — que vêm do componente compartilhado
`components/ui/layouts/card_footer_actions.html` — emitem `name="wizard_action"`.
O valor do botão nunca chegava, e o helper caía no default:

- "Finalizar plano" recarregava a mesma página, sem mensagem;
- "Voltar" empurrava o usuário para a etapa seguinte.

Quatro telas do wizard de plano de trabalho ficaram assim até a correção. Com a
função em `core`, a divergência deixa de ser possível sem alguém mexer aqui.
"""

from __future__ import annotations


def normalizar_acao_do_wizard(post, *, default: str = "wizard_next") -> str:
    """Ação pedida pelo rodapé do wizard.

    Lê `wizard_action` primeiro: `name="action"` colide com `form.action` no DOM
    (vira `RadioNodeList`) e quebra o JS que lê a URL de submit do formulário. O
    nome legado continua aceito para não depender de todo template ter migrado.
    """
    bruto = post.get("wizard_action")
    if bruto in (None, ""):
        bruto = post.get("action")
    acao = (bruto or default).strip()
    if acao == "save_continue":
        return "wizard_next"
    return acao
