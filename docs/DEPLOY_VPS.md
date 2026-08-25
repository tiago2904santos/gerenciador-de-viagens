# Deploy — Hostinger VPS (Ubuntu 22.04/24.04)

Guia completo para hospedar o Gerenciador de Viagens 3.0 em produção com até ~10 usuários simultâneos.

---

## 1. Plano Recomendado na Hostinger

### Escolha: **KVM 2** (ou equivalente)

| Recurso | KVM 1 | **KVM 2 (recomendado)** | KVM 4 |
|---|---|---|---|
| vCPU | 1 | **2** | 4 |
| RAM | 4 GB | **8 GB** | 16 GB |
| Disco | 50 GB NVMe | **100 GB NVMe** | 200 GB NVMe |
| Banda | 1 Gbps | **1 Gbps** | 1 Gbps |
| Preço aprox. | ~R$35/mês | **~R$65/mês** | ~R$130/mês |

**Por que KVM 2 e não KVM 1?**
- WeasyPrint (geração de PDF) é intensivo em memória (~300-500 MB por render)
- PostgreSQL precisa de RAM para cache de queries
- Com 5-10 usuários simultâneos, 4 GB pode ficar apertado ao gerar documentos grandes
- KVM 2 dá folga confortável e permite crescer sem migrar

**Sistema operacional:** Ubuntu 22.04 LTS (suporte até 2027) ou 24.04 LTS

---

## 2. Configuração Inicial do Servidor

### 2.1 Primeiro acesso (como root)

```bash
# Conecte via SSH com o IP e senha que a Hostinger enviou por e-mail
ssh root@SEU_IP_VPS

# Atualize o sistema
apt update && apt upgrade -y
```

### 2.2 Crie um usuário não-root para a aplicação

```bash
adduser viagens
usermod -aG sudo viagens

# Copie sua chave SSH para o novo usuário (opcional, mas recomendado)
rsync --archive --chown=viagens:viagens ~/.ssh /home/viagens
```

### 2.3 Instale as dependências de sistema

```bash
# Execute como root ou com sudo
apt install -y \
    python3.12 python3.12-venv python3.12-dev python3-pip \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    git \
    build-essential libpq-dev \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
    libffi-dev libcairo2 libgdk-pixbuf2.0-0 \
    shared-mime-info fonts-liberation fonts-dejavu-core
```

> `redis-server` é o broker do Celery para gerar PDF/DOCX/XLSX fora do request
> e sincronizar o Drive (seção 5.3). Redis, worker e beat são obrigatórios em
> produção; sem a fila, novos downloads falham rápido em vez de bloquear o web worker.

> **Por que essas libs?** `libpango`, `libcairo` e `libharfbuzz` são exigidas pelo WeasyPrint para renderizar HTML em PDF. Sem elas, a geração de documentos falha silenciosamente.

### 2.4 Configure o firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
ufw status
```

---

## 3. Banco de Dados (PostgreSQL)

```bash
# Entre no PostgreSQL como superusuário
sudo -u postgres psql

# Dentro do psql, execute:
CREATE USER viagens_user WITH PASSWORD 'CRIE-UMA-SENHA-FORTE-AQUI';
CREATE DATABASE viagens_prod OWNER viagens_user;
GRANT ALL PRIVILEGES ON DATABASE viagens_prod TO viagens_user;
\q
```

---

## 4. Código da Aplicação

### 4.1 Clone o repositório

```bash
# Crie o diretório da aplicação
sudo mkdir -p /var/www/gerenciador-viagens
sudo chown viagens:viagens /var/www/gerenciador-viagens

# Como usuário viagens
su - viagens
cd /var/www/gerenciador-viagens

git clone https://github.com/tiago2904santos/gerenciador-de-viagens.git app
cd app
```

### 4.2 Crie e ative o ambiente virtual

```bash
python3.12 -m venv /var/www/gerenciador-viagens/venv
source /var/www/gerenciador-viagens/venv/bin/activate

