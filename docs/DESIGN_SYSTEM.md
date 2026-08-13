# Design System

## Regras globais

- CSS centralizado em `static/css/`.
- JS centralizado em `static/js/`.
- Proibido CSS e JS soltos por pagina.
- Nao criar estilo especifico por CRUD; corrigir no component global reutilizavel.
- Proibido `style=""` em templates.
- Proibido JS inline em templates.
- Proibido `href="#"` para acao visual.
- Navegacao deve omitir link quando a URL nao resolver; renderizar item neutro/desabilitado sem `href` invalido.
- Inicializacao de tema deve ocorrer por `static/js/core/theme-init.js` (sem `<script>` inline no `base.html`).
- Configuracao de tema (chave, temas validos e normalizacao) deve ficar centralizada em `static/js/core/theme-shared.js`.
- Seletor de tema deve manter os 4 modos oficiais (`dark-dark`, `light-dark`, `dark-light`, `light-light`) sem script inline.
- A **tela de login** usa layout proprio (sem sidebar): classes em `static/css/auth.css` (prefixo `auth-`), importado tambem em `style.css`; ver `docs/AUTENTICACAO.md`.
- Se um valor CSS aparece em mais de um ponto relevante, ele deve virar token semantico (`--color-*`, `--radius-*`, `--space-*`, `--shadow-*`, `--control-*`, `--font-*`).
- Evitar valor bruto em componente (`999px`, `#ffffff`, sombras repetidas); usar token semantico equivalente.
- `border-radius: 999px` e proibido em componente; usar sempre `var(--radius-pill)`.
- Hardcode restante so e aceito com justificativa especifica (seletor + motivo tecnico), nunca justificativa generica.
- Seletor de tema deve respeitar semantica de `radiogroup` (`role="radio"` com `aria-checked` coerente).

## Tokenizacao semantica (refactor)

- Tokens globais vivem em `static/css/tokens.css`.
- Variacao por tema vive em `static/css/theme.css`.
- Compatibilidade com legado `--theme-*` deve ser mantida via alias quando necessario (sem quebra abrupta).
- Cada arquivo CSS deve ser organizado por secoes com comentarios de contexto (shell, secoes, mapa, overrides, responsividade).

## Dark mode bem resolvido

- Tema escuro funcional != tema escuro bem desenhado.
- Funcional: tudo escuro e legivel no minimo.
- Bem desenhado: hierarquia entre secoes/cards/inputs, contraste de label/help e estados vazios coerentes.
- Em painel escuro, evitar blocos brancos de estado vazio; preferir `--color-info-*`.
- Em inputs disabled/read-only, manter `opacity: 1` e reduzir contraste por token, nao por opacidade global.
- Em componentes que existem em dark mode, e proibido texto em azul escuro hardcoded (`#0b3a66` e similares).
- Hierarquia de texto recomendada:
  - titulo interno: `--color-heading` / `--color-section-title`
  - label: `--color-label` / `--color-label-strong`
  - ajuda/descricao: `--color-help` / `--color-description`
- Icones em painel escuro usam `--color-icon-*`; radio/checkbox usam `accent-color` por token.

## Padrao visual premium

- Superficies em camadas claras, com bordas suaves e sombra controlada.
- Cabecalho de pagina com gradiente azul profundo, luz suave e hierarquia forte.
- Inputs, cards e botoes com altura/radius consistentes para manter ritmo visual.
- Estados de sucesso, erro, aviso e info com contraste elegante e sem agressividade.
- Densidade otimizada para CRUD: menos espaco morto e leitura mais rapida.
- Identidade oficial: azul institucional solido com destaque amarelo/dourado.
- Evitar verde/ciano como destaque padrao em labels, chips e elementos de identidade.
- Evitar gradientes acinzentados pesados no header e no fundo global.
- Page header deve manter margem, respiro e contraste forte de titulo/descricao.

## Referência estética do legacy

