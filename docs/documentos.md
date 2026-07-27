# Núcleo documental (DOCX / PDF)

Este projeto gera **DOCX** com [docxtpl](https://docxtpl.readthedocs.io/) e **PDF** por dois caminhos distintos. Perceber essa distinção evita confusão com fluxogramas genéricos “DOCX → PDF”.

## Modelos DOCX (`documentos/resources/`)

Os ficheiros seguem o nome do enum `DocumentoTipo` (ex.: `oficio.docx`, `justificativa.docx`, `termo_autorizacao.docx`, `plano_trabalho.docx`, `ordem_servico.docx`). A resolução passa por `DOCUMENTOS_RESOURCES_DIR` e `resolve_resource_docx` (apenas caminhos dentro desse diretório).

### Placeholders

| Documento | Estilo de placeholders no modelo | Contexto passado ao docxtpl |
|-----------|----------------------------------|------------------------------|
| Ofício, Justificativa | Chaves planas `{% raw %}{{ protocolo }}{% endraw %}`, etc. | `docxtpl_context` montado em `oficios.docxtpl_context` |
| Termo, Plano de trabalho, Ordem de serviço | Aninhados `{% raw %}{{ oficio.numero_formatado }}{% endraw %}`, `{% raw %}{{ termo.participante.nome }}{% endraw %}`, … | Payload canónico (`oficios.documents`) sem `docxtpl_context` |

## PDF: motor por defeito

Com `DOCUMENTOS_DEFAULT_PDF_ENGINE=auto` (padrão), o sistema escolhe o melhor
motor disponível. Em produção, para manter fidelidade ao DOCX e baixa latência,
configure `unoserver`; o LibreOffice permanece residente em vez de iniciar um
processo novo a cada PDF.

## PDF: LibreOffice (DOCX preenchido → PDF)

- Defina `DOCUMENTOS_DEFAULT_PDF_ENGINE=libreoffice`, **ou**
- Em falha do WeasyPrint (ex.: DLL GTK em falta no Windows), a façade tenta converter o **DOCX já renderizado** com o binário `soffice`.

Deteção do executável:

- `DOCUMENTOS_LIBREOFFICE_BINARY` (caminho explícito para `soffice` / `soffice.exe`), **ou**
- Pesquisa em `PATH`, pastas típicas de instalação e variáveis `SOFFICE_PATH` / `LIBREOFFICE_SOFFICE`.

## Último recurso: PDF simples (`fpdf2`)

Em desenvolvimento no Windows, se WeasyPrint e LibreOffice falharem, pode ativar-se `DOCUMENTOS_SIMPLE_PDF_FALLBACK` (em `config.settings.dev` fica `True` por omissão salvo override no ambiente). O resultado é um PDF de texto mínimo, sem fidelidade ao layout institucional.

## Variáveis de ambiente (resumo)

| Variável | Função |
|----------|--------|
| `DOCUMENTOS_RESOURCES_DIR` | Pasta dos `.docx` (default: `BASE_DIR/documentos/resources`) |
| `DOCUMENTOS_DEFAULT_PDF_ENGINE` | `auto`, `unoserver`, `libreoffice`, `word_com`, `weasyprint` ou `simple` |
| `DOCUMENTOS_LIBREOFFICE_BINARY` | Caminho do `soffice` |
| `DOCUMENTOS_SIMPLE_PDF_FALLBACK` | `true` para permitir PDF mínimo em dev |
| `DOCUMENTOS_PERSIST_ARTEFATOS` | `false` na suíte de testes; em produção grava artefactos em `MEDIA_ROOT` |
| `MEDIA_ROOT` / `MEDIA_URL` | Armazenamento de ficheiros gerados |

## CI (Linux)

O workflow em `.github/workflows/tests.yml` instala **LibreOffice** no runner Ubuntu para que testes ou conversões que dependam de `soffice` possam correr; WeasyPrint pode exigir bibliotecas de sistema adicionais se forem adicionados testes que invoquem o motor HTML real.
