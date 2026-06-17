# eProtocolo - Treinamento/Demo

Esta fase pausa totalmente a integracao real e usa a Central de Protocolos em
modo visual de treinamento/mock. O objetivo e demonstrar a experiencia completa
sem chamar API real, sem credenciais e sem alterar ambiente oficial.

## Como ativar

Use o `.env` local em modo mock:

```env
EPROTOCOLO_AMBIENTE=mock
EPROTOCOLO_BASE_URL=
EPROTOCOLO_TOKEN_URL=
EPROTOCOLO_CLIENT_ID=
EPROTOCOLO_CLIENT_SECRET=
EPROTOCOLO_CONSUMER_ID=
```

Tambem funciona em ambientes sem credenciais, porque `cfg.em_modo_mock()` impede
chamadas HTTP reais.

## Dados simulados

Ao abrir a lista da Central de Protocolos em mock, o sistema cria/atualiza dados
demo idempotentes:

- `24.123.456-7`: oficio em tramitacao, 3 documentos e 1 pendencia.
- `24.987.654-3`: termo aguardando assinatura, 2 assinaturas pendentes.
- `25.111.222-0`: justificativa com pendencia de complemento de PDF.
- `23.555.888-1`: ordem de servico concluida, 5 documentos e historico.

Esses registros sao marcados com `modo_mock=True` e payload `_demo=True`.

## Acoes simuladas

Em mock/treinamento, as acoes usam `protocolos/services.py` e
`integracoes/eprotocolo/mocks.py`:

- atualizar situacao;
- enviar documento;
- solicitar assinatura;
- tramitar;
- concluir cadastro;
- gerar protocolo a partir de documento interno.

As mensagens da interface deixam claro que a operacao foi registrada em
treinamento/mock. Nenhuma dessas acoes chama `EProtocoloClient`.

## Como usar na demonstracao

1. Rode o servidor local normalmente.
2. Acesse a Central de Protocolos.
3. Use a busca/filtro da lista.
4. Abra um protocolo e navegue por Resumo, Documentos, Assinaturas, Pendencias,
   Tramitacoes, Movimentacoes e Logs.
5. Nos documentos internos, use o bloco compacto de integracao para gerar,
   vincular, ver e atualizar protocolos simulados.

## O que depende da API real futuramente

- consulta oficial de protocolo;
- download real de documentos;
- envio real de PDF;
- criacao real de pendencia/assinatura;
- tramitacao oficial;
- criacao e conclusao real de protocolo.

Esses fluxos devem continuar passando pelas travas do modo `real_controlado`
quando a homologacao oficial for retomada.
