# Plano — Central de Configurações

Remodelação de `/cadastros/configuracao/` para que a página responda sozinha à
pergunta "como este sistema se comporta", organizada **por documento**.

Decisões tomadas com o solicitante antes de escrever este plano:

- Navegação por **abas por documento**, cada aba com URL própria.
- Escopo: **reorganizar + preferências novas + integrações**.
- Cadastros de apoio (Servidores, Cargos, Viaturas, Unidades, Combustíveis)
  **ficam fora**, com atalho contextual onde faz sentido.

---

## 1. Diagnóstico — o que existe hoje

### 1.1 A página atual

`cadastros/views.py:572` (`configuracao_sistema`) renderiza quatro cards num
`cv-form-section-stack`, com três formulários independentes separados por um
`form_id` no POST:

| Card | Formulário | `form_id` |
| --- | --- | --- |
| Dados da unidade e endereço | `ConfiguracaoSistemaForm` | — (default) |
| Assinantes padrão por documento | `ConfiguracaoAssinaturasForm` | — (mesmo POST) |
| Valores de diária | `TabelaDiariaForm` | `diarias` |
| Destinatário padrão do Ofício | `ConfiguracaoDestinatarioForm` | `destinatarios` |

O padrão de "vários `<form>` numa página, cada card com o seu rodapé de Salvar"
**já está certo** e é o que o resto do sistema usa. O problema não é o
mecanismo — é que a página cresceu por acumulação e não tem eixo: endereço
institucional e valor de diária moram no mesmo scroll, e nada diz a que
documento cada ajuste pertence.

### 1.2 Onde a configuração mora hoje

**`ConfiguracaoSistema`** (`cadastros/models.py:448`) — `OneToOne` com
`AreaTrabalho`, ou seja **toda configuração já é por área**. Isso é um acerto e
o plano preserva integralmente:

- Institucional: `nome_orgao`, `sigla_orgao`, `unidade`, `sede`,
  `cep`/`logradouro`/`numero`/`bairro`/`cidade_endereco`/`uf`,
  `telefone`, `ramal`, `email`, `nome_chefia`, `cargo_chefia`,
  `cidade_sede_padrao`
- Ofício: `destinatario_oficio` + `destinatario_oficio_nome` / `_cargo` / `_unidade`
- Justificativa: `prazo_justificativa_dias`
- Plano de Trabalho: `coordenador_adm_plano_trabalho`, `pt_ultimo_numero`,
  `pt_ano`, `pt_sufixo_numero`

**`AssinaturaConfiguracao`** (`cadastros/models.py:612`) — assinante padrão por
tipo. Hoje só quatro tipos: `OFICIO`, `JUSTIFICATIVA`, `PLANO_TRABALHO`,
`ORDEM_SERVICO`. **O Termo de Autorização não tem assinante padrão** — lacuna.

**`TabelaDiaria`** (`cadastros/models.py:659`) — faixa + vigência + valor de 24h,
com 15% e 30% derivados no servidor. Modelo bom, com noção de vigência.

### 1.3 O que está fixo no código e deveria ser preferência

Levantado arquivo a arquivo:

| Onde | O que está fixo | Documento |
| --- | --- | --- |
| `oficios/models.py:180` | formato `{numero:02d}/{ano}` | Ofício |
| `ordens_servico/models.py:164` | formato `OS {numero:03d}/{ano}` e reinício anual | OS |
| `planos_trabalho/models.py:432` | formato `{numero:02d}/{ano}/{sufixo}` | PT |
| `oficios/assunto_oficio.py:39` | frases "Solicitação de autorização/convalidação e concessão de diárias." | Ofício |
| `justificativas/services.py:19` | fallback de 10 dias quando a config não responde | Justificativa |
| `documentos/resources/*.docx` | 11 modelos de documento embutidos no repositório | Todos |
| `config/settings/base.py:248-273` | `GOOGLE_DRIVE_MODO`, `PASTA_RAIZ_ID`, `UPLOAD_EM_MOCK`, timeout | Integração |
| `core/perfil.html` | card do Google Drive vive em **Meu Perfil**, não em Configurações | Integração |

