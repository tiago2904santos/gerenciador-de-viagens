# eProtocolo — Ambiente de Treinamento (spi-servicos)

Guia da camada de integração **real** com o eProtocolo do Paraná no ambiente de
**treinamento**. A Central de Protocolos continua funcionando em modo mock
quando não há credenciais — nada quebra por ausência de configuração.

> **Escopo desta etapa:** apenas `mock` e `treinamento`. Produção **não** é
> usada nem habilitada aqui.

---

## 1. Objetivo do ambiente de treinamento

Validar, de forma controlada e sem risco para produção:

1. autenticação (token JWT via Central de Segurança);
2. consulta simples (órgãos/locais/assuntos/espécies);
3. criação de protocolo de teste a partir de um Ofício;
4. envio de documento PDF de teste;
5. conclusão do cadastro;
6. consulta de situação, documentos, movimentações e tramitações.

---

## 2. Variáveis `.env` necessárias

Defina no seu `.env` **local** (nunca versionado). Modelo completo em
`.env.example`.

```env
EPROTOCOLO_AMBIENTE=treinamento
EPROTOCOLO_BASE_URL=            # base do barramento spi-servicos (sem /v3)
EPROTOCOLO_TOKEN_URL=           # endpoint OAuth2 da Central de Segurança

EPROTOCOLO_CLIENT_ID=
EPROTOCOLO_CLIENT_SECRET=
EPROTOCOLO_CONSUMER_ID=

EPROTOCOLO_TIMEOUT=30
EPROTOCOLO_VERIFY_SSL=True

# Códigos institucionais (NÃO sensíveis) — exigidos para criar protocolo:
EPROTOCOLO_COD_ORGAO_PADRAO=
EPROTOCOLO_COD_LOCAL_ORIGEM_PADRAO=
EPROTOCOLO_COD_LOCAL_DESTINO_PADRAO=
EPROTOCOLO_COD_ASSUNTO_VIAGEM=
EPROTOCOLO_COD_ESPECIE_OFICIO=
EPROTOCOLO_COD_PALAVRA_CHAVE_VIAGEM=
EPROTOCOLO_COD_TIPO_TRAMITACAO_PADRAO=
```

**Obrigatórios para sair do mock:** `BASE_URL`, `TOKEN_URL`, `CLIENT_ID`,
`CLIENT_SECRET`, `CONSUMER_ID`. Sem qualquer um deles o sistema permanece em
modo mock automaticamente.

**Obrigatórios para criar protocolo de Ofício:** `COD_ORGAO_PADRAO`,
`COD_LOCAL_ORIGEM_PADRAO`, `COD_ASSUNTO_VIAGEM`, `COD_ESPECIE_OFICIO`. O mapper
valida e aborta com mensagem clara se faltarem.

---

## 3. Como rodar o diagnóstico (não chama a API)

```bash
python manage.py eprotocolo_check
python manage.py eprotocolo_check --escopos   # lista também os escopos esperados
```

Mostra ambiente, presença das URLs, `client_id`/`consumer_id` **mascarados** e
se a configuração mínima está OK. Nunca exibe o `client_secret`.

Saída típica (treinamento configurado):

```
Ambiente: treinamento
Base URL: configurada
Token URL: configurada
Client ID: abcd****
Client Secret: configurado
Consumer ID: cons****
Modo real: sim
Produção: não
Status: configuração mínima OK
```

---

## 4. Como rodar o ping (token + 1 consulta read-only)

```bash
python manage.py eprotocolo_ping
```

Gera o token e faz **uma** consulta (órgãos). Não cria, não envia, não tramita.
Em modo mock, valida o fluxo sem tocar a rede.

---

## 5. Como rodar o dry-run de homologação (não altera nada)

```bash
python manage.py eprotocolo_homologar --oficio <ID> --dry-run
```

Localiza o Ofício, monta e **valida** o payload, gera/localiza o PDF, confere a
assinatura `%PDF`, calcula o MD5 e imprime um resumo. **Não** chama a API nem
altera o banco.

