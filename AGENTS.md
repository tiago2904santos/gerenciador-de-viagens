# AGENTS.md — Constituição do refactor

Este arquivo é o contrato único para **qualquer agente de IA** que escreve código neste
repositório: Claude Code, Cursor e Codex. Cursor e Codex leem este arquivo nativamente;
o Claude Code lê via `CLAUDE.md`, que aponta para cá.

> Se algo neste arquivo conflitar com uma instrução do chat, **este arquivo vence** —
> exceto quando o humano disser explicitamente "ignore o AGENTS.md nesta tarefa".

---

## 1. Onde está a verdade

O sistema foi auditado em 27–28/07/2026. As auditorias são a **especificação** do refactor.
Nenhum agente deve "descobrir sozinho" o que precisa ser feito: o defeito já tem número.

| Documento | Domínio | IDs de defeito |
|---|---|---|
| `docs/AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md` | CSS, tokens, tema escuro | `D-xx` |
| `docs/AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md` | Templates, semântica, motores JS | `H-xx`, `J-xx` |
| `docs/AUDITORIA_BACKEND_INFRA_COMPLETA.md` | Python, settings, testes, infra | `P-xx`, `S-xx`, `T-xx`, `D-0x`, `R-xx`, `G-xx` |
| `docs/AUDITORIA_FINAL_CORRECAO_E_CUSTO.md` | Regra de negócio, desempenho, a11y medidos | `N-xx` |
| `docs/AUDITORIA_COMPLETA_SISTEMA_2026-07-27.md` | Segurança e privacidade (já remediada em parte) | — |
| `docs/PLANO_REFATORACAO_EXECUCAO.md` | **Ordem de execução, dono e gate de cada etapa** | — |
| `docs/PROMPTS_REFATORACAO.md` | Prompts prontos por etapa e por ferramenta | — |

Os documentos `docs/PADRAO_*.md` descrevem o contrato de camadas **já vigente**. Código novo
segue o `PADRAO_*` correspondente; divergência é defeito, não estilo pessoal.

## 2. Regra de ouro: o ID do defeito é a unidade de trabalho

- Toda tarefa começa citando um ou mais IDs (`D-01`, `J-02`, `N-01`…).
- Todo commit cita o ID: `fix(css): define fundo e sombra do toast de download (D-01)`.
- Todo PR lista os IDs resolvidos e marca a linha correspondente em
  `docs/PLANO_REFATORACAO_EXECUCAO.md` **no mesmo PR**.
- **Não existe trabalho fora de ID.** Se você encontrar um defeito não catalogado, adicione
  uma linha nova no catálogo da auditoria correspondente (com `NOVO` na coluna de origem) e
  só então conserte — ou registre e siga em frente, se estiver fora do escopo da etapa.

## 3. Limites invioláveis

1. **Não misture etapas no mesmo PR.** Um PR = uma fase do plano. Correção de defeito e
   renomeação de classe nunca viajam juntas.
2. **Não renomeie nada pela metade.** Renomear uma classe/hook/template exige, no mesmo PR:
   template + CSS + JS + testes + o dicionário de renomeação da auditoria atualizado.
3. **Não toque em regra de dinheiro sem teste antes.** Qualquer mudança em
   `roteiros/services/diarias.py` exige teste de caracterização escrito **antes** da mudança,
   provando o comportamento atual, e o teste da regra nova depois.
4. **Não crie migração sem checar dados.** Constraint/index novo (`P-03`) exige query de
   validação dos dados existentes no PR + procedimento de backup citado.
5. **Não desative gate de CI para passar.** `scripts/audit_frontend_standards.py --max-warnings`
   é uma catraca: o número **só desce**. Se seu PR aumenta o número, o PR está errado.
6. **Não apague arquivo "morto" sem prova.** Prova = `grep` no repositório inteiro (templates,
   JS, CSS, Python) colado no PR mostrando zero referências.
7. **Nada de `fetch()` cru, `alert()`, `confirm()`, `style=` inline, `<script>` inline, cor
   literal fora dos arquivos de token, ORM dentro de view.** Estes são os invariantes que as
   auditorias mediram; regredir qualquer um deles reprova o PR.
8. **Segredo não entra no repositório.** Chave, token, senha: só em `.env` e `.env.example`
   com placeholder.

## 4. Ciclo de trabalho obrigatório

```
1. Ler a seção da auditoria que define o defeito (não o documento inteiro).
2. Rodar a suíte ANTES:   python manage.py test --settings=config.settings.test
3. Escrever/ajustar o teste que prova o defeito (quando o defeito for testável).
4. Corrigir.
5. Rodar a suíte DEPOIS + os auditores:
     python scripts/audit_frontend_standards.py --max-warnings <N atual>
     python scripts/audit_django_architecture.py
     python scripts/audit_ui_patterns.py
6. Atualizar docs/PLANO_REFATORACAO_EXECUCAO.md (status da linha) e o catálogo da auditoria.
7. Abrir PR com o template da seção 5.
```

Suíte de referência: **924 testes verdes** (eram 812 até `NOVO-08` devolver ao runner os 95
testes de `core/tests/`, que nunca foram descobertos). Um PR que reduz o número de testes
verdes ou aumenta o tempo em mais de 20% precisa justificar no corpo.

## 5. Corpo de PR obrigatório

```markdown
## Etapa
Etapa N do docs/PLANO_REFATORACAO_EXECUCAO.md

## Defeitos resolvidos
- D-01 — toast sem fundo (static/css/components/document-download-loading.css)
- D-04 — variant="muted" inexistente

## Como verifiquei
- [ ] Suíte completa verde (N testes, Xs)
- [ ] audit_frontend_standards: 465 → 461 avisos
- [ ] Telas afetadas conferidas em tema claro e escuro (print no PR)

## O que NÃO fiz
(escopo deliberadamente deixado de fora, com o ID do defeito)
```

## 6. Divisão de trabalho entre as três ferramentas

Resumo; o detalhe por etapa está em `docs/PLANO_REFATORACAO_EXECUCAO.md` §4.

| Ferramenta | Faz bem aqui | Não use para |
|---|---|---|
| **Claude Code** | Tarefas que exigem ler muitos arquivos, rodar a suíte, decidir arquitetura: testes de Prestações, motor de diárias, motores JS, camada de selectors | Ajuste fino de aparência que precisa de olho humano na tela |
| **Cursor** | Trabalho visual com feedback imediato: contraste, tokens de cor, aparência de componente, revisão página a página no navegador | Refactor mecânico em 60 arquivos (caro e lento no editor) |
| **Codex** | Tarefas mecânicas, bem especificadas, verificáveis por comando: apagar arquivos mortos, trocar literal por token, higiene de repositório, migrar `fetch()` → `CV.http` | Decisão de regra de negócio ou qualquer coisa sem critério objetivo de pronto |

**Regra de paralelismo:** duas ferramentas nunca trabalham na mesma camada ao mesmo tempo.
CSS e JS podem correr em paralelo; CSS e HTML não.

## 7. Comandos do projeto

```bash
source .venv/bin/activate
python manage.py test --settings=config.settings.test        # suíte completa
python manage.py test <app> --settings=config.settings.test  # suíte de um app
python manage.py check --deploy --settings=config.settings.prod
python manage.py makemigrations --check --dry-run --settings=config.settings.test
python scripts/audit_frontend_standards.py --max-warnings 465
python manage.py runserver 0.0.0.0:8000
```

Ambiente: Django + PostgreSQL, `requirements/lock.txt` pinado com hash. CI em
`.github/workflows/tests.yml` — leia-o antes de propor qualquer gate novo.