E o que simplesmente **não existe** como preferência, mas o operador pede na
prática: qual etapa do wizard é obrigatória, se o Diário de Bordo é gerado
sempre ou sob demanda, quem recebe o link de assinatura por padrão, se a
prestação exige anexo assinado antes de finalizar.

---

## 2. Arquitetura proposta

### 2.1 Abas por documento

Uma faixa `cv-segment-toggle--nav` logo abaixo do cabeçalho, exatamente o
componente que o toggle Usuários/Áreas já usa (`components/lists/list_toggle.html`
+ `static/js/components/segment-nav.js`). São links de página inteira, então
cada aba é uma URL indexável, com histórico e botão voltar funcionando:

```
/cadastros/configuracao/                    → Instituição (default)
/cadastros/configuracao/oficio/
/cadastros/configuracao/termo/
/cadastros/configuracao/ordem-servico/
/cadastros/configuracao/plano-trabalho/
/cadastros/configuracao/roteiros/
/cadastros/configuracao/prestacao/
/cadastros/configuracao/integracoes/
```

Rota única com `<slug:aba>` e um mapa aba → (formulários, template do corpo);
não oito views copiadas.

**Por que URL e não `?aba=`:** ofícios/eventos usam `?aba=` para *filtrar a
mesma lista*. Aqui cada aba é um conjunto diferente de formulários, com POST
próprio — merece caminho próprio, e o redirect pós-salvamento volta para a
aba certa sem carregar querystring.

**Justificativa não ganha aba.** Ela é sempre "Justificativa do Ofício N" —
sem numeração nem existência independente. Vira um bloco dentro da aba Ofício.
São 8 abas; uma nona só para dois campos empurraria a faixa para o scroll
horizontal no desktop.

### 2.2 Estrutura de cada aba

Reaproveita o casco já validado na página de Área que acabamos de refazer:

```
flow_base (page-shell--standard cv-page--form, document-form-page)
└── cabeçalho + faixa de abas
    └── cv-form-section-stack--comfortable
        ├── <form> → components/form/card.html  (um card por assunto)
        │             └── form_block travel-document-block  (blocos internos)
        │             └── card_footer_section  (Voltar / Salvar)
        └── <form> → ... (próximo card, POST independente)
```

Regra que o plano fixa: **um card = um formulário = um botão Salvar**. Salvar o
endereço não pode arriscar perder o que foi digitado na numeração.

### 2.3 Estado "não configurado"

Toda aba abre com um `pendencias_card` no topo listando o que falta para os
documentos daquele tipo saírem corretos (ex.: "Ofício: sem assinante padrão").
É o mesmo componente já usado nos wizards. Isso é o que transforma a página de
formulário em painel: ela passa a responder "o que ainda falta configurar".

---

## 3. Inventário aba a aba

Legenda: **[hoje]** já existe · **[novo]** exige campo/migração ·
**[mover]** existe em outro lugar e vem para cá.

### Aba 1 — Instituição

Base compartilhada por todos os documentos. É a única aba que não é "por
documento", e vem primeiro porque tudo depende dela.

- **Identificação do órgão** — `nome_orgao`, `sigla_orgao`, `unidade` **[hoje]**
- **Endereço dos documentos** — CEP (com busca ViaCEP), logradouro, número,
  bairro, cidade, UF **[hoje]**
- **Contato** — telefone, ramal, e-mail **[hoje]**
- **Chefia** — `nome_chefia`, `cargo_chefia` **[hoje]**
- **Sede e cidade padrão** — `sede`, `cidade_sede_padrao` **[hoje]**
- **Brasão / logotipo** — `ImageField` usado no cabeçalho dos documentos **[novo]**

