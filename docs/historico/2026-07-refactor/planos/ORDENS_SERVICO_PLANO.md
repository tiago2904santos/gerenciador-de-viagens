# Plano de Implementação — Ordens de Serviço

## Escopo

Preparar `ordens_servico` para implementação de CRUD e geração documental com vínculo a Ofício e contexto operacional.

## Dependências

- `oficios` para origem e consistência de vínculo.
- `documentos/services/` para validação/render/download.

## Arquivos-alvo (fases futuras)

- `ordens_servico/models.py`
- `ordens_servico/forms.py`
- `ordens_servico/selectors.py`
- `ordens_servico/services.py`
- `ordens_servico/presenters.py`
- `ordens_servico/views.py`

## Ordem recomendada

1. Definir schema com campos operacionais e estados.
2. Implementar service de montagem/validação de contexto.
3. Implementar forms e validações de consistência.
4. Implementar fluxo de listagem, detalhe e geração documental.
