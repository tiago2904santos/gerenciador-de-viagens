# Plano de Implementação — Planos de Trabalho

## Escopo

Evoluir `planos_trabalho` com foco em composição por serviços (estado, diárias, efetivo e atividades), sem monólito em form/view.

## Dependências

- `roteiros` para dados de deslocamento.
- `oficios` para vínculo documental.
- `documentos/services/` para geração de artefatos.

## Arquivos-alvo (fases futuras)

- `planos_trabalho/models.py`
- `planos_trabalho/forms.py`
- `planos_trabalho/selectors.py`
- `planos_trabalho/services.py`
- `planos_trabalho/presenters.py`
- `planos_trabalho/views.py`

## Ordem recomendada

1. Definir schema principal e entidades auxiliares.
2. Implementar services de reconciliação de estado e cálculo.
3. Implementar forms em fatias (núcleo + complementos).
4. Implementar listagem/detalhe/download/autosave.
