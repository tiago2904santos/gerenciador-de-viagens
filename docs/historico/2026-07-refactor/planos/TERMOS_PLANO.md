# Plano de Implementação — Termos

## Escopo

Definir implementação incremental do app `termos`, incluindo criação, edição e renderização documental por modalidade.

## Dependências

- `documentos/services/` para contratos de render e validação.
- `oficios` e (quando aplicável) `eventos` para contexto de origem.

## Arquivos-alvo (fases futuras)

- `termos/models.py`
- `termos/forms.py`
- `termos/selectors.py`
- `termos/services.py`
- `termos/presenters.py`
- `termos/views.py`

## Ordem recomendada

1. Definir schema de termo e vínculos.
2. Implementar service de contexto e geração por tipo.
3. Implementar forms e validações de entrada.
4. Implementar listagem/detalhe/download com presenters.
