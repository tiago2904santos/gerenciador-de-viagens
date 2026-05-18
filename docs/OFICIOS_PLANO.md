# Plano de Implementação — Ofícios

## Escopo

Preparar o app `oficios` para sair do placeholder e receber implementação por etapas, sem criar schema nesta fase.

## Dependências

- `documentos/services/` (tipos, validação, filenames, renderers).
- Reuso de blocos e contratos de `roteiros` para trechos/destinos/retorno.
- `assinaturas` para fluxo de assinatura e validação de integridade.

## Arquivos-alvo (fases futuras)

- `oficios/models.py`
- `oficios/forms.py`
- `oficios/selectors.py`
- `oficios/services.py`
- `oficios/presenters.py`
- `oficios/views.py`

## Ordem recomendada

1. Fechar schema e estados de Ofício.
2. Implementar selectors e services transacionais.
3. Implementar formulários por etapa (fase1/fase2 + integração com roteiro).
4. Implementar listagem/detalhe com presenters.
5. Conectar geração documental e assinatura.