- O projeto em `legacy/` foi usado como referencia visual e conceitual para sidebar, gradientes, densidade de cards, botoes em pilula e acabamento de toolbar/formularios.
- Foram aproveitadas ideias de identidade: menu lateral escuro com estados ativos mais evidentes, cabecalho com gradiente institucional, cards com acento lateral e superficies em camadas.
- Foram descartados trechos especificos e volumosos de CSS legado, estilos acoplados por pagina e estruturas antigas de template nao componentizadas.
- A reinterpretacao foi aplicada somente no design system novo (`templates/components/` + `static/css/`) com tokens globais.
- Nao existe importacao, dependencia de runtime, ou reaproveitamento tecnico direto de arquivos de `legacy/`.

## Mascaras reutilizaveis

As mascaras do sistema ficam em `static/js/components/masks.js` e devem ser habilitadas por `data-mask` nos campos.

Mascaras padrao:

- CPF: `000.000.000-00`
- RG: `00.000.000-0`
- Telefone: `(00) 0000-0000` ou `(00) 00000-0000`
- Placa: `AAA-1234` ou `AAA1A23`

A normalizacao final ocorre no backend (forms/models).

## Card-toggle (checkbox)

Booleanos visiveis em formularios devem usar o padrao **card-toggle** (`app-card-toggle` em `static/css/forms.css`, componente `card_toggle.html`), inspirado no botao **Data unica** do Plano de Trabalho do legacy.

Regras:

- Checkbox cru do navegador nao deve aparecer na interface final.
- O input real continua no DOM, oculto com tecnica acessivel de visually-hidden.
- O card mostra icone, titulo forte, descricao pequena e badge de estado `LIGADA` / `DESLIGADA`.
- Desligado usa fundo e borda vermelhos suaves, com badge vermelho.
- Ligado usa azul institucional com acento amarelo/dourado, borda destacada e badge premium.
- BooleanFields futuros renderizados manualmente devem usar `templates/components/ui/forms/card_toggle.html`.
- JS de sincronismo em `static/js/components/card-toggle.js` (sem JS inline).

## Cadastros como referencia

As telas de `Unidade`, `Cidade`, `Cargo`, `Combustivel`, `Servidor` e `Viatura` sao a referencia visual e estrutural para os proximos modulos.

## Tipos de listagem

- **Lista simples** (`components/lists/list_page_standard.html`, `simple_list.html`): para cadastros enxutos com poucos campos — `Cargo`, `Combustivel`, `Unidade`, `Cidade`. Visual compacto, estilo tabela premium sem `<table>`, com linhas densas e acoes a direita.
- **Cards ricos** (`list_page.html` + `document_card`): para entidades com mais contexto — `Servidor`, `Viatura` e, no futuro, documentos (Oficios, Termos, etc.).

## Regras para evolucao visual

- Ajustes de header em `templates/components/layout/page_header.html` e `static/css/layout.css`.
- Ajustes de sidebar em `templates/components/layout/sidebar.html`, `static/css/sidebar.css` e `static/js/components/sidebar.js`.
- Ajustes de toolbar de lista em `templates/components/ui/headers/filter_page_header.html` e `static/css/lists.css`.
- Ajustes de formularios em `templates/components/ui/forms/*.html` e `static/css/forms.css`.
- Ajustes de cards em `templates/components/cards/*.html` e `static/css/cards.css`.
- Ajustes de feedback em `templates/components/feedback/*.html` e `static/css/utilities.css`.
- Nunca copiar CSS bruto do legado em bloco; extrair o conceito e reconstruir no sistema atual.

## CSS de dominio (`domain.css`)

- Arquivo: `static/css/domain.css`.
- Uso: blocos compartilhados de **roteiros, trechos, destinos, retorno, calculadora e resumo de rota** — classes semanticas como `.domain-block`, `.domain-block__title`, `.route-summary`, `.route-card`.
- Regra: estilos que servem a **qualquer modulo** com o mesmo tipo de bloco ficam aqui; o que for **exclusivo do wizard avulso** (densidade, hero, grids do `roteiro-editor`) permanece em `static/css/roteiros.css`.
- Paginas que incluem `templates/components/travel/*` devem importar `domain.css` no `extra_css` (alem de `style.css` via `base.html`).
- Proibido `style=""` nos templates; proibido variar o mesmo tipo de bloco com classes duplicadas em outro arquivo sem motivo.

