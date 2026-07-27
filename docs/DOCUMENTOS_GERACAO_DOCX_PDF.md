# Geração de documentos DOCX e PDF (multiplataforma)

Este guia descreve como o núcleo `documentos` gera ficheiros, que motores de PDF existem em cada sistema operativo, e como diagnosticar ou preparar o ambiente **fora** de pedidos HTTP.

## Regra importante

**Nunca** instalar pacotes de sistema, LibreOffice, Word nem correr `pip install` automaticamente durante um request HTTP. A aplicação apenas tenta gerar o ficheiro; falhas de motor resultam em erro tratado (redirect com mensagem nos downloads de PDF de ofícios e documentos associados) ou excepção em contextos não web. Use os comandos de gestão abaixo a partir do terminal.

## DOCX

- Modelos em `documentos/resources/` (nomes alinhados a `DocumentoTipo`).
- Dependências Python: `docxtpl`, `python-docx` (em `requirements/base.txt`).
- Se faltar pacote Python, instale manualmente, por exemplo: `python -m pip install docxtpl python-docx`.

## Motores de PDF

### Valor `auto` (`DOCUMENTOS_DEFAULT_PDF_ENGINE=auto`)

É o valor por omissão em `config/settings/base.py`. A resolução escolhe uma cadeia de motores conforme o SO e a disponibilidade real (binários, imports, DLLs). Ordem típica:

| SO | Ordem preferencial (resumo) |
|----|------------------------------|
| Windows | Word COM (se `pywin32` / `docx2pdf` e Word disponíveis) → LibreOffice → WeasyPrint → PDF simples (`fpdf2`) se permitido |
| Linux | LibreOffice → WeasyPrint → PDF simples se permitido |
| macOS | LibreOffice → WeasyPrint → PDF simples se permitido |

Para **ofício** e outros fluxos com `docxtpl_context`, a façade prefere conversão a partir do **DOCX preenchido** (Word ou LibreOffice) antes de cair em HTML + WeasyPrint, para manter fidelidade ao modelo.

### Motores explícitos

Valores suportados na configuração (quando não usa `auto`): `word_com`, `libreoffice`, `weasyprint`, `simple`.

- **word_com**: apenas Windows; dependências opcionais em `requirements/windows.txt` (`docx2pdf`, `pywin32`).
- **libreoffice**: binário `soffice`; deteção alargada (PATH, `SOFFICE_PATH`, `LIBREOFFICE_SOFFICE`, `DOCUMENTOS_LIBREOFFICE_BINARY`, pastas típicas Windows/Linux/macOS).
- **weasyprint**: render HTML/CSS; no Windows pode falhar por falta de GTK/Pango — o relatório de ambiente indica o erro.
- **simple**: último recurso com `fpdf2`; layout mínimo, sem fidelidade institucional.

### Degradação e fallback

- **`DOCUMENTOS_PDF_AUTO_FALLBACK`**: quando `True`, se o motor pedido falhar, tenta os seguintes na ordem definida para o SO. Em `config/settings/dev.py` tende a estar `True` por omissão (salvo variável de ambiente).
- **`DOCUMENTOS_SIMPLE_PDF_FALLBACK`**: permite o motor `simple` / PDF mínimo como último recurso (útil em desenvolvimento; desligado por omissão em produção se não definido).

### UNOSERVER

`DOCUMENTOS_UNOSERVER_URL` ativa o cliente XML-RPC oficial do unoserver. O
serviço mantém o LibreOffice residente e evita reiniciar a suíte em cada PDF.
Use, por exemplo, `http://libreoffice:2003` junto de
`deploy/docker-compose.documentos.yml`. A porta não possui autenticação e deve
ficar restrita à rede interna do serviço.

No deploy tradicional com systemd, use `http://127.0.0.1:2003` e siga a
seção **5.4 UNOSERVER** de `docs/DEPLOY_VPS.md`. Definir apenas a URL sem manter
o serviço ativo faz o resolver cair para o LibreOffice por processo, que
preserva a geração, mas não o SLA de latência.

## Comandos de gestão