*Atalho contextual:* "Gerenciar unidades" → `cadastros:unidades_index`.

### Aba 2 — Ofício

- **Assinante padrão** — `AssinaturaConfiguracao(OFICIO)` **[hoje]**
  · atalho "Gerenciar servidores"
- **Destinatário padrão** — servidor + cargo + unidade lotada **[hoje]**
- **Numeração** **[novo]**
  - `oficio_digitos` (padrão 2) — largura do zero à esquerda
  - `oficio_reinicia_por_ano` (padrão sim)
  - `oficio_reaproveita_lacunas` (padrão sim) — hoje o comportamento de
    `OficioNumeroLacuna` é obrigatório e invisível
  - prévia ao vivo do formato ("Ofício 07/2026")
- **Textos do documento** **[novo]**
  - `oficio_frase_autorizacao`, `oficio_frase_convalidacao` — hoje constantes em
    `oficios/assunto_oficio.py:39`
  - **Limite inviolável:** a frase fixa continua aceitando apenas os termos
    *autorização* e *convalidação* (defeito já registrado em memória do
    projeto); o campo edita a redação em volta, nunca o termo.
- **Justificativa** (bloco, não aba)
  - Assinante padrão — `AssinaturaConfiguracao(JUSTIFICATIVA)` **[hoje]**
  - `prazo_justificativa_dias` **[hoje]** — hoje editável só via admin
  - `justificativa_obrigatoria_apos_prazo` (padrão sim) **[novo]**

### Aba 3 — Termo de Autorização

- **Assinante padrão** — **[novo]**: exige acrescentar `TERMO` ao
  `TIPO_CHOICES` de `AssinaturaConfiguracao`. Lacuna real de hoje.
- **Variante padrão** **[novo]** — a escolha entre `termo_autorizacao.docx`,
  `..._automatico.docx` e `..._automatico_sem_viatura.docx` já é parametrizável
  na chamada (`termos/services.py:45`), mas o *default* é derivado só da
  presença de viatura (`oficios/documents.py:188`). O que falta é um default
  por área — e a opção de forçar o semipreenchido, que hoje nenhum caminho
  automático escolhe.
- **Preferências de geração** **[novo]**
  - `termo_um_por_servidor` (padrão sim) — hoje fixo
  - `termo_exige_viatura` (padrão não)
- **Assinatura eletrônica** **[novo]** — ligar/desligar o link público de
  assinatura e definir o texto da mensagem de WhatsApp

### Aba 4 — Ordem de Serviço

- **Assinante padrão** — `AssinaturaConfiguracao(ORDEM_SERVICO)` **[hoje]**
- **Numeração** **[novo]** — `os_digitos` (padrão 3), `os_prefixo` (padrão "OS"),
  `os_reinicia_por_ano`; hoje tudo fixo em `ordens_servico/models.py:164`
- **Preferências** **[novo]** — servidores obrigatórios sim/não, viatura
  obrigatória sim/não

### Aba 5 — Plano de Trabalho

- **Assinante padrão** — `AssinaturaConfiguracao(PLANO_TRABALHO)` **[hoje]**
- **Coordenador administrativo padrão** — `coordenador_adm_plano_trabalho` **[hoje]**
- **Numeração** — `pt_sufixo_numero` **[hoje]**; acrescentar `pt_digitos` e
  **exibir** `pt_ultimo_numero`/`pt_ano` como leitura, com ação explícita
  "reiniciar contador" protegida por confirmação **[novo]**
- **Etapas do wizard** **[novo]** — quais etapas (metas, recursos, atividades)
  são obrigatórias antes de gerar o documento

### Aba 6 — Roteiros e diárias

- **Tabela de diárias** — faixa, vigência, valor de 24h, com 15%/30% derivados
  e o histórico de vigências **[hoje]** — mantém como está, só muda de vizinhança
