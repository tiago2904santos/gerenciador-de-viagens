# Álbum de telas — 05/08/2026

Inventário visual do sistema inteiro: **122 telas × 2 temas = 244 capturas**.

Não é registro histórico como as auditorias — é um instrumento, e deve ser
regerado quando a interface mudar de forma relevante.

## O que tem aqui

```
light/NNN-<grupo>-<tela>.webp   captura no tema claro
dark/NNN-<grupo>-<tela>.webp    captura no tema escuro
_relatorio.json                 rota, status HTTP, altura e arquivo de cada captura
```

As imagens são WebP com 880 px de largura (q70). Os PNG originais da captura
(1440×900, página inteira) não são versionados: 244 arquivos passavam de 140 MB.
Para tê-los em resolução cheia, rode a captura de novo — o passo 2 abaixo.

## Como regerar

```bash
source .venv/bin/activate
python manage.py resetar_banco_demo                    # 1. banco de demonstração
python manage.py runserver 127.0.0.1:8000 --noreload & # 2. servidor
python scripts/album_telas.py                          # 3. captura os PNG
python scripts/album_pagina.py screenshots/album-sistema  # 4. monta album.html
```

`album.html` é uma página única e autocontida (imagens embutidas como data URI);
abre offline e não é versionada — o passo 4 a reconstrói em segundos.

Usuário e senha da captura vêm de `ALBUM_USUARIO`/`ALBUM_SENHA`. O álbum só deve
ser gerado contra banco de demonstração; **nunca contra base com dado real.**

## Cobertura

Toda rota que renderiza página entrou, incluindo os estados que só existem
depois de um clique — a edição em linha dos catálogos (`P-02` tirou a página
de edição própria) e os diálogos de confirmação de exclusão.

Ficaram de fora, por não serem tela: endpoints de API/JSON e autosave, download
de arquivo, visualização inline de PDF, rotas POST-only (excluir, cancelar,
definir padrão), o fluxo público de assinatura (exige token vivo) e o Django
admin.

## Duas telas faltam — as duas devolvem 500

Reproduzem em qualquer PK do banco de demonstração. Ainda **sem ID de defeito**;
precisam entrar no catálogo da auditoria correspondente antes de serem
corrigidas.

| Rota | Causa |
|---|---|
| `/termos/oficio/<pk>/preview/` | `termos/views.py:693` serializa o contexto com `DjangoJSONEncoder`, e o contexto carrega uma instância de `Cidade` — `TypeError: Object of type Cidade is not JSON serializable`. |
| `/planos-trabalho/<pk>/identificacao/` | `templates/planos_trabalho/partials/resumo_evento_card.html:17` usa `total` dentro do mesmo `{% with %}` que o define. O Django resolve todos os valores do `with` contra o contexto de fora, então o lookup falha em qualquer plano com mais de um evento. |