### `python manage.py documentos_check`

Imprime um relatório do ambiente (DOCX, motores PDF, LibreOffice, Word COM, WeasyPrint, `fpdf2`). Opções:

- `--json`: saída em JSON.
- `--verbose`: mais detalhe.

Códigos de saída: `0` se DOCX e PDF estão disponíveis; `1` se o PDF não está disponível mas o DOCX sim; `2` se o DOCX não está disponível.

### `python manage.py documentos_setup_pdf`

Sugere ou executa comandos **no terminal** para instalar dependências Python ou pacotes de sistema (consoante deteta `winget`, `choco`, `apt`, `dnf`, `pacman`, `brew`). Opções importantes:

- **`--dry-run`**: apenas lista o que faria.
- **`--yes`**: executa os comandos listados (use com consciência).
- **`--python-only`**: apenas `pip` para pacotes DOCX/PDF em Windows.
- **`--engine`**: foco num motor (`libreoffice`, `weasyprint`, etc.).

Não usa `sudo` em silêncio sem avisos explícitos na saída quando aplicável.

### `python manage.py documentos_unoserver_check --benchmark --representative-resources --max-ms 1000 --iterations 3`

Valida a porta e executa conversões reais sem cache usando os maiores modelos
DOCX e XLSX do sistema. O comando termina com erro quando qualquer execução
fica acima do SLA informado; use-o após cada deploy do conversor. A CI usa três
execuções por formato e bloqueia a entrega se alguma atingir 1 s.

Conversões DOCX/XLSX idênticas usam cache por SHA-256 após a primeira execução.
Configure `REDIS_URL` em produção para compartilhar esse cache entre workers.

## Variáveis de ambiente (referência)

| Variável | Descrição |
|----------|-----------|
| `DOCUMENTOS_DEFAULT_PDF_ENGINE` | `auto` (omissão), `unoserver`, `word_com`, `libreoffice`, `weasyprint`, `simple` |
| `DOCUMENTOS_PDF_AUTO_FALLBACK` | `true` / `false` — tentar motores alternativos após falha |
| `DOCUMENTOS_LIBREOFFICE_BINARY` | Caminho explícito para `soffice` |
| `DOCUMENTOS_UNOSERVER_URL` | URL XML-RPC interna do unoserver persistente |
| `DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS` | Timeout da verificação rápida do serviço |
| `DOCUMENTOS_ENGINE_PROBE_CACHE_SECONDS` | Janela para reutilizar as sondas de disponibilidade dos motores |
| `DOCUMENTOS_BINARY_CONVERSION_CACHE` | Reutilizar PDF convertido pela hash exata do DOCX/XLSX |
| `DOCUMENTOS_BINARY_CACHE_SECONDS` | TTL do PDF convertido no Redis/cache Django |
| `DOCUMENTOS_SIMPLE_PDF_FALLBACK` | Permitir PDF mínimo `fpdf2` |
| `DOCUMENTOS_ENABLE_LIBREOFFICE` | Flag em `settings` (ex.: `deploy/docker-compose.documentos.yml`); reservada para cenários com LibreOffice em contentores |
| `DOCUMENTOS_TMP_DIR` | Pasta temporária para conversões |
| `DOCUMENTOS_PERSIST_ARTEFATOS` | Persistir artefactos gerados em `MEDIA_ROOT` |
| `DOCUMENTOS_OFICIO_PDF_VIA_DOCX` | Se `False`, altera o ramo de ofício (facade); omissão `True` |

Variáveis adicionais reconhecidas pelo resolver: `SOFFICE_PATH`, `LIBREOFFICE_SOFFICE`.

## Erros no browser

Quando um download de **PDF** falha por configuração de motor, as vistas de download redireccionam para o passo **Documentos** do wizard do ofício e mostram uma mensagem de erro (DOCX não é afectado pelo mesmo redirect de motor).

## Validação local sugerida

```powershell
python manage.py check
python manage.py test documentos
python manage.py test oficios
```

## Documentação relacionada

- [documentos.md](documentos.md) — visão original do núcleo (placeholders, CI).