## Layout do shell

Tokens em `static/css/tokens.css`:

- `--sidebar-width: 15%` — largura da coluna da sidebar em relacao ao viewport.
- `--page-max-width: 100%` — conteudo principal sem teto artificial de largura.

O `grid` em `static/css/layout.css` usa `var(--sidebar-width)` + `minmax(0, 1fr)` para a area principal ocupar o restante (~85%) sem estourar overflow.

## Sidebar hierarquica

A sidebar e a unica navegacao lateral. O menu **Cadastros** e o unico bloco com botao de expandir/recolher; dentro dele, os itens sao uma lista plana com **indentacao visual** (e opcional indicador) para `Cargos` sob `Servidores` e `Combustiveis` sob `Viaturas`, **sem** sub-submenus com segundo toggle.

A hierarquia e declarada em `core/navigation.py` (filhos de Cadastros com `sidebar_indent`), renderizada em `templates/components/layout/sidebar.html`, estilizada em `static/css/sidebar.css` e o grupo Cadastros e aberto via `static/js/components/sidebar.js` (incluindo `localStorage`).

Ordem sob Cadastros: Servidores, Cargos (subordinado visual), Viaturas, Combustiveis (subordinado visual), Unidades, Cidades. `Motoristas` nao aparece.
`Estados` permanece como rota administrativa interna e nao integra a lista principal da sidebar.

### Comportamento do grupo expansivel (Cadastros)

- O usuario abre/fecha o grupo pelo botao **Cadastros** (toggle).
- Ao clicar em qualquer **link principal** fora do grupo (Dashboard, Roteiros, modulos, marca no topo), os grupos expansiveis **fecham** e o estado e removido do `localStorage`, para nao reabrir em rotas erradas.
- Se a URL atual for sob `/cadastros/` (ou `/cadastros`), o grupo **Cadastros** carrega **aberto**; fora desse prefixo, carrega **fechado** e o `localStorage` nao mantem o submenu aberto.

## Excecoes oficiais arquiteturais

Estas excecoes sao decisoes deliberadas e documentadas. O auditor (`scripts/audit_frontend_standards.py`) as reconhece como EXCECAO, nao como ERRO.

### Dashboard — `dashboard-login-inspired`

- **Arquivo:** `templates/core/dashboard.html` + `static/css/dashboard.css`
- **Decisao:** manter o shell `dashboard-login-inspired` como excecao oficial
- **Justificativa:** o Dashboard tem identidade visual propria (hero de boas-vindas, grade de stats, grade de acesso rapido) que nao se mapeia diretamente no padrao `app-page-hero`. Migracao forcada fragmentaria o visual sem beneficio funcional.
- **Conformidade atual:** usa 100% CSS variables (zero hex hardcoded como valor primario); emite classes canônicas `app-page`, `app-page__shell`, `app-section`, `app-card` em paralelo.
- **O que NAO deve ser feito:** adicionar CSS fixo por cor hex; duplicar tokens criando `--dashboard-*` para o mesmo conceito; misturar o shell de dashboard em outras paginas.

### Forms shell com tema de Roteiros — `.roteiro-editor__*` em `forms.css`

- **Arquivo:** `static/css/forms.css`
- **Decisao:** manter `.roteiro-editor__*` como joint selectors de `.app-form-shell` em `forms.css`
- **Justificativa:** esses seletores sao sempre pareados com seletores globais (`.app-form-shell .form-actions`, etc.) na mesma regra CSS. Separar exigiria refactor das regras globais sem ganho visual.
- **Conformidade atual:** usa apenas tokens `--route-*` (definidos globalmente em `theme.css`), nao hex hardcoded.

