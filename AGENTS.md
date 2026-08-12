# AGENTS.md — Constituição do refactor

Este arquivo é o contrato único para **qualquer agente de IA** que escreve código neste
repositório: Claude Code, Cursor e Codex. Cursor e Codex leem este arquivo nativamente;
o Claude Code lê via `CLAUDE.md`, que aponta para cá.

> Se algo neste arquivo conflitar com uma instrução do chat, **este arquivo vence** —
> exceto quando o humano disser explicitamente "ignore o AGENTS.md nesta tarefa".

---

## 1. Onde está a verdade

O sistema foi reauditado em **05/08/2026**, ao fim do ciclo de julho. O catálogo novo é a
**especificação** do refactor. Nenhum agente deve "descobrir sozinho" o que precisa ser feito:
o defeito já tem número.

| Documento | Domínio | IDs de defeito |
|---|---|---|
| `docs/CATALOGO_DEFEITOS_2026-08.md` | **Todos os defeitos vigentes, com evidência medida** | `BE`, `DB`, `UI`, `HT`, `JS`, `PF`, `QA` |
| `docs/PLANO_MESTRE_REFATORACAO.md` | **Ordem de execução, gate e critério de pronto de cada etapa** | — |
| `docs/PLANO_BACKEND.md` | Python, camadas, dados, migrações | `BE-xx`, `DB-xx` |
| `docs/PLANO_FRONTEND.md` | CSS, templates, JS, acessibilidade | `UI-xx`, `HT-xx`, `JS-xx` |
| `docs/PLANO_DESEMPENHO.md` | Queries, cache, assets, documentos | `PF-xx` |

O ciclo anterior está congelado em `docs/historico/2026-07-refactor/` — leia o `README.md` de
lá se precisar do contexto de uma decisão antiga. **Os IDs antigos (`D-`, `H-`, `J-`, `P-`,
`S-`, `T-`, `N-`, `NOVO-`) não são mais unidade de trabalho**; descrevem o código de julho.

Os documentos `docs/PADRAO_*.md` descrevem o contrato de camadas **já vigente**. Código novo
segue o `PADRAO_*` correspondente; divergência é defeito, não estilo pessoal.

## 2. Regra de ouro: o ID do defeito é a unidade de trabalho

- Toda tarefa começa citando um ou mais IDs (`BE-01`, `PF-03`, `UI-07`…).
- Todo commit cita o ID: `fix(perf): elimina N+1 na lista de termos (PF-02)`.
- Todo PR lista os IDs resolvidos e marca a linha correspondente em
  `docs/CATALOGO_DEFEITOS_2026-08.md` e no plano da etapa **no mesmo PR**.
- **Não existe trabalho fora de ID.** Se você encontrar um defeito não catalogado, adicione
  uma linha nova em `docs/CATALOGO_DEFEITOS_2026-08.md` (com `NOVO` na coluna de origem) e só
  então conserte — ou registre e siga em frente, se estiver fora do escopo da etapa.

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
   **Poda de CSS é por família de classe, não por arquivo.** A regra antiga ("um arquivo por PR")
   quebrava no caso comum: classe estilizada em dois CSS e usada em nenhum template é morta nos
   dois, e podar só um lado deixa regra órfã do outro. Medido em `cv-buttons.css`, 16 das 25
   classes mortas estavam nessa situação. A unidade de PR é a **classe**, com a prova de grep
   cobrindo todos os arquivos que a estilizam. O que continua valendo, e é o que a regra
   protegia: nada sai sem grep de repositório inteiro, e o grep tem de cobrir **concatenação com
   `+` e interpolação no meio da string**, não só `` `${…}` `` no começo.
7. **Nada de `fetch()` cru, `alert()`, `confirm()`, `style=` inline, `<script>` inline, cor
   literal fora dos arquivos de token, ORM dentro de view.** Estes são os invariantes que as
   auditorias mediram; regredir qualquer um deles reprova o PR.
8. **Segredo não entra no repositório.** Chave, token, senha: só em `.env` e `.env.example`
   com placeholder.
9. **Falha genérica não some em silêncio.** Todo `except Exception` de produção deve relançar a
   exceção ou registrar a falha com logger/`core.errors.capture()`. Exceções esperadas devem ser
   capturadas pelo tipo específico; fallback silencioso genérico reprova a auditoria de arquitetura.

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
6. Atualizar docs/CATALOGO_DEFEITOS_2026-08.md (status da linha) e o plano da etapa.
7. Abrir PR com o template da seção 5.
```

Suíte de referência: **1.306 testes verdes** em PostgreSQL, ~10 s com `--parallel 4`
(medido em 05/08/2026). Um PR que reduz o número de testes verdes ou aumenta o tempo em mais
de 20% precisa justificar no corpo.

## 5. Corpo de PR obrigatório

```markdown
## Etapa
Etapa N do docs/PLANO_MESTRE_REFATORACAO.md

## Defeitos resolvidos
- PF-02 — N+1 na lista de termos (termos/presenters.py:118)
- UI-05 — 4 camadas de token com valor conflitante

## Como verifiquei
- [ ] Suíte completa verde (N testes, Xs)
- [ ] audit_frontend_standards: 392 → 388 avisos
- [ ] Números de desempenho antes/depois, quando a etapa for de desempenho
- [ ] Telas afetadas conferidas em tema claro e escuro (print no PR)

## O que NÃO fiz
(escopo deliberadamente deixado de fora, com o ID do defeito)
```

## 6. Divisão de trabalho entre as ferramentas

**Desde 05/08/2026 o Claude Code é o dono do refactor de ponta a ponta** — condução das
etapas, decisão de arquitetura e fechamento do sistema. Cursor e Codex passam a ser apoio
opcional, usados quando a etapa se beneficia do que cada um faz melhor. O detalhe por etapa
está em `docs/PLANO_MESTRE_REFATORACAO.md` §4.

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
python scripts/audit_frontend_standards.py --max-warnings 401   # teto atual; confira em tests.yml
python scripts/audit_django_architecture.py
python scripts/audit_ui_patterns.py
python scripts/build_shell_bundles.py --check                   # bundles do shell em dia
python manage.py runserver 0.0.0.0:8000
```

Ambiente: Django + PostgreSQL, `requirements/lock.txt` pinado com hash. CI em
`.github/workflows/tests.yml` — leia-o antes de propor qualquer gate novo.
