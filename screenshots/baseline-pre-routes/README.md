# Baseline visual pré-Fase 5 (rotas/trechos)

Capturas de referência antes de refatorar `pages/roteiros/editor/index.js` e `roteiros-map.js`.

## Ferramenta

- **Playwright** (já usado em `screenshots/auditoria-telas/_capturar.py`)
- Script desta pasta: `_capturar_baseline.py`
- Servidor local: `python manage.py runserver` em `http://localhost:8000`
- Usuário autenticado nas rotas de cadastros/ofícios (sem login, telas redirecionam para `/login/`)

## Rotas prioritárias

| Arquivo PNG | Rota |
|-------------|------|
| `ui-lab-lists.png` | `/dev/ui-lab/lists/` |
| `ui-lab-fields.png` | `/dev/ui-lab/fields/` |
| `ui-lab-selects-filters.png` | `/dev/ui-lab/selects-filters/` |
| `cadastros-cargos.png` | `/cadastros/cargos/` |
| `cadastros-servidores.png` | `/cadastros/servidores/` |
| `cadastros-viaturas.png` | `/cadastros/viaturas/` |
| `oficios-index.png` | `/oficios/` |
| `roteiros-index.png` | `/roteiros/` |
| `cadastros-configuracao.png` | `/cadastros/configuracao/` |

## Execução

```bash
python screenshots/baseline-pre-routes/_capturar_baseline.py
```

Relatório JSON: `_baseline_report.json` (inclui erros/warnings de console coletados na sessão).

## Resolução e tema

- Viewport sugerido: **1440×900** (desktop)
- Tema claro/escuro: capturar manualmente após alternar o toggle global, se necessário comparar contraste
- Esta fase não exige duplicar todos os temas em PNG automatizado

## Observação

Se o script não rodar (servidor parado ou Playwright indisponível), o baseline visual fica como **checklist manual** documentado em `docs/historico/2026-07-refactor/relatorios/RELATORIO_BASELINE_PRE_ROTAS.md`.
