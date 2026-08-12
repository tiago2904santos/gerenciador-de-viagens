"""`BE-11` — a orquestração da submissão do editor de roteiro, uma vez só.

`roteiros/views.py::novo` e `::editar` tinham **55 linhas idênticas** (de 89 e 86 úteis):
a mesma sequência de validar, decidir entre sobrescrever um duplicado, atualizar ou criar,
e depois normalizar o estado para re-renderizar. O cálculo já morava em service
(`roteiro_editor.py`); o que estava escrito duas vezes era a *sequência de decisões*.

O que **não** está aqui, de propósito: `request`, `messages` e `redirect`. O service diz
*o que aconteceu*; a view decide *o que mostrar* — e precisa decidir, porque as duas
mensagens de duplicado têm textos diferentes e o retorno depende de `?next=` e do evento.
É o contrato de `docs/PADRAO_SERVICES.md`.
"""

from dataclasses import dataclass
from dataclasses import field

from roteiros.models import Roteiro

from .roteiro_editor import atualizar_roteiro
from .roteiro_editor import criar_roteiro
from .roteiro_editor import encontrar_roteiro_duplicado
from .roteiro_editor import normalizar_destinos_e_trechos_apos_erro_post
from .roteiro_editor import sobrescrever_roteiro_duplicado
from .roteiro_editor import validar_submissao_editor_roteiro


@dataclass(frozen=True)
class ResultadoSubmissaoEditor:
    """O que a submissão produziu. A view traduz isto em mensagem e redirect."""

    #: Persistiu; a view pode redirecionar.
    salvo: bool
    #: O roteiro que ficou gravado — o duplicado, quando houve fusão.
    roteiro: Roteiro | None
    #: O roteiro idêntico encontrado, se houve. Quem fundiu no duplicado precisa do pk
    #: dele para a mensagem, e é isso que distingue as duas mensagens de sucesso.
    duplicado: Roteiro | None
    #: Achou duplicado mas a sobrescrita devolveu `None`: vira erro não-de-campo no form,
    #: sem redirect. Ramo estreito, mas o único em que `duplicado` é relevante e `salvo`
    #: é falso ao mesmo tempo — daí o campo próprio em vez de deduzir dos outros dois.
    colisao_sem_saida: bool
    roteiro_state: dict = field(default_factory=dict)
    validated: dict = field(default_factory=dict)
    #: Estado normalizado para re-renderizar o editor depois de um POST com erro.
    destinos_atuais: list = field(default_factory=list)
    trechos_list: list = field(default_factory=list)

    @property
    def fundiu_no_duplicado(self) -> bool:
        return self.salvo and self.duplicado is not None

    def erros_de_validacao(self):
        return self.validated.get("errors", [])

    def estado_para_rerender(self):
        """A mesma tripla de `preparar_estado_editor_roteiro_para_get`, na mesma ordem.

        Os dois ramos da view — POST com erro e GET — desembocam no mesmo `render`, e a
        simetria só é legível se ambos devolverem a tripla de uma vez.
        """
        return self.destinos_atuais, self.trechos_list, self.roteiro_state


def processar_submissao_editor(post, form, route_state_map, *, roteiro=None, evento=None):
    """Valida o POST do editor e decide entre sobrescrever duplicado, atualizar ou criar.

    `roteiro` é a instância que está sendo editada. Em `editar` nunca é `None`; em `novo`
    é o rascunho de autosave, que pode não existir — e é exatamente aí, e só aí, que o
    caminho é `criar_roteiro`. Nenhuma bandeira nova: a distinção que as duas views já
    faziam (`elif rascunho is not None` / `else`) é `roteiro is None`.
    """
    roteiro_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
        post, route_state_map, roteiro=roteiro
    )

    if form.is_valid() and validated["ok"]:
        duplicado = encontrar_roteiro_duplicado(
            validated,
            roteiro_state,
            evento=evento,
            excluir_pk=getattr(roteiro, "pk", None),
        )
        if duplicado is not None:
            salvo = sobrescrever_roteiro_duplicado(
                duplicado,
                post,
                method="POST",
                roteiro_state=roteiro_state,
                validated=validated,
                diarias_resultado=diarias_resultado,
                instance_obsoleta=roteiro,
            )
        elif roteiro is not None:
            salvo = atualizar_roteiro(roteiro, form, roteiro_state, validated, diarias_resultado)
        else:
            salvo = criar_roteiro(form, roteiro_state, validated, diarias_resultado, evento=evento)

        if salvo is not None:
            return ResultadoSubmissaoEditor(
                salvo=True,
                roteiro=salvo,
                duplicado=duplicado,
                colisao_sem_saida=False,
                roteiro_state=roteiro_state,
                validated=validated,
            )

        # Só se chega aqui com `duplicado` preenchido: `atualizar_roteiro` e
        # `criar_roteiro` não devolvem `None`.
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(roteiro_state)
        return ResultadoSubmissaoEditor(
            salvo=False,
            roteiro=None,
            duplicado=duplicado,
            colisao_sem_saida=True,
            roteiro_state=roteiro_state,
            validated=validated,
            destinos_atuais=destinos_atuais,
            trechos_list=trechos_list,
        )

    destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(roteiro_state)
    return ResultadoSubmissaoEditor(
        salvo=False,
        roteiro=None,
        duplicado=None,
        colisao_sem_saida=False,
        roteiro_state=roteiro_state,
        validated=validated,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
    )
