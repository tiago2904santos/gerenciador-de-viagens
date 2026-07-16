# Multi-login, dados separados por area e Google Drive por usuario

## Objetivo

Permitir que o sistema tenha varios logins usando a mesma aplicacao, mas com dados
separados por area/setor. Exemplo:

- ASCOM: dois usuarios acessam os mesmos eventos, oficios, documentos, cadastros
  e configuracoes da ASCOM.
- DPCAP: outros usuarios acessam outro conjunto de eventos, oficios, documentos,
  cadastros e configuracoes.
- Google Drive: cada usuario institucional conecta a propria conta Google, por
  exemplo `adm.tsantos@pc.pr.gov.br`.

O conceito central deve ser uma entidade de area, tambem chamada de tenant.

## Diagnostico da base atual

Hoje a base ainda esta desenhada como instalacao unica:

- `cadastros.ConfiguracaoSistema` e singleton via `get_singleton()` com `pk=1`.
- `integracoes.google_drive.DriveCredenciais` precisa ser resolvido por usuario,
  nao por unidade.
- Listagens como eventos, oficios, roteiros, servidores e viaturas consultam as
  tabelas inteiras.
- Numeracoes como oficio `ano + numero` sao globais.
- Artefatos documentais e registros do Drive nao carregam uma area propria.

Com esse desenho, se a DPCAP entrar no mesmo sistema, ela enxerga ou reaproveita
dados da ASCOM. Para resolver corretamente, toda entidade de negocio precisa
pertencer a uma area.

## Decisao recomendada

Usar um unico banco de dados com separacao por `area_id` em cada tabela de
negocio.

Esse modelo e mais simples e seguro para este projeto do que criar um banco
fisico diferente por login, porque:

- mantem as migrations do Django simples;
- permite relacionamentos normais entre tabelas;
- facilita backup e deploy;
- evita criar conexoes dinamicas de banco por request;
- permite que dois usuarios da ASCOM compartilhem os mesmos dados da ASCOM;
- ainda entrega isolamento logico entre ASCOM, DPCAP e futuras areas.

Banco fisico separado por area so vale se houver exigencia juridica/operacional
forte de isolamento fisico. Caso contrario, `area_id` e o caminho pragmatico.

## Modelo de dados proposto

Criar em `usuarios.models`:

```python
class AreaTrabalho(models.Model):
    nome = models.CharField(max_length=120)
    sigla = models.CharField(max_length=30, unique=True)
    ativa = models.BooleanField(default=True)


class VinculoUsuarioArea(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    area = models.ForeignKey(AreaTrabalho, on_delete=models.CASCADE)
    papel = models.CharField(max_length=30, choices=[...])
    area_padrao = models.BooleanField(default=False)
```

Se um usuario pertencer a uma unica area, o sistema seleciona automaticamente.
Se pertencer a mais de uma, mostrar um seletor de area apos o login ou no topo
da interface.

## Tabelas que devem ganhar `area`

Dados separados por area:

- `ConfiguracaoSistema`
- `AssinaturaConfiguracao`
- `Unidade`
- `Servidor`
- `Viatura`
- `Cargo`, se cada area puder personalizar cargos
- `Combustivel`, se cada area puder personalizar combustiveis
- `Evento`
- `TipoEvento`
- `ModeloMotivoEvento`
- `EventoAnexo`
- `EventoDocumentoSolicitacao`
- `Oficio`
- `OficioNumeroLacuna`
- `ModeloMotivoOficio`
- `Roteiro`
- `TermoAutorizacao`
- `Justificativa`
- `PlanoTrabalho`
- `ProgramaSolicitante`
- `HorarioAtendimento`
- `AtividadePlanoTrabalho`
- `OrdemServico`
- `PrestacaoContas`
- `ModeloTextoRelatorioTecnico`
- `DocumentoArtefato`
- `DriveReorganizacaoJob` (por usuario e area)
- `DriveArquivo`, isolado pela area do `DocumentoArtefato`
- `DriveArquivoExterno`, isolado pela area do objeto de origem
- `DriveSyncStatus`, isolado pelo usuario e pela area do objeto de origem
- modelos de protocolo/eProtocolo, se tambem forem especificos da area.

Dados que podem continuar globais:

- `Estado`
- `Cidade`
- bases geograficas/IBGE.
- `DriveCredenciais`, porque a credencial e por usuario/login, nao por area.

## Configuracao por area

Substituir o singleton global:

```python
ConfiguracaoSistema.get_singleton()
```

por acesso contextual:

```python
ConfiguracaoSistema.get_for_area(area)
```

ou:

```python
get_configuracao_sistema(request)
```

