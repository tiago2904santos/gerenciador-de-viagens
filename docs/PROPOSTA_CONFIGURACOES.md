# Proposta — arquitetura de configurações

**Status:** proposta aguardando decisão. Nada implementado.
**Origem:** pedido de reorganizar a tela de configurações e torná-la extensível
por documento, por lista e por usuário.
**Relação com o plano:** é **escopo novo**, fora das oito etapas de
[`PLANO_REFATORACAO_EXECUCAO.md`](PLANO_REFATORACAO_EXECUCAO.md). Precisa entrar
como etapa própria, com posição decidida — não como desvio de uma etapa em curso.

---

## 1. O problema já existe

`ConfiguracaoSistema` tem cerca de 30 campos numa tabela só, misturando quatro
coisas de natureza diferente:

| Natureza | Exemplos | Muda com que frequência |
|---|---|---|
| Identidade institucional | `nome_orgao`, `sigla_orgao`, endereço, telefone | quase nunca |
| Padrão de documento | `destinatario_oficio`, `nome_chefia`, `cargo_chefia` | raramente |
| Regra de negócio | `prazo_justificativa_dias` | quando a norma muda |
| Estado operacional | `pt_ultimo_numero` | a cada documento emitido |

O último é o sintoma mais claro: um **contador** vive na mesma tabela que o
endereço do órgão. Cada emissão de plano de trabalho escreve na linha que também
guarda a identidade da instituição.

Sem uma estrutura, cada necessidade nova vira mais uma coluna. Em dois anos são
80 campos, uma tela com rolagem infinita e nenhuma forma de saber quem pode
mudar o quê.

## 2. O que **não** fazer

**Chave-valor genérico** (`Configuracao(chave, valor_texto)`). É a solução que
parece flexível e cobra caro depois:

- sem tipo: todo consumidor faz `int(valor)` ou `Decimal(valor)` na mão, e um
  dia alguém salva `"10 dias"` num campo que era número;
- sem validação: o banco aceita qualquer coisa;
- sem migração: mudar o significado de uma chave não tem como ser versionado;
- sem referência: `FK` para `Servidor` ou `Cidade` vira `"id: 42"` em texto.

Este sistema já tem uma prova viva do custo disso: **`diaria_valor_override`**,
que guarda valor monetário como texto livre e aceita `"abc"` (`NOVO-10`). É
exatamente o que chave-valor genérico produz, multiplicado por cada opção.

## 3. A proposta

### 3.1 Três escopos, com donos diferentes

Configuração não é uma coisa só. São três, com ciclos de vida distintos:

| Escopo | Quem decide | Exemplos | Onde vive |
|---|---|---|---|
| **Área** | administrador da área | identidade institucional, destinatário padrão de ofício, prazo de justificativa, tabela de diárias | modelo por domínio, FK para `AreaTrabalho` |
| **Usuário** | cada pessoa, para si | filtros preferidos por lista, ordenação padrão, densidade da tela, tema | modelo próprio, FK para `User` |
| **Sistema** | quem opera o servidor | motor de PDF, chaves, limites | `.env` / `settings`, **nunca** em tela |

A terceira linha é uma fronteira que vale escrever: **o que muda o
comportamento técnico do servidor não vai para tela**. Colocar motor de PDF numa
tela de configuração transforma um erro de clique em incidente de produção.

### 3.2 Modelos tipados por domínio, não uma tabela larga

Em vez de `ConfiguracaoSistema` crescer, cada domínio ganha o seu, com os campos
que fazem sentido para ele e as validações que ele exige:

```
ConfiguracaoInstitucional   identidade do órgão, endereço, chefia
ConfiguracaoOficio          destinatário padrão, assunto padrão, numeração
ConfiguracaoJustificativa   prazo, modelo de texto padrão
ConfiguracaoTermo           …
ConfiguracaoPlanoTrabalho   coordenador administrativo, numeração
ConfiguracaoOrdemServico    …
ConfiguracaoPrestacao       …
TabelaDiaria                já existe (Etapa 3)
```

Ganhos concretos: cada campo tem tipo e validação de verdade; `FK` continua
sendo `FK`; migração de um domínio não toca nos outros; e o teste de cada
domínio fica no app dele.

O contador (`pt_ultimo_numero`) **não** entra em configuração — é estado
operacional e pertence ao serviço de numeração.

### 3.3 Um registro que monta a tela sozinha

A extensibilidade que você pediu não vem de guardar tudo numa tabela genérica —
vem de a **tela** ser montada a partir de uma lista declarada:

```python
# core/config/registry.py  (esqueleto da ideia)
@registrar_secao
class SecaoOficios:
    slug = "oficios"
    titulo = "Ofícios"
    icone = "document"
    modelo = ConfiguracaoOficio
    form = ConfiguracaoOficioForm
    papel_minimo = VinculoUsuarioArea.PAPEL_ADMIN
    ordem = 20
```

Acrescentar configuração de um documento novo passa a ser: criar o modelo, o
form, e registrar a seção. A tela, o menu lateral e o controle de acesso vêm de
graça. Nenhum template precisa ser editado.

É o mesmo princípio dos motores globais que a auditoria de HTML/JS propõe para o
front — declarar em vez de repetir.

### 3.4 Preferência de lista por usuário

O caso que você citou (filtros preferidos por lista) é escopo **usuário**, e tem
uma forma natural:

```
PreferenciaLista(usuario, lista, filtros_padrao, ordenacao, itens_por_pagina)
```

`lista` é o identificador da tela (`oficios`, `prestacoes`, `roteiros`…), e o
conteúdo é validado contra os filtros que aquela lista declara — não texto
livre. Assim uma preferência salva para um filtro que deixou de existir é
detectável, em vez de virar erro silencioso.

**Cuidado que vale antecipar:** preferência de filtro interage com a pendência
aberta da busca em tempo real (hoje filtrando só a página corrente). Fazer as
duas sem coordenar produz uma tela que "lembra" um filtro que não funciona como
o usuário espera.

## 4. Controle de acesso — a parte que hoje não existe

A auditoria de segurança registrou: *"os papéis Administrador, Editor e Leitor
existem, mas não são aplicados às operações dos módulos"*.

Uma tela de configurações **torna isso urgente**. Sem papel aplicado, qualquer
usuário da área pode mudar o valor da diária ou o destinatário padrão dos
ofícios. Hoje o risco é menor porque a tela é pequena e pouco visitada; com a
reorganização proposta, ela vira o painel de controle do sistema.

Por isso `papel_minimo` está no registro da seção desde o esqueleto. **Não
recomendo implementar a tela nova sem isso.**

## 5. Custo e sequenciamento

Estimativa grosseira, no mesmo formato do plano:

| Fatia | Escopo | Dias-pessoa |
|---|---|---|
| 1 | Registro de seções + tela montada por declaração + `papel_minimo` aplicado | 4–6 |
| 2 | Separar `ConfiguracaoSistema` em institucional + por documento (com migração de dados) | 6–9 |
| 3 | `PreferenciaLista` por usuário, começando por uma lista | 3–5 |
| 4 | Demais documentos e preferências, incrementais | 4–8 |
| | **Total** | **17–28** |

É comparável a uma etapa do plano — entre a Etapa 1 (8–12) e a Etapa 2 (18–24).
Não cabe como "uma aba a mais".

### Onde encaixar

Três posições defensáveis, em ordem de recomendação:

**a) Depois da Etapa 4 (backend de aderência).** A Etapa 4 cria `core/catalog.py`
e a camada de selectors nos apps faltantes — a mesma disciplina que o registro
de seções precisa. Fazer depois aproveita a fundação em vez de duplicá-la.

**b) Como fatia da Etapa 4.** Se a tela for prioridade de uso, ela entra junto
com o backend, sem esperar.

**c) Agora, antes da Etapa 4.** Só vale se houver necessidade operacional
concreta — e mesmo assim eu faria a fatia 1 apenas, deixando a separação de
`ConfiguracaoSistema` para depois.

## 6. O que precisa da sua decisão

1. **Onde encaixar** — (a), (b) ou (c) da seção 5.
2. **Papéis:** aplicar `ADMIN/EDITOR/LEITOR` na tela de configurações faz parte
   desta proposta, ou vira tarefa separada? Minha recomendação é **junto** —
   uma tela de configuração sem controle de acesso é pior que a atual.
3. **`prazo_justificativa_dias` e afins:** são configuração de área ou passam a
   ser regra versionada com vigência, como a tabela de diárias? Vale decidir
   agora quais parâmetros mudam de valor com o tempo e precisam guardar
   histórico — mudar depois custa migração de dados.

## 7. O que faço enquanto isso

A **tabela de diárias** (Etapa 3, parte 3) entra na tela de configurações atual,
numa seção própria, com os três campos e o cálculo ao vivo. É pequena, é
necessária agora, e serve de **protótipo** do registro de seções: se a forma se
provar boa ali, a fatia 1 desta proposta vira generalização de algo que já
funciona, em vez de desenho no papel.
