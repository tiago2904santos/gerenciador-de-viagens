# Documentos Núcleo V1

## Objetivo

Consolidar `documentos/services` como infraestrutura documental reutilizável, sem CRUD completo de domínio e sem dependência de runtime em `legacy/`.

## API pública

- `DocumentoTipo`, `DocumentoFormato`, `DocumentoTipoDefinicao`;
- `DocumentoRegistry`, `default_document_registry`;
- `DocumentTemplateDefinition`, `DocumentTemplateRegistry`, `default_template_registry`;
- `ValidationResult`, `DocumentValidatorRegistry`, `ensure_required_fields`;
- `extract_placeholders`, `ensure_required_placeholders`, `ensure_no_unresolved_placeholders`;
- `DocumentRenderRequest`, `DocumentRenderResult`, `DocumentRenderer`, `NoopDocumentRenderer`, `render_document`;
- `build_document_filename`;
- `build_download_response`;
- exceções de núcleo (`DocumentError` e subclasses).

## Fluxo técnico padrão

1. app de domínio (ex.: `oficios`) monta `payload`;
2. valida campos obrigatórios e regras específicas por tipo;
3. valida tipo no `DocumentoRegistry` e formato permitido para o tipo;
4. busca template no `DocumentTemplateRegistry` para `(tipo, formato)`;
5. valida placeholders obrigatórios e detecta placeholders não resolvidos;
6. seleciona renderer e valida disponibilidade/compatibilidade de formato;
7. executa `render_document(...)` e recebe `(DocumentRenderResult, filename)`;
8. retorna download com `build_download_response(...)`.

## Contrato de erros de renderização

No núcleo V1, `render_document(...)` falha de forma previsível com:

- `UnsupportedDocumentType`: tipo não registrado;
- `UnsupportedDocumentFormat`: formato não permitido para o tipo ou renderer incompatível;
- `DocumentTemplateNotFound`: template não registrado para `(tipo, formato)`;
- `DocumentValidationError`: placeholder obrigatório ausente no payload;
- `UnresolvedPlaceholderError`: placeholder permaneceu no conteúdo após substituição;
- `DocumentRendererUnavailable`: renderer não disponível para executar o formato.

## Consumo futuro por Ofícios

`oficios/services.py` deve orquestrar:

- validação funcional do ofício (número, assunto, período, assinatura etc.);
- construção de payload;
- chamada ao núcleo em `documentos/services`;
- retorno HTTP pela view apenas com resposta final e mensagens.

Assim, regras documentais ficam desacopladas de request/template HTML e permanecem reutilizáveis por `termos`, `justificativas`, `planos_trabalho` e `ordens_servico`.

## PDF no V1 (hardening)

- PDF pode aparecer como formato conceitualmente permitido no `DocumentoRegistry`.
- Isso **não** implica geração final de produção nesta fase.
- A geração em PDF depende simultaneamente de:
  - template registrado para PDF;
  - renderer compatível e disponível;
  - backend/conversor da próxima fase.
- Quando esses pré-requisitos não existem, o núcleo deve falhar com exceção explícita (nunca silenciosamente).

## Fora de escopo desta fase

- CRUD completo de Ofícios;
- geração DOCX final de produção;
- conversão PDF por stack externa obrigatória;
- templates DOCX definitivos de cada domínio;
- mudanças visuais em Roteiros.