pip install --upgrade pip
pip install -r requirements/prod.txt
```

### 4.3 Configure as variáveis de ambiente

```bash
# Copie o template de produção
cp .env.production.example .env

# Edite com seus valores reais
nano .env
```

**Campos obrigatórios no `.env`:**

```bash
# Gere a SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Preencha:
- `SECRET_KEY` — use o valor gerado acima
- `ALLOWED_HOSTS` — IP do VPS e/ou domínio (ex: `189.28.100.5,meusite.com.br`)
- `DB_PASSWORD` — senha do banco criada no passo 3
- `MEDIA_ROOT` — `/var/www/gerenciador-viagens/media`
- `STATIC_ROOT` — `/var/www/gerenciador-viagens/staticfiles`
- `DJANGO_SETTINGS_MODULE` — `config.settings.prod`
- `FIELD_ENCRYPTION_KEYS` — cifragem dos tokens do Drive; `prod.py` recusa subir sem ela
- `REDIS_URL` — `redis://127.0.0.1:6379/1` (o Redis do passo 2.3)
- `SENTRY_DSN` — opcional; DSN público do projeto de monitoramento de erros
- `SENTRY_ENVIRONMENT` — nome do ambiente, por exemplo `production`
- `SENTRY_RELEASE` — SHA/tag implantado para correlacionar regressões com deploys

Com `SENTRY_DSN` vazio, nenhum evento sai do servidor. Quando habilitado, o backend recebe
exceções sem PII padrão e sem tracing; configure alertas e retenção no próprio projeto Sentry.

> **`REDIS_URL` passou a ser obrigatória (`QA-02`).** O Redis já era exigido aqui como
> broker do Celery, mas o Django não o usava como cache: sem a variável ele caía para
> `LocMemCache`, que é **por processo**. Com os 3 workers do gunicorn, o rate limit de
> login (5 tentativas / 15 min) virava até ~15 antes de um worker bloquear sozinho, e
> zerava a cada `systemctl restart` — que o próprio deploy executa. `/metrics/` sofria
> do mesmo: contava só o worker que atendeu à requisição.
>
> `config/settings/prod.py` agora recusa subir sem ela, em vez de degradar em silêncio.
> **Num servidor já no ar, acrescente a linha ao `.env` antes do próximo deploy** — o
> `migrate` do `deploy.yml` roda com settings de produção e vai falhar sem ela.

### 4.4 Crie os diretórios de mídia

```bash
mkdir -p /var/www/gerenciador-viagens/media/tmp_documentos
mkdir -p /var/www/gerenciador-viagens/staticfiles
```

### 4.5 Execute as migrações e collectstatic

```bash
# Ative o venv se não estiver ativo
source /var/www/gerenciador-viagens/venv/bin/activate

cd /var/www/gerenciador-viagens/app

# Variável de settings para todos os comandos
export DJANGO_SETTINGS_MODULE=config.settings.prod

# Rode as migrations
python manage.py migrate

# Colete os arquivos estáticos
python manage.py collectstatic --noinput

# Carregue os dados geográficos (estados e cidades do IBGE)
# IMPORTANTE: sem isso o campo "Cidade" nos formulários não funciona
python manage.py importar_base_geografica

# (Opcional) Dados de demonstração para apresentação
python manage.py seed_cadastros_demo
```

### 4.6 Crie o superusuário administrador

```bash
python manage.py createsuperuser
```

---

## 5. Gunicorn (servidor WSGI)

### 5.1 Teste o Gunicorn manualmente

```bash
source /var/www/gerenciador-viagens/venv/bin/activate
cd /var/www/gerenciador-viagens/app

gunicorn config.wsgi:application \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --env DJANGO_SETTINGS_MODULE=config.settings.prod
```

Se abrir sem erros, Ctrl+C e passe para o próximo passo.

### 5.2 Crie o serviço systemd

