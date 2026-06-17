# eProtocolo - Real Controlado

Este guia documenta a homologacao real/controlada da integracao Django com o
eProtocolo. O objetivo inicial e validar acesso real em modo somente consulta,
sem alterar protocolo oficial.

## 1. Modos de uso

- `mock`: nao chama rede; usado em desenvolvimento e testes automatizados.
- `treinamento`: chama o ambiente real de treinamento quando ha credenciais.
- `real_controlado`: chama o ambiente real autorizado, com mutacoes bloqueadas
  por padrao.

## 2. Variaveis do `.env`

Preencha valores reais somente no `.env` local. Nao versionar credenciais.

```env
EPROTOCOLO_AMBIENTE=real_controlado

EPROTOCOLO_BASE_URL=
EPROTOCOLO_TOKEN_URL=

EPROTOCOLO_CLIENT_ID=
EPROTOCOLO_CLIENT_SECRET=
EPROTOCOLO_CONSUMER_ID=

EPROTOCOLO_TIMEOUT=30
EPROTOCOLO_VERIFY_SSL=True

EPROTOCOLO_REAL_READONLY=True
EPROTOCOLO_REAL_MUTATIONS_ENABLED=False

EPROTOCOLO_COD_ORGAO_PADRAO=
EPROTOCOLO_COD_LOCAL_ORIGEM_PADRAO=
EPROTOCOLO_COD_LOCAL_DESTINO_PADRAO=
EPROTOCOLO_COD_ASSUNTO_VIAGEM=
EPROTOCOLO_COD_ESPECIE_OFICIO=
EPROTOCOLO_COD_TIPO_TRAMITACAO_PADRAO=
```

Com `EPROTOCOLO_REAL_READONLY=True`, nenhuma mutacao real deve passar. Com
`EPROTOCOLO_REAL_MUTATIONS_ENABLED=False`, criacao, anexo, pendencia,
assinatura, conclusao e tramitacao ficam bloqueadas.

## 3. Check real

```bash
python manage.py eprotocolo_check_real
```

O comando valida configuracao minima, timeout e SSL. Ele nao chama rede, nao
consulta protocolo e nao altera o banco. Segredos aparecem apenas mascarados ou
como "configurado".

## 4. Ping real

```bash
python manage.py eprotocolo_ping_real
```

O comando gera token em memoria, faz uma consulta simples de tabela auxiliar e
registra log seguro. Ele nao cria protocolo, nao salva token e nao altera o
eProtocolo.

Interpretacao rapida:

- `401`: revisar `client_id`, `client_secret` e `token_url`.
- `403`: revisar `consumerId`, escopos, usuario, orgao/local, IP ou VPN.
- `404`: revisar `base_url` e path.
- `422`: revisar parametros/payload.
- `timeout`: revisar rede, VPN ou IP liberado.
- `SSL`: revisar certificado, proxy ou rede.

## 5. Consultar protocolo real

```bash
python manage.py eprotocolo_consultar_real --protocolo <NUMERO>
```

Consulta dados gerais, documentos, documentos do volume, tramitacoes,
movimentacoes, pendencias e assinaturas de documentos quando houver codigo de
documento. Nao baixa documentos, nao mostra documentos completos e nao altera o
eProtocolo.

## 6. Importar/espelhar protocolo real

```bash
python manage.py eprotocolo_importar_real --protocolo <NUMERO>
```

Consulta o protocolo e cria/atualiza o espelho local em `Protocolo`, documentos,
tramitacoes, movimentacoes e pendencias. A origem local fica marcada como
`eprotocolo_real`. O comando usa codigos externos/datas/metadados para evitar
duplicidade e nao baixa arquivos automaticamente.

## 7. Por que mutacoes ficam bloqueadas

Operacoes como anexar, assinar, tramitar e criar protocolo podem movimentar
processos oficiais. Por isso, no real controlado elas exigem todos os itens:

- `EPROTOCOLO_AMBIENTE=real_controlado`
- `EPROTOCOLO_REAL_READONLY=False`
- `EPROTOCOLO_REAL_MUTATIONS_ENABLED=True`
- flag `--real`
- um unico protocolo por execucao
- confirmacao manual digitando exatamente `CONFIRMO OPERACAO REAL`
- log seguro no sistema

## 8. Comandos perigosos/controlados

Nao executar sem autorizacao institucional clara.

```bash
python manage.py eprotocolo_anexar_real --protocolo <NUMERO> --arquivo <PDF> --real
python manage.py eprotocolo_pendencia_real --protocolo <NUMERO> --documento <CODIGO> --cpf <CPF> --tipo assinatura --real
python manage.py eprotocolo_tramitar_real --protocolo <NUMERO> --local-destino <CODIGO> --parecer "..." --real
python manage.py eprotocolo_criar_real --oficio <ID> --real
```

`eprotocolo_criar_real` aceita `--concluir`, mas conclusao tambem e uma acao
real. Use apenas se houver autorizacao explicita.

## 9. Primeira execucao real recomendada

```bash
python manage.py eprotocolo_check_real
python manage.py eprotocolo_ping_real
python manage.py eprotocolo_consultar_real --protocolo <NUMERO_REAL_AUTORIZADO>
```

Se a consulta funcionar:

```bash
python manage.py eprotocolo_importar_real --protocolo <NUMERO_REAL_AUTORIZADO>
```

Nao executar anexo, pendencia, assinatura, tramitacao ou criacao nesta primeira
fase.

## 10. Seguranca e logs

O client e os services mascaram `Authorization`, token, `client_secret`,
`consumerId` e CPFs quando persistem payloads ou exibem diagnosticos. Token JWT
permanece apenas em cache de memoria do processo e nao e salvo no banco.
