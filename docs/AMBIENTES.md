# Ambientes: producao e homologacao

Use dois sites separados para trabalhar com seguranca:

- **Producao**: site real, dados reais, branch `main`, banco `central_viagens_prod`.
- **Homologacao**: site de testes, dados descartaveis ou copia controlada, branch `develop`, banco `central_viagens_homolog`.

O ponto mais importante e nunca compartilhar banco de dados nem pasta de arquivos (`MEDIA_ROOT`) entre os dois ambientes.

## Uso local

Enquanto o sistema estiver rodando apenas no seu computador, use:

```powershell
.\scripts\run_local_real.ps1
```

Abre o site real local em:

```text
http://127.0.0.1:8000
```

Esse comando usa o arquivo `.env` atual e o banco configurado nele.

Para testar melhorias sem mexer no real local, use outro terminal:

```powershell
.\scripts\run_local_teste.ps1
```

Abre o site de teste local em:

```text
http://127.0.0.1:8001
```

Na primeira execucao, esse comando cria `.env.local.teste` automaticamente com:

```text
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=dados/local_teste.sqlite3
MEDIA_ROOT=media_teste
STATIC_ROOT=staticfiles_teste
```

Esse ambiente de teste local usa SQLite de proposito, para nao depender da senha de administrador do PostgreSQL e para nao interferir no banco real local.

Se preferir testar tambem com PostgreSQL separado, altere `.env.local.teste` para `DB_ENGINE=django.db.backends.postgresql` e rode:

```powershell
.\scripts\setup_local_teste_db.ps1
```

Se o usuario normal do banco nao tiver permissao para criar bancos, rode uma vez:

```powershell
.\scripts\criar_banco_teste_admin.ps1
```

Esse comando usa o usuario `postgres` e pode pedir a senha de administrador do PostgreSQL. Depois disso, use normalmente o `run_local_teste.ps1`.

## 1. Criar branches

No computador de desenvolvimento:

```powershell
git checkout main
git pull
git checkout -b develop
git push -u origin develop
```

Fluxo recomendado:

```text
feature/minha-melhoria -> develop -> main
```

Na pratica:

```powershell
git checkout develop
git checkout -b feature/minha-melhoria
```

Depois de testar:

```powershell
git checkout develop
git merge feature/minha-melhoria
```

Quando estiver pronto para virar real:

```powershell
git checkout main
git merge develop
```

## 2. Criar bancos separados

Exemplo com PostgreSQL:

```powershell
psql -U postgres -c "CREATE USER central_viagens_prod_user WITH PASSWORD 'troque-esta-senha';"
psql -U postgres -c "CREATE DATABASE central_viagens_prod OWNER central_viagens_prod_user;"
psql -U postgres -d central_viagens_prod -c "GRANT ALL ON SCHEMA public TO central_viagens_prod_user;"

psql -U postgres -c "CREATE USER central_viagens_homolog_user WITH PASSWORD 'troque-esta-senha';"
psql -U postgres -c "CREATE DATABASE central_viagens_homolog OWNER central_viagens_homolog_user;"
psql -U postgres -d central_viagens_homolog -c "GRANT ALL ON SCHEMA public TO central_viagens_homolog_user;"
```

## 3. Criar arquivos `.env` diferentes

Use os modelos:

- `.env.producao.example`
- `.env.homologacao.example`

No servidor de producao, copie o modelo de producao para `.env` dentro da pasta da aplicacao de producao.

No servidor de homologacao, copie o modelo de homologacao para `.env` dentro da pasta da aplicacao de homologacao.

Cada `.env` deve ter:

- `DJANGO_SETTINGS_MODULE=config.settings.prod`
- `DEBUG=False`
- `ALLOWED_HOSTS` com o dominio daquele site
- `DB_NAME`, `DB_USER` e `DB_PASSWORD` exclusivos daquele ambiente
- `MEDIA_ROOT` exclusivo daquele ambiente
- `STATIC_ROOT` exclusivo daquele ambiente

## 4. Rodar migrations em cada ambiente

Em producao:

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

Em homologacao:

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

Esses comandos precisam ser executados separadamente porque cada site aponta para um banco diferente.

## 5. Conferir antes de usar

Em cada ambiente, valide:

```powershell
python manage.py check --deploy
```

Depois entre no admin ou na tela inicial e confirme visualmente:

- o dominio esta correto;
- o login esta ativo;
- os dados da producao nao aparecem na homologacao;
- arquivos gerados em homologacao nao aparecem na producao.

## Regra operacional

Trabalhe e teste primeiro em `develop`/homologacao. So envie para `main`/producao quando a melhoria estiver pronta.
