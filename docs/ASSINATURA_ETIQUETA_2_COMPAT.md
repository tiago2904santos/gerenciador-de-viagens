# Assinatura de documentos — contrato vigente

Este documento descreve os dois fluxos de arquivo assinado que existem no Central de Viagens.
O antigo backend criptográfico baseado em pyHanko foi removido junto com os campos de assinatura
de `DocumentoArtefato` na migration `documentos/0003_remove_assinatura_fields.py`.

## 1. Anexo manual de PDF assinado

`DocumentoArtefato` guarda o PDF gerado e, opcionalmente, um PDF assinado fora do sistema. O
serviço `documentos.services.persistence.anexar_arquivo_assinado`:

- aceita somente nome `.pdf` e conteúdo que começa com a assinatura binária de PDF;
- calcula SHA-256 e cria uma `DocumentoAssinaturaVersao` imutável;
- preserva versões anteriores quando o arquivo é substituído;
- faz o download preferir o arquivo assinado enquanto ele estiver ativo.

Remover o anexo revoga a versão corrente, mas não apaga o histórico. Esse fluxo registra e
preserva um documento recebido; ele não valida certificado digital, PAdES ou cadeia ICP-Brasil.

## 2. Assinatura eletrônica da prestação de contas

Relatórios técnicos e diários de bordo usam `prestacoes_contas.AssinaturaDocumento`. Após confirmar
a identidade esperada, o sistema recebe a imagem da assinatura, aplica um carimbo ao PDF com
`pypdf` + `reportlab`, grava posição, instante, IP, hash do documento de origem e um código de
verificação. A implementação vive em `prestacoes_contas/assinatura_services.py`.

O hash e o código dão rastreabilidade ao registro da aplicação. Eles não transformam o carimbo em
assinatura digital qualificada. Quando houver exigência jurídica de ICP-Brasil, a assinatura deve
ser realizada por uma solução institucional externa e o PDF resultante pode entrar pelo fluxo de
anexo manual.

## Dependências e provas

- `pypdf` e `reportlab`: composição do carimbo no PDF;
- `hashlib` da biblioteca padrão: integridade e rastreabilidade;
- `documentos/tests/test_assinatura_manual.py`: anexo, substituição, histórico, remoção e download;
- `prestacoes_contas/tests_assinatura.py` e `prestacoes_contas/test_assinatura_publica.py`:
  identidade, carimbo, código e acesso público.

Não há import, configuração ou caminho de execução de pyHanko no código de produção.