### Tela de autenticacao — `auth-*`

- **Arquivo:** `static/css/auth.css`
- **Decisao:** excecao de layout (sem sidebar, shell proprio `auth-shell`)
- **Justificativa:** a tela de login nao tem sidebar e usa layout diferente de qualquer modulo interno.

## API canonica — referencia rapida

### Shell de pagina

```html
<div class="app-page">
  <div class="app-page__shell">
    <header class="app-page-hero app-page__header app-page-hero--hybrid app-page__header--hybrid">
      <div class="app-page-hero__stage">
        <span class="app-page-hero__eyebrow">Modulo</span>
        <h1 class="app-page-hero__title">Titulo</h1>
      </div>
      <div class="app-page-hero__body">
        <div class="app-page__hero-top">
          <div class="app-page__brand">
            <div class="app-page__brand-mark">XX</div>
            <div class="app-page__brand-copy">
              <p class="app-page__subtitle">Descricao</p>
            </div>
          </div>
          <div class="app-page__hero-actions">
            {# action_button.html #}
          </div>
        </div>
      </div>
      <div class="app-page-hero__ribbon" aria-hidden="true"></div>
    </header>
    {# conteudo #}
  </div>
</div>
```

### Formulario canonico

```html
{% raw %}
<form class="app-form-shell form-shell">
  <div class="form-section app-form-section">
    {# form_field.html — emite app-form-field, app-form-label, app-form-help, app-form-error #}
    <div class="form-grid app-form-grid">
      {% include "components/ui/forms/field.html" with field=form.campo only %}
    </div>
  </div>
  <div class="form-actions">
    {% include "components/ui/buttons/button.html" with ... only %}
  </div>
</form>
{% endraw %}
```

### Botao canonico

```html
{% raw %}
{# Via componente (preferido) #}
{% include "components/ui/buttons/button.html" with href=url label="Acao" variant="primary" only %}

{# Saida: emite .btn.btn-primary.app-btn.app-btn--primary #}
{% endraw %}
```

### Lista canonico

```html
<div class="list-grid app-list-grid">
  {# cards #}
</div>

<div class="simple-list app-list">
  <div class="simple-list__row app-list__row">
    {# conteudo + acoes #}
  </div>
</div>
```

## Responsabilidade dos arquivos CSS

| Arquivo | Responsabilidade |
|---------|-----------------|
| `tokens.css` | Primitivos: cores, espacamento, radius, tipografia |
| `theme.css` | Tokens semanticos por tema, `--app-*`, `--route-*` |
| `base.css` | Reset, body, tipografia base, inputs globais |
| `layout.css` | Shell global (`app-shell`, `app-main`), `.eyebrow` |
| `sidebar.css` | Sidebar institucional |
| `buttons.css` | `.btn` / `.app-btn` e variantes |
| `forms.css` | Form shell, campos, controles, joint selectors de Roteiros |
| `lists.css` | Listas, toolbar, `.simple-list`, aliases `.app-list-*` |
| `cards.css` | Cards, secoes, paineis, aliases `.app-card`, `.app-section` |
| `oficios.css` | CSS exclusivo do modulo Oficios (card, wizard, equipe, motivo) |
| `app-ui.css` | `.app-page-hero`, badges, chips, status-pill |
| `dashboard.css` | Shell e grid exclusivos do Dashboard (excecao oficial) |
| `app-page.css` | `.app-page`, `.app-page__shell`, superficies de pagina |
| `stages.css` | Stepper/stages do wizard de Oficios |
| `documents.css` | Cards e superficies de documentos (PDF/DOCX) |
| `utilities.css` | Classes utilitarias |
| `domain.css` | Componentes de dominio: rota, trechos, destinos, resumo |
| `roteiros.css` | CSS extra do editor de Roteiros (Leaflet, mapa, autosave) |
| `roteiros-list.css` | CSS extra da lista de Roteiros (cards com diarias) |
