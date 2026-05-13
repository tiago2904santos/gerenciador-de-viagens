# Núcleo Documental

## Objetivo desta fase

Transformar `documentos/` em base técnica real para evolução document-centric, sem antecipar CRUDs completos de `oficios`, `termos`, `planos_trabalho` e `ordens_servico`.

## O que já existe

- Pacote `documentos/services/` com contratos e implementações seguras de base:
  - `types.py`: tipos e formatos de documento.
  - `registry.py`: registro de tipos suportados.
  - `validators.py`: contrato de validação e validador neutro.
  - `filenames.py`: resolução de nomes de arquivo.
  - `renderers/base.py`: contrato padrão de renderização.
  - `renderers/docx_renderer.py` e `renderers/pdf_renderer.py`: wrappers seguros (sem dependência obrigatória de ambiente).
- `documentos/views.py` mantém a index e passa a expor status do núcleo.

## O que é contrato (e deve permanecer estável)

- Enum de formato (`DocumentoFormato`) e enum de tipo (`DocumentoTipo`).
- Registro central de tipos (`default_document_registry`).
- Assinatura de validação (`DocumentValidator` + `ValidationResult`).
- Assinatura de render (`RenderRequest` -> `RenderResult`) e erros de indisponibilidade (`RendererUnavailableError`).
- Geração de nome de arquivo (`build_document_filename`), sem lógica de domínio acoplada.

## O que depende dos apps de domínio

Ainda não faz parte deste núcleo:

- montagem de contexto de negócio (campos de Ofício/Termo/PT/OS);
- validações específicas de regra funcional por domínio;
- pipeline final de geração por template real e download por fluxo de negócio;
- assinatura digital, snapshots e integrações externas.

Essas responsabilidades serão adicionadas pelos apps de domínio, consumindo o núcleo atual como infraestrutura.

## Como os próximos apps devem consumir

- `oficios`, `termos`, `planos_trabalho` e `ordens_servico` devem:
  1. montar payload de domínio no próprio service;
  2. validar payload com validator específico (contrato de `validators.py`);
  3. resolver nome de arquivo via `build_document_filename`;
  4. chamar renderer compatível com formato (`DocxRenderer`/`PdfRenderer`) por adapter explícito;
  5. manter views apenas como orquestração HTTP.

## Limites deliberados desta fase

- Sem novas models e sem migrations.
- Sem dependência obrigatória de LibreOffice/Word/stack externa.
- Sem promessa de CRUD documental completo na UI.