---

## 6. Como rodar o teste real controlado (treinamento)

```bash
python manage.py eprotocolo_homologar --oficio <ID> --real
python manage.py eprotocolo_homologar --oficio <ID> --real --concluir
```

O modo `--real` só executa se **todas** as condições forem atendidas:

- `EPROTOCOLO_AMBIENTE=treinamento` (nunca produção);
- credenciais e `BASE_URL`/`TOKEN_URL`/`CONSUMER_ID` configuradas;
- PDF válido e payload válido;
- confirmação explícita digitando `CONFIRMO TREINAMENTO` no terminal
  (use `--sim` apenas em automações controladas).

Fluxo real: token → cria protocolo → salva número → envia PDF → salva código do
documento → (opcional) conclui → consulta situação/documentos/movimentações →
registra logs seguros.

---

## 7. Interpretando erros

| Erro | Provável causa / ação |
|------|------------------------|
| **config ausente** | revisar `BASE_URL`/`TOKEN_URL`/`CLIENT_ID`/`CLIENT_SECRET`/`CONSUMER_ID` |
| **401** | `client_id`/`client_secret`/`token_url` incorretos |
| **403** | escopos/`consumerId`/permissões/IP/VPN |
| **404** | `base_url`/path incorretos |
| **422** | payload inválido (campos obrigatórios) |
| **500** | indisponibilidade do barramento — tentar mais tarde |
| **timeout** | VPN/IP/rede |
| **erro SSL** | certificado/`EPROTOCOLO_VERIFY_SSL` |

---

## 8. Cuidados de segurança

- Credenciais ficam **apenas** no `.env` local; nunca commitar.
- Logs **não** registram `client_secret`, token JWT, `Authorization` nem
  `consumerId` completo; CPF é mascarado.
- Token JWT fica **só em memória** (cache com expiração), nunca no banco.
- Não há sync automático periódico nesta etapa.
- `--real` é limitado a treinamento e exige confirmação manual.

---

## 9. O que ainda depende da Celepar / SEAP / eProtocolo

- URLs oficiais de treinamento (`BASE_URL`, `TOKEN_URL`);
- credenciais (`CLIENT_ID`, `CLIENT_SECRET`, `CONSUMER_ID`);
- liberação dos escopos OAuth2 (seção 10);
- liberação de IP/VPN para acesso ao barramento;
- confirmação dos **paths v3** e do **formato exato dos payloads** de criação,
  documento, tramitação e pendência (hoje seguem o padrão `spi-servicos` e devem
  ser conferidos contra a documentação oficial);
- códigos institucionais (órgão, locais, assunto, espécie, palavra-chave).

---

## 10. Escopos OAuth2 esperados

Solicitar à Celepar/SEAP (lista também disponível via
`python manage.py eprotocolo_check --escopos`):

```
spiserv.protocolos.consultar
spiserv.protocolos.incluir
spiserv.protocolos.concluir
spiserv.protocolos.alterar
spiserv.protocolos.documentos.consultar
spiserv.protocolos.documentos.incluir
spiserv.volumes.documentos.consultar
spiserv.protocolos.movimentacoes.consultar
spiserv.protocolos.tramitacoes.consultar
spiserv.protocolos.tramitacoes.incluir
spiserv.protocolos.pendencias.consultar
spiserv.protocolos.pendencias.incluir
spiserv.protocolos.pendencias.cancelar
spiserv.protocolos.documentos.assinaturas.consultar
spiserv.protocolos.documentos.assinaturas.incluir
spiserv.orgaos.consultar
spiserv.locais.consultar
spiserv.assuntos.consultar
spiserv.especies.consultar
```

---

## 11. Comandos (resumo)

```bash
python manage.py eprotocolo_check
python manage.py eprotocolo_ping
python manage.py eprotocolo_homologar --oficio <ID> --dry-run
python manage.py eprotocolo_homologar --oficio <ID> --real
python manage.py eprotocolo_homologar --oficio <ID> --real --concluir
```