O registro de configuracao deixa de ser `pk=1` e passa a ser unico por area:

```python
area = models.OneToOneField("usuarios.AreaTrabalho", on_delete=models.CASCADE)
```

Isso permite:

- ASCOM com cabecalho, chefia, unidade, sufixo e assinaturas proprias;
- DPCAP com cabecalho, chefia, unidade, sufixo e assinaturas proprias;
- numeracao de Plano de Trabalho separada.

## Google Drive por usuario

`DriveCredenciais` deve ganhar:

```python
usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```

E todos os pontos que hoje fazem:

```python
DriveCredenciais.objects.first()
```

devem passar a usar:

```python
DriveCredenciais.objects.filter(usuario=request.user).first()
```

ou, em services/tasks sem request:

```python
DriveCredenciais.objects.filter(usuario=usuario).first()
```

Cada usuario autoriza a propria conta institucional uma vez. Ao entrar no
sistema, o usuario usa:

```text
usuario -> area atual para dados/configuracoes
usuario -> credencial Google Drive do proprio usuario
```

A area continua separando os dados. A credencial Google separa a conta de Drive
de cada login.

## Filtros obrigatorios nas views

Toda listagem precisa filtrar pela area atual:

```python
Evento.objects.filter(area=request.area)
Oficio.objects.filter(area=request.area)
Servidor.objects.filter(area=request.area)
```

Todo `get_object_or_404` precisa validar a area:

```python
get_object_or_404(Evento, pk=pk, area=request.area)
```

Isso e mais importante que a tela de login. Sem esse filtro, um usuario poderia
abrir uma URL direta de outra area.

## Numeracoes separadas

As constraints de numeracao devem incluir `area`.

Exemplo para oficios:

```python
UniqueConstraint(
    fields=["area", "ano", "numero"],
    condition=Q(ano__isnull=False, numero__isnull=False),
    name="oficios_oficio_area_ano_numero_unique",
)
```

E a busca do proximo numero deve usar:

```python
Oficio.objects.filter(area=area, ano=ano)
```

Assim ASCOM pode ter `75/2026` e DPCAP tambem pode ter `75/2026`, sem conflito.

## Middeware/contexto recomendado

Criar middleware que resolve a area atual:

1. usuario nao autenticado: sem area;
2. usuario com uma area: define `request.area`;
3. usuario com varias areas: usa `request.session["area_id"]`;
4. se a area da sessao nao pertence ao usuario: limpa sessao e exige selecao.

Tambem e util criar:

```python
core.tenancy.get_current_area()
core.tenancy.get_area_from_request(request)
```

para services antigos que ainda nao recebem `request`, mas a refatoracao ideal
e passar `area` explicitamente para services e selectors.

## Ordem segura de implementacao

1. Criar `AreaTrabalho` e `VinculoUsuarioArea`.
2. Criar middleware/seletor de area atual.
3. Migrar `ConfiguracaoSistema` de singleton global para configuracao por area.
4. Migrar `DriveCredenciais` para credenciais por usuario.
5. Adicionar `area` aos modelos principais: eventos, oficios, roteiros,
   documentos, cadastros, planos de trabalho, ordens de servico e prestacoes.
6. Atualizar selectors/views/forms para filtrar sempre por `request.area`.
7. Atualizar numeracoes e constraints para incluir `area`.
8. Atualizar Google Drive services, signals e Celery tasks para carregar
   credenciais pelo usuario autenticado/responsavel pela acao.
9. Migrar dados existentes para uma area inicial, por exemplo ASCOM.
10. Criar testes de isolamento: usuario ASCOM nao ve nem acessa dados DPCAP.

## Migracao dos dados atuais

Antes de adicionar `area` como obrigatoria, criar uma area inicial:

```text
nome: Assessoria de Comunicacao Social
sigla: ASCOM
```

Depois preencher todos os registros existentes com essa area. So entao tornar
`area` obrigatoria nos modelos de negocio.

## Checklist de aceite

- Usuario ASCOM 1 e ASCOM 2 veem os mesmos dados da ASCOM.
- Usuario DPCAP nao ve eventos, oficios, servidores, viaturas ou documentos da
  ASCOM.
- Configuracoes da ASCOM nao alteram configuracoes da DPCAP.
- Cada usuario conecta sua conta/pasta propria do Google Drive.
- Uploads e reorganizacao do Drive usam a credencial Google do usuario correto.
- Numeracao de oficios e planos e independente por area.
- URLs diretas de outra area retornam 404 ou permissao negada.
- Testes cobrem listagem, detalhe, criacao, edicao, exclusao por area e Drive por usuario.
