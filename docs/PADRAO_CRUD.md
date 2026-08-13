# Padrao CRUD

## Escopo atual

No app `cadastros`, o padrao CRUD esta consolidado para `Unidade`, `Cargo`, `Combustivel`, `Servidor`, `Viatura`, `Cidade`, `Estado` e a tela de **Configuracao do sistema** (`ConfiguracaoSistema` / assinaturas por tipo). Como regra de navegacao, `Cidade` integra menu lateral e landing principal; `Estado` permanece como base administrativa interna (rota ativa e acessivel na landing de base interna).

`Motorista` nao e entidade de cadastro.

O app `roteiros` possui CRUD publico em `/roteiros/` (listagem, novo, editar, detalhe, excluir) como **modulo referencia** de arquitetura (`selectors`, `services/roteiro_editor`, `presenters`, components de dominio). O Django Admin permanece disponivel.

## Estrutura

- `forms.py`: validacao, normalizacao e mascaras de entrada.
- `selectors.py`: consultas e busca por `q`.
- `services.py` ou `services/`: criacao, atualizacao e exclusao fisica (ex.: `roteiros/services/roteiro_editor.py`).
- `presenters.py`: dados dos cards sem HTML.
- metadados de listagem simples e cards devem usar contrato coerente (`title`, `meta`, `badges`, `actions` quando aplicável), sem montar HTML no presenter.
- `views.py`: fluxo request/form/service/messages/redirect.
- integrações HTTP externas devem ser delegadas para service/infra (sem `requests` direto em view).
- `urls.py`: rotas nomeadas padronizadas.
- `templates/`: composicao com components globais.

## Roteiros base

- `models.py`: `Roteiro` e trechos associados.
- `admin.py`: cadastro manual auxiliar.
- `selectors.py`: listagem, detalhe, trechos, cidades para select, estimativa.
- `services/roteiro_editor.py`: fluxo do wizard avulso e exclusao com `ProtectedError`.
- `presenters.py`: card, contexto de formulario (dono da montagem desde o `BE-13` fatia 2; o estado vem do `services/editor_state_builder.py`), pagina de detalhe.
- `views.py`: orquestracao magra; endpoints de diarias e estimativa.
- `templates/roteiros/` + `templates/components/travel/`: UI componentizada.

Vinculos documentais em Oficios/Planos/OS usam o roteiro como referencia; esses modulos nao foram alterados nesta etapa.

## Regras de exclusao

- Exclusao sempre fisica.
- Em vinculo impeditivo, bloquear com:

```text
Não foi possível excluir este cadastro porque ele está vinculado a outros registros.
```

## Regras especificas

- Servidor: nome unico em maiusculo, sem matricula, cargo obrigatorio no form, CPF validado, RG opcional ou `sem_rg`, telefone opcional com unicidade quando preenchido.
- Viatura: sem marca/unidade, placa validada (AAA1234 ou AAA1A23), modelo obrigatorio, combustivel selecionavel e tipo fixo.
- Cargo e Combustivel: nomes unicos em maiusculo; `is_padrao` opcional (um padrao por tipo).
- Configuracao: formulario singleton + escolha de servidores para assinatura por tipo de documento (persistencia em `AssinaturaConfiguracao`).

## Frontend

- Sem CSS inline e sem JS inline.
- Mascaras em `static/js/components/masks.js` via `data-mask="cpf|rg|placa|cep|telefone|upper"`.
- Padrao visual global aplicado por components em `templates/components/`.
- Header oficial do CRUD: `components/layout/page_header.html`.
- Confirmacao de exclusao via component global `components/feedback/confirm_delete_block.html`.
- Estados vazios e alertas devem usar os components de feedback reutilizaveis.
- Excecoes de exclusao em Cadastros devem manter contrato visual equivalente ao `confirm_delete_block` (acao danger + cancelamento secundario + contexto de risco).

## Integracao externa (exemplo canônico)

- Consulta de CEP segue o padrão: `views.py` valida entrada e monta `JsonResponse`; service/infra executa chamada ao ViaCEP.
- O contrato de resposta HTTP permanece na borda (view), e a integração fica isolada para manutenção e teste.
