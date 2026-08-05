# Plano de Implementação — Justificativas

## Escopo

Estruturar o app `justificativas` para fluxo global e por Ofício, com regras de prazo e modelos de texto.

## Estado da implementação (Ofício / wizard)

| Item | Estado |
|------|--------|
| Schema (`ModeloJustificativa`, `Justificativa` 1:1 com Ofício) | Implementado |
| Regra de prazo (10 dias / `ConfiguracaoSistema`) | Implementado (`justificativas/services.py`) |
| Forms, selectors, services de persistência, presenters | Implementado |
| Integração etapa 4 do wizard | Implementado (`oficios:wizard_justificativa`) |
| Validação documental / finalização | Integrado em `validar_oficio_para_documento` |

## Futuro (fora do escopo atual do wizard)

- CRUD global de justificativas (telas dedicadas em `/justificativas/` além do placeholder).
- Geração DOCX específica de “Justificativa” como documento separado.
- UI global para gestão de modelos de justificativa (além do admin Django).

## Dependências

- `oficios` para vínculo contextual.
- `documentos/services/` para geração quando houver artefato documental.

## Ordem recomendada (histórico)

1. Definir schema de justificativa + modelos de texto.
2. Implementar serviços de regra de prazo e obrigatoriedade.
3. Implementar forms e validações de vínculo.
4. Implementar integração com Ofício (wizard).