- **Regras de cálculo** **[novo]**
  - `diaria_meia_ate_horas` (padrão 24)
  - `diaria_arredondamento` — expor a regra `ROUND_HALF_UP` já aplicada
  - **Limite inviolável:** o roteiro guarda o valor **por um servidor**; a
    multiplicação por número de servidores acontece na exibição/geração
    (`Oficio.diarias_para_servidores()`). Nenhuma preferência desta aba pode
    mudar isso — é defeito já corrigido e registrado.
- **Roteiro** — *proposta, não levantamento*: permitir bate-volta, exigir
  quilometragem. Confirmar contra `roteiros/` antes de virar campo.

### Aba 7 — Prestação de contas

> **A validar antes de implementar.** Os campos abaixo são proposta, não
> levantamento: diferente das abas 1 a 6, não fiz a leitura do wizard de
> prestação para confirmar o que hoje é fixo e o que já é escolha do usuário.
> A Etapa 5 começa por esse levantamento.

- **Relatório Técnico** — assinante padrão (novo tipo `RELATORIO_TECNICO`),
  prazo em dias após o retorno, texto compartilhado padrão
- **Diário de Bordo** — gerar sempre ou sob demanda, formato padrão (XLSX/PDF),
  permitir troca de motorista sim/não
- **Encerramento** — exigir documento assinado para finalizar,
  arquivamento automático após N dias

### Aba 8 — Integrações e modelos

- **Google Drive** **[mover]** — o card hoje vive em Meu Perfil
  (`templates/core/perfil.html:44`). A **conexão continua individual por
  usuário** — isso não muda. O que vem para cá é o que é da área: pasta raiz,
  modo (mock/ativo), upload automático ligado/desligado, e o painel de
  pendências de upload.
- **Modelos de documento** **[novo]** — lista dos 11 `.docx` de
  `documentos/resources/`, cada um com baixar / substituir / restaurar padrão
- **Assinatura eletrônica** **[novo]** — fonte do carimbo, texto do rodapé,
  validade do link público

---

## 4. Modelo de dados

### 4.1 Onde guardar as preferências novas

**Recomendação: campos nomeados em `ConfiguracaoSistema`**, não uma tabela
chave/valor genérica.

Motivo: chave/valor perde tipagem, validação de formulário e migração de
default — e este projeto já paga esse preço em outros lugares. São ~30 campos
novos num modelo que já tem 25; grande, mas honesto. A alternativa (um modelo
`PreferenciaDocumento` com `tipo` + campos) só compensaria se as preferências
fossem realmente as mesmas entre documentos, e não são.

**Exceção:** as preferências que são *por tipo de documento e repetidas*
(assinante) já têm o seu modelo — `AssinaturaConfiguracao`. Basta acrescentar
os tipos `TERMO` e `RELATORIO_TECNICO` ao `TIPO_CHOICES`.

### 4.2 Migrações

1. `AssinaturaConfiguracao.TIPO_CHOICES` += `TERMO`, `RELATORIO_TECNICO`
   (`AlterField` de choices — sem impacto em dados)
2. `ConfiguracaoSistema` += campos de numeração (Ofício, OS, PT)
3. `ConfiguracaoSistema` += campos de texto (frases do ofício)
4. `ConfiguracaoSistema` += campos de preferência (booleanos e prazos)
5. `ConfiguracaoSistema` += `brasao` (`ImageField`)
6. `ModeloDocumento` (novo) — arquivo substituível por área, com fallback para
   `documentos/resources/`

**Todo campo novo nasce com o default igual ao comportamento atual.** A
migração não pode mudar nenhum documento já emitido nem o comportamento de
quem não abrir a página.

---

## 5. Riscos e limites

**Modelos `.docx` substituíveis pelo usuário — risco real.** `docxtpl` renderiza
Jinja2 dentro do documento. Um `.docx` enviado por um usuário é, na prática,
código executado no servidor com acesso ao contexto de renderização. Antes de
liberar o upload:

- restringir a ação a administradores (o gate `somente_administrador` já existe);
- renderizar com `jinja2.sandbox.SandboxedEnvironment`;
- validar que o arquivo é um OOXML válido antes de aceitar;
- manter o modelo de fábrica intacto no repositório, com "restaurar padrão"
  sempre disponível.

Se essa proteção não couber na etapa, **entregar a aba de modelos só com baixar
e restaurar** — sem upload — e deixar a substituição para um PR próprio.

**Google Drive.** Trazer `GOOGLE_DRIVE_MODO` e `PASTA_RAIZ_ID` do `.env` para o
banco é útil; trazer o caminho das credenciais não é — credencial continua no
ambiente. A aba lê o estado da integração e edita só o que é da área.

**Numeração.** Mudar dígitos ou prefixo com documentos já emitidos cria
inconsistência visual no histórico. A preferência deve avisar em tela que vale
para documentos **novos** e não reescreve o passado.

**Contador do PT.** `pt_ultimo_numero` é reservado com lock pessimista
(`planos_trabalho/models.py:537`). Expor isso como campo editável convida a
duplicar número. Por isso o plano expõe como **leitura + ação explícita**, nunca
como input livre.

---

## 6. Etapas de execução

Uma etapa por PR, na ordem. Cada uma entrega página funcionando.

| # | Etapa | Risco | Entrega |
| --- | --- | --- | --- |
| 1 | Casco e navegação | baixo | Rota `<slug:aba>`, faixa de abas, redirect pós-save para a aba certa. As 4 seções de hoje redistribuídas em Instituição / Ofício / Roteiros. Nenhum campo novo. |
| 2 | Assinantes completos | baixo | `TERMO` e `RELATORIO_TECNICO` no `TIPO_CHOICES`; abas Termo e Prestação nascem com o card de assinante. |
| 3 | Numeração por documento | **médio** | Campos de numeração + leitura nos três geradores. Exige plan mode: mexe em `_assign_numero` e no contador com lock. |
| 4 | Textos e preferências de geração | médio | Frases do ofício, prazo da justificativa, preferências de Termo/OS/PT. Cada leitura de constante vira leitura de config com o default de hoje. |
| 5 | Prestação e Diário | médio | Preferências da aba 7, ligadas ao wizard de prestação. |
| 6 | Integrações | médio | Drive movido do Perfil; painel de pendências. |
| 7 | Modelos de documento | **alto** | Só depois de resolvido o sandbox do `docxtpl`. Pode entregar em duas metades (baixar/restaurar, depois upload). |
| 8 | Painel de pendências | baixo | `pendencias_card` no topo de cada aba. |

---

## 7. Testes

Por etapa, no padrão que `usuarios/tests/test_admin_page.py` já usa:

- **Roteamento** — cada slug de aba responde 200; slug inválido responde 404;
  a aba ativa vem marcada com `aria-current="page"`.
- **Isolamento de formulários** — POST numa aba não zera campo de outra; é a
  regressão mais provável de toda a mudança e precisa de teste explícito.
- **Default preservado** — para cada preferência nova, um teste de que a
  configuração recém-criada produz **exatamente** o comportamento de hoje.
- **Por área** — duas áreas com configurações diferentes geram documentos
  diferentes; nenhuma lê a configuração da outra.
- **Numeração** — formato respeita os dígitos configurados; reinício anual
  liga/desliga; lacunas do ofício continuam funcionando quando ligadas.

---

## 8. O que este plano NÃO faz

- Não move Servidores, Cargos, Viaturas, Unidades e Combustíveis para dentro da
  página (decisão do solicitante) — só acrescenta atalhos contextuais.
- Não mexe em `AreaTrabalho` nem no middleware de área.
- Não reescreve o motor de diárias — só expõe o que ele já decide.
- Não altera documento já emitido: toda preferência vale daqui para frente.