```bash
sudo nano /etc/systemd/system/gerenciador-viagens.service
```

Cole o conteúdo abaixo (ajuste se necessário):

```ini
[Unit]
Description=Gerenciador de Viagens — Gunicorn
After=network.target postgresql.service

[Service]
User=viagens
Group=viagens
WorkingDirectory=/var/www/gerenciador-viagens/app
EnvironmentFile=/var/www/gerenciador-viagens/app/.env
Environment="DJANGO_SETTINGS_MODULE=config.settings.prod"
ExecStart=/var/www/gerenciador-viagens/venv/bin/gunicorn \
          config.wsgi:application \
          --workers 3 \
          --bind 127.0.0.1:8000 \
          --timeout 120 \
          --access-logfile /var/www/gerenciador-viagens/logs/access.log \
          --error-logfile /var/www/gerenciador-viagens/logs/error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Crie o diretório de logs
mkdir -p /var/www/gerenciador-viagens/logs
chown viagens:viagens /var/www/gerenciador-viagens/logs

# Ative e inicie o serviço
sudo systemctl daemon-reload
sudo systemctl enable gerenciador-viagens
sudo systemctl start gerenciador-viagens
sudo systemctl status gerenciador-viagens
```

### 5.3 Celery (documentos, Drive e manutenção dos jobs)

Obrigatório em produção. O request cria um job durável e retorna polling; o
worker gera o arquivo e o beat encerra jobs órfãos e remove resultados após 24 h.

```bash
# Garanta que o Redis (instalado no passo 2.3) está ativo
sudo systemctl enable --now redis-server
```

Crie o serviço systemd do worker:

```bash
sudo nano /etc/systemd/system/gerenciador-viagens-celery.service
```

```ini
[Unit]
Description=Gerenciador de Viagens — Celery worker
After=network.target redis-server.service

[Service]
User=viagens
Group=viagens
WorkingDirectory=/var/www/gerenciador-viagens/app
EnvironmentFile=/var/www/gerenciador-viagens/app/.env
Environment="DJANGO_SETTINGS_MODULE=config.settings.prod"
ExecStart=/var/www/gerenciador-viagens/venv/bin/celery \
          -A config worker \
          --loglevel=info \
          --logfile=/var/www/gerenciador-viagens/logs/celery.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable gerenciador-viagens-celery
sudo systemctl start gerenciador-viagens-celery
sudo systemctl status gerenciador-viagens-celery
```

Crie também `/etc/systemd/system/gerenciador-viagens-celery-beat.service`:

```ini
[Unit]
Description=Gerenciador de Viagens — Celery beat
After=network.target redis-server.service

[Service]
User=viagens
Group=viagens
WorkingDirectory=/var/www/gerenciador-viagens/app
EnvironmentFile=/var/www/gerenciador-viagens/app/.env
Environment="DJANGO_SETTINGS_MODULE=config.settings.prod"
ExecStart=/var/www/gerenciador-viagens/venv/bin/celery \
          -A config beat \
          --loglevel=info \
          --logfile=/var/www/gerenciador-viagens/logs/celery-beat.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gerenciador-viagens-celery-beat
sudo systemctl status gerenciador-viagens-celery-beat
```

### 5.4 UNOSERVER (PDF em menos de 1 segundo)

O LibreOffice iniciado para cada documento demora vários segundos. Para o SLA de
PDF, mantenha uma instância residente e acessível apenas pelo host local:

```bash
sudo apt update
sudo apt install -y libreoffice-writer python3-uno python3-venv
python3 -m venv --system-site-packages /var/www/gerenciador-viagens/unoserver-venv
/var/www/gerenciador-viagens/unoserver-venv/bin/pip install "unoserver>=3.4,<4.0"
mkdir -p /var/www/gerenciador-viagens/unoserver-home
sudo chown -R viagens:viagens \
  /var/www/gerenciador-viagens/unoserver-venv \
  /var/www/gerenciador-viagens/unoserver-home
```

