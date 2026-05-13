# Padrao Theme

## Objetivo

Padronizar o sistema com quatro modos oficiais (`dark-dark`, `light-dark`, `dark-light`, `light-light`), com superfícies sólidas e sem transparência estrutural.

## Contrato técnico

- Preferência do usuário: `dark-dark`, `light-dark`, `dark-light` e `light-light` (UI e `localStorage`).
- Atributo `data-theme` no `html` usa os 4 modos oficiais.
- Aliases legados continuam aceitos no CSS e no processo de normalização para migração.
- Persistência: `localStorage` na chave `cv-theme`.
- Inicialização antecipada: `static/js/core/theme-init.js` no `head` do `base.html`.
- Interação do usuário: `static/js/theme-toggle.js`.
- Fonte única de verdade no front-end: `static/js/core/theme-shared.js`.
- Troca de tema entre abas sincroniza por `window.storage`.

## Compatibilidade legada

O sistema normaliza automaticamente valores antigos:

- `dark` -> `dark-dark`
- `light` -> `light-light`
- `variant-a` -> `dark-dark`
- `variant-b` -> `light-light`

Após normalização, o valor salvo no `localStorage` e aplicado no DOM passa a ser um dos 4 modos oficiais.

## Responsabilidades por arquivo

- `templates/base.html`: carrega `theme-init.js` antes do CSS e `theme-toggle.js` com `defer`.
- `static/js/core/theme-shared.js`: expõe `STORAGE_KEY`, `VALID_THEMES`, `normalizeTheme()` e helpers de leitura/escrita.
- `static/js/core/theme-init.js`: resolve tema inicial usando `theme-shared`.
- `static/js/theme-toggle.js`: aplica tema selecionado, atualiza ARIA do radiogroup, persiste e escuta `storage`.
- `static/css/theme.css`: define tokens por tema (escuro/claro) e aliases legados.
- `templates/components/layout/sidebar.html`: expõe os 4 modos oficiais em `radiogroup`.

## Consumo de tokens por component

- Componentes globais (`forms.css`, `cards.css`, `lists.css`, `utilities.css`) devem consumir tokens semânticos e evitar hex direto para borda/cor de estado.
- `domain.css` deve priorizar tokens de rota (`--route-*`) com fallback para tokens globais.
- Novos estados de tema precisam primeiro virar token em `tokens.css`/`theme.css`; só depois podem ser usados nos componentes.

## Exceções autorizadas (curtas)

- `static/css/theme.css`: valores-base de tema e gradientes institucionais.
- `static/css/roteiros.css`: hardcodes necessários para preservar contrato visual aprovado de `roteiros/novo/`.

## Regras visuais obrigatórias

- Superfícies principais devem ser sólidas.
- Não usar transparência em `background` de card/painel/seção/input/select/textarea.
- Transparência permitida somente para `box-shadow`, `focus-ring`, borda sutil e elementos decorativos não estruturais.
- Priorizar token semântico em vez de hardcode.

## Hierarquia de superfícies (Roteiros)

1. Superfície principal: `--route-card-bg`
2. Blocos internos: `--route-card-inner-bg`
3. Labels/cards clicáveis internos: `--route-card-inner-bg`
4. Campos preenchíveis: `--color-card`

## Checklist mínimo de validação

### Tema Escuro
- [ ] `/roteiros/`
- [ ] `/roteiros/novo/`
- [ ] `/roteiros/<id>/editar/`
- [ ] dashboard
- [ ] uma lista documental
- [ ] um formulário documental

### Tema Claro
- [ ] `/roteiros/`
- [ ] `/roteiros/novo/`
- [ ] `/roteiros/<id>/editar/`
- [ ] dashboard
- [ ] uma lista documental
- [ ] um formulário documental