Crie `/etc/systemd/system/gerenciador-viagens-unoserver.service`:

```ini
[Unit]
Description=Gerenciador de Viagens — conversor PDF persistente
After=network.target

[Service]
User=viagens
Group=viagens
Environment="HOME=/var/www/gerenciador-viagens/unoserver-home"
ExecStart=/var/www/gerenciador-viagens/unoserver-venv/bin/unoserver \
          --interface 127.0.0.1 \
          --port 2003 \
          --conversion-timeout 30 \
          --stop-after 1000 \
          --quiet
ExecStartPost=/var/www/gerenciador-viagens/unoserver-venv/bin/unoconvert \
              --host 127.0.0.1 \
              --port 2003 \
              --host-location local \
              --dont-update-index \
              /var/www/gerenciador-viagens/app/deploy/unoserver/warmup.rtf \
              /tmp/gerenciador-viagens-unoserver-warmup.pdf
Restart=always
RestartSec=2
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

No `.env` da aplicação:

```bash
DOCUMENTOS_DEFAULT_PDF_ENGINE=unoserver
DOCUMENTOS_UNOSERVER_URL=http://127.0.0.1:2003
DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS=5
DOCUMENTOS_ENGINE_PROBE_CACHE_SECONDS=60
DOCUMENTOS_PDF_AUTO_FALLBACK=true
```

Ative e valide antes de reiniciar a aplicação:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gerenciador-viagens-unoserver
/var/www/gerenciador-viagens/unoserver-venv/bin/unoping \
  --host 127.0.0.1 \
  --port 2003
sudo systemctl restart gerenciador-viagens gerenciador-viagens-celery gerenciador-viagens-celery-beat
cd /var/www/gerenciador-viagens/app
source /var/www/gerenciador-viagens/venv/bin/activate
python manage.py documentos_unoserver_check \
  --benchmark --representative-resources --max-ms 1000 --iterations 3
```

Gere uma chave de criptografia para os tokens OAuth e salve-a no `.env`
(nunca no banco ou no repositório):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# FIELD_ENCRYPTION_KEYS=cole_a_chave_aqui
```

Para rotação sem indisponibilidade, informe `chave_nova,chave_antiga`, execute
as migrações e, depois de recriptografar os registros, remova a chave antiga.

Os uploads privados exigem antivírus em produção — a política é *fail-closed*,
então sem `clamd` respondendo nenhum anexo entra. Prefira o workflow
`Antivirus da VPS (ClamAV)` (modo `checar` antes, `instalar` depois) a fazer
isto na mão; ele instala, baixa as assinaturas e valida o resultado no mesmo
formato que o Django usa. O equivalente manual:

```bash
sudo apt-get install -y clamav-daemon clamav-freshclam
sudo systemctl stop clamav-freshclam && sudo freshclam
sudo systemctl enable --now clamav-freshclam clamav-daemon
clamdscan --version
```

O `clamd` roda como usuário `clamav` e recebe apenas o caminho do arquivo, mas
o temporário criado pelo Django nasce com modo 0600 sob o usuário do gunicorn.
Sem `--fdpass` o daemon responde `Access denied` e sai com 2, e todo anexo é
recusado — por isso o default de `CLAMAV_SCAN_COMMAND` é `clamdscan --fdpass`.
Para conferir do jeito que o app faz:

```bash
T=$(mktemp /tmp/av-XXXXXX.pdf) && chmod 600 "$T" && printf '%%PDF-1.4
' > "$T"
clamdscan --fdpass --no-summary "$T"; echo "exit=$?"; rm -f "$T"
```

Não exponha a porta 2003 no firewall ou no Nginx; o protocolo não possui
autenticação. O `ExecStartPost` é intencional: o serviço só fica pronto após
uma conversão de aquecimento, evitando que o primeiro usuário pague o custo de
carregar os filtros do LibreOffice.

---

## 6. Nginx (proxy reverso)

```bash
sudo nano /etc/nginx/sites-available/gerenciador-viagens
```

Cole:

```nginx
server {
    listen 80;
    server_name SEU_IP_VPS seudominio.com.br www.seudominio.com.br;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/gerenciador-viagens/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Nunca exponha /media/ diretamente. O Django autoriza o usuário/área e,
    # depois disso, delega a transferência ao Nginx por X-Accel-Redirect.
    location /_protected_media/ {
        internal;
        alias /var/www/gerenciador-viagens/media/;
    }

    location /media/ {
        return 404;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
# Ative o site
sudo ln -s /etc/nginx/sites-available/gerenciador-viagens /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 7. HTTPS com Let's Encrypt (gratuito)

Só funciona se você tiver um **domínio apontado para o IP do VPS**.

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br
```

O Certbot configura o HTTPS automaticamente e renova o certificado. Após isso, adicione ao `.env`:
```
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

> Se não tiver domínio, o sistema funciona normalmente via `http://IP_DO_VPS`. Os cookies secure já estão configurados no `settings/prod.py` — basta garantir HTTPS quando possível.

---

## 8. Atualizações Futuras

Para atualizar o código após mudanças no repositório:

```bash
cd /var/www/gerenciador-viagens/app
git pull origin main

source /var/www/gerenciador-viagens/venv/bin/activate
pip install -r requirements/prod.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

sudo systemctl restart gerenciador-viagens
sudo systemctl restart gerenciador-viagens-celery gerenciador-viagens-celery-beat
```

Ou use o script pronto:

```bash
sudo bash /var/www/gerenciador-viagens/app/scripts/deploy_update.sh
```

---

## 9. Verificação Final

Após tudo configurado, verifique:

```bash
# Serviço rodando
sudo systemctl status gerenciador-viagens

# Nginx respondendo
curl -I http://SEU_IP_VPS

# Logs em tempo real
sudo journalctl -u gerenciador-viagens -f
```

Acesse `http://SEU_IP_VPS/admin` e faça login com o superusuário criado.

---

## 10. Checklist de Go-Live

- [ ] VPS KVM 2 criado na Hostinger (Ubuntu 22.04/24.04)
- [ ] Dependências de sistema instaladas (incluindo libs WeasyPrint)
- [ ] PostgreSQL configurado com usuário e banco de produção
- [ ] Repositório clonado em `/var/www/gerenciador-viagens/app`
- [ ] Ambiente virtual criado e dependências instaladas (`requirements/prod.txt`)
- [ ] `.env` configurado com `SECRET_KEY`, `ALLOWED_HOSTS`, `DB_*` e `MEDIA_ROOT`
- [ ] `python manage.py migrate` executado sem erros
- [ ] `python manage.py collectstatic` executado
- [ ] `python manage.py importar_base_geografica` executado (dados de cidades)
- [ ] Superusuário criado (`createsuperuser`)
- [ ] Serviço systemd ativo e respondendo
- [ ] Redis + worker + beat Celery configurados (documentos e Drive — seção 5.3)
- [ ] Nginx configurado e recarregado
- [ ] (Opcional) HTTPS configurado com Certbot
- [ ] Login funcional no navegador
- [ ] Geração de PDF testada (crie um roteiro de teste)

---

## Módulos disponíveis na versão atual

| Módulo | Status em produção |
|---|---|
| Login / autenticação | Funcional |
| Cadastros (Servidores, Viaturas, Cargos, etc.) | Funcional |
| Roteiros com cálculo de distância | Funcional |
| Geração de PDF via WeasyPrint | Funcional |
| Ofícios (wizard parcial) | Em desenvolvimento |
| Planos de Trabalho | Em desenvolvimento |
| Eventos, Termos, Ordens, Prestações | Placeholder (tela existe, sem lógica) |

> Os módulos em "Placeholder" aparecem no menu mas não têm funcionalidade — isso não quebra o sistema, apenas exibe telas vazias.
