"""
Limpa o banco (flush total) e recadastra a estrutura institucional da PCPR 2026:
estados, cidades (com lat/long), unidades (somente as do docx), cargos, combustíveis
e servidores (CSV) lotados nas unidades do docx.

Uso:
    python manage.py importar_estrutura_pcpr --csv "C:/caminho/planilha.csv"
    python manage.py importar_estrutura_pcpr --no-flush      # nao zera (diagnostico)
    python manage.py importar_estrutura_pcpr --superuser admin --senha SENHA

A estrutura de UNIDADES e CIDADES vem embutida (gerada do docx oficial).
Os SERVIDORES vem do CSV informado.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.db import transaction

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Combustivel
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade


CSV_PADRAO = r"C:\Users\tiago\Downloads\PLANILHA DE VIAGENS COMPLETA 2.0 - Dados p_ Viagens.csv"

ESTADO_PR = ("PARANÁ", "PR", 41)

UNIDADES = [
    ('Departamento da Polícia Civil', 'PCPR'),
    ('Delegacia-Geral da Polícia Civil', 'DGPC'),
    ('Delegacia-Geral Adjunta', 'DGA'),
    ('Conselho da Polícia Civil', 'CPC'),
    ('Assessoria de Comunicação', 'ASCOM'),
    ('Assessoria de Planejamento Estratégico', 'PLANEJAMENTO'),
    ('Assessoria de Relações Institucionais', 'ARI'),
    ('Assessoria Jurídica', 'ASSEJUR'),
    ('Assessoria de Informática e Tecnologia', 'AIT'),
    ('Corregedoria-Geral da Polícia Civil', 'CGPC'),
    ('Escola Superior de Polícia Civil', 'ESPC'),
    ('Agência de Inteligência da Polícia Civil', 'AIPC'),
    ('Grupo Auxiliar Financeiro', 'GAF'),
    ('Departamento de Recursos Humanos', 'DRH'),
    ('Departamento de Logística e Patrimônio', 'DLP'),
    ('Delegacia de Homicídios', 'DH'),
    ('Delegacia de Proteção à Pessoa', 'DPP'),
    ('Subdivisão de Repressão Penal', 'SRP'),
    ('Subdivisão de Inteligência e Informações', 'SII'),
    ('Delegacia de Combate à Corrupção', 'DECCOR'),
    ('Delegacia de Furtos e Roubos', 'DFR'),
    ('Delegacia de Furtos e Roubos de Veículos', 'DFRV'),
    ('Delegacia de Furtos e Roubos de Cargas', 'DFRC'),
    ('Delegacia de Vigilância e Capturas', 'DVC'),
    ('Delegacia da Mulher', 'DM'),
    ('Núcleo de Proteção à Criança e ao Adolescente', 'NUCRIA'),
    ('Delegacia do Adolescente', 'DA'),
    ('Delegacia de Crimes contra a Economia', 'DELCON'),
    ('Delegacia de Delitos de Trânsito', 'DEDETRAN'),
    ('Delegacia de Proteção ao Meio Ambiente', 'DPMA'),
    ('Delegacia de Estelionato', 'DE'),
    ('Núcleo de Combate aos Cibercrimes', 'NUCIBER'),
    ('Delegacia Móvel de Atendimento a Futebol e Eventos', 'DEMAFE'),
    ('Centro de Operações Policiais Especiais', 'COPE'),
    ('Tático Integrado de Grupos de Repressão Especial', 'TIGRE'),
    ('Grupamento de Operações Aéreas', 'GOA'),
    ('1º Distrito Policial', '1DP'),
    ('2º Distrito Policial', '2DP'),
    ('3º Distrito Policial', '3DP'),
    ('4º Distrito Policial', '4DP'),
    ('5º Distrito Policial', '5DP'),
    ('6º Distrito Policial', '6DP'),
    ('7º Distrito Policial', '7DP'),
    ('8º Distrito Policial', '8DP'),
    ('9º Distrito Policial', '9DP'),
    ('10º Distrito Policial', '10DP'),
    ('11º Distrito Policial', '11DP'),
    ('12º Distrito Policial', '12DP'),
    ('13º Distrito Policial', '13DP'),
    ('Delegacia de São José dos Pinhais', 'DP SJP'),
    ('Delegacia de Colombo', 'DP COL'),
    ('Delegacia de Pinhais', 'DP PIN'),
    ('Delegacia de Araucária', 'DP ARA'),
    ('Delegacia de Piraquara', 'DP PIR'),
    ('Delegacia de Fazenda Rio Grande', 'DP FRG'),
    ('Delegacia de Almirante Tamandaré', 'DP ALT'),
    ('1ª Subdivisão Policial', '1SDP'),
    ('2ª Subdivisão Policial', '2SDP'),
    ('3ª Subdivisão Policial', '3SDP'),
    ('4ª Subdivisão Policial', '4SDP'),
    ('5ª Subdivisão Policial', '5SDP'),
    ('6ª Subdivisão Policial', '6SDP'),
    ('7ª Subdivisão Policial', '7SDP'),
    ('8ª Subdivisão Policial', '8SDP'),
    ('9ª Subdivisão Policial', '9SDP'),
    ('10ª Subdivisão Policial', '10SDP'),
    ('11ª Subdivisão Policial', '11SDP'),
    ('12ª Subdivisão Policial', '12SDP'),
    ('13ª Subdivisão Policial', '13SDP'),
    ('14ª Subdivisão Policial', '14SDP'),
    ('15ª Subdivisão Policial', '15SDP'),
    ('16ª Subdivisão Policial', '16SDP'),
    ('17ª Subdivisão Policial', '17SDP'),
    ('18ª Subdivisão Policial', '18SDP'),
    ('19ª Subdivisão Policial', '19SDP'),
    ('21ª Subdivisão Policial', '21SDP'),
    ('22ª Subdivisão Policial', '22SDP'),
    ('23ª Subdivisão Policial', '23SDP'),
    ('25ª Delegacia Regional de Polícia', '25DRP'),
    ('Delegacia de Medianeira', 'DP MED'),
    ('Delegacia de Guaíra', 'DP GUA'),
    ('Delegacia de MCR', 'DP MCR'),
    ('Delegacia de Palotina', 'DP PAL'),
    ('Delegacia de Assis', 'DP ASSIS'),
    ('Delegacia de Ivaiporã', 'DP IVA'),
    ('Delegacia de Rolândia', 'DP ROL'),
    ('Delegacia de Cambé', 'DP CAM'),
    ('Delegacia de Ibiporã', 'DP IBI'),
    ('Delegacia de Castro', 'DP CAS'),
    ('Delegacia de Irati', 'DP IRA'),
    ('Delegacia de Prudentópolis', 'DP PRU'),
    ('Delegacia de Pinhão', 'DP PIN'),
    ('Delegacia da Lapa', 'DP LAP'),
    ('Delegacia de Rio Negro', 'DP RN'),
    ('Delegacia de Antonina', 'DP ANT'),
    ('Delegacia de Guaratuba', 'DP GUA'),
    ('Delegacia de Matinhos', 'DP MAT'),
]

CIDADES = [
    ('Almirante Tamandaré', '-25.3253000', '-49.3081000'),
    ('Antonina', '-25.4289000', '-48.7119000'),
    ('Apucarana', '-23.5509000', '-51.4609000'),
    ('Arapongas', '-23.4194000', '-51.4244000'),
    ('Araucária', '-25.5936000', '-49.4106000'),
    ('Assis Chateaubriand', '-24.4111000', '-53.5203000'),
    ('Cambé', '-23.2766000', '-51.2783000'),
    ('Campo Mourão', '-24.0463000', '-52.3781000'),
    ('Cascavel', '-24.9555000', '-53.4552000'),
    ('Castro', '-24.7911000', '-50.0119000'),
    ('Cianorte', '-23.6633000', '-52.6050000'),
    ('Colombo', '-25.2922000', '-49.2242000'),
    ('Cornélio Procópio', '-23.1811000', '-50.6464000'),
    ('Curitiba', '-25.4284000', '-49.2733000'),
    ('Fazenda Rio Grande', '-25.6622000', '-49.3075000'),
    ('Foz do Iguaçu', '-25.5478000', '-54.5882000'),
    ('Francisco Beltrão', '-26.0814000', '-53.0550000'),
    ('Goioerê', '-24.1850000', '-53.0272000'),
    ('Guarapuava', '-25.3935000', '-51.4562000'),
    ('Guaratuba', '-25.8825000', '-48.5747000'),
    ('Guaíra', '-24.0858000', '-54.2569000'),
    ('Ibiporã', '-23.2697000', '-51.0519000'),
    ('Irati', '-25.4675000', '-50.6511000'),
    ('Ivaiporã', '-24.2483000', '-51.6753000'),
    ('Jacarezinho', '-23.1606000', '-49.9697000'),
    ('Lapa', '-25.7697000', '-49.7158000'),
    ('Laranjeiras do Sul', '-25.4075000', '-52.4156000'),
    ('Londrina', '-23.3045000', '-51.1696000'),
    ('Marechal Cândido Rondon', '-24.5557000', '-54.0578000'),
    ('Maringá', '-23.4205000', '-51.9333000'),
    ('Matinhos', '-25.8175000', '-48.5428000'),
    ('Medianeira', '-25.2950000', '-54.0939000'),
    ('Palotina', '-24.2842000', '-53.8403000'),
    ('Paranaguá', '-25.5161000', '-48.5225000'),
    ('Paranavaí', '-23.0731000', '-52.4650000'),
    ('Pato Branco', '-26.2289000', '-52.6708000'),
    ('Pinhais', '-25.4447000', '-49.1925000'),
    ('Pinhão', '-25.6953000', '-51.6597000'),
    ('Piraquara', '-25.4419000', '-49.0628000'),
    ('Ponta Grossa', '-25.0916000', '-50.1668000'),
    ('Prudentópolis', '-25.2136000', '-50.9778000'),
    ('Rio Negro', '-26.1058000', '-49.7967000'),
    ('Rolândia', '-23.3094000', '-51.3689000'),
    ('São José dos Pinhais', '-25.5306000', '-49.2058000'),
    ('São Mateus do Sul', '-25.8744000', '-50.3836000'),
    ('Telêmaco Borba', '-24.3236000', '-50.6164000'),
    ('Toledo', '-24.7136000', '-53.7433000'),
    ('Umuarama', '-23.7661000', '-53.3206000'),
    ('União da Vitória', '-26.2272000', '-51.0869000'),
]


CARGO_PADRAO = "AGENTE DE POLÍCIA JUDICIÁRIA"

COMBUSTIVEIS = [
    ("GASOLINA", False),
    ("ETANOL", False),
    ("FLEX", True),
    ("DIESEL", False),
    ("DIESEL S10", False),
]

# Mapa de lotacao (CSV) -> sigla da unidade no docx.
# Distritos da capital sao resolvidos por regex (N + DISTRITO/DP/DPC -> NDP).
LOTACAO_MAP = {
    "COPE": "COPE",
    "ASCOM": "ASCOM",
    "ESTELIONATO": "DE",
    "SDP TOLEDO": "19SDP",
    "GAF": "GAF",
    "DM": "DM",
    "DPMA": "DPMA",
    "DFRV": "DFRV",
    "GAB DGA": "DGA",
    "DELEGACIA DO ADOLESCENTE": "DA",
    "ALM TAMANDARE DPMETRO": "DP ALT",
    "DP PIQUARA": "DP PIR",
}

# Lotacoes que NAO existem no docx (ficam sem unidade, conforme decidido).
RE_DISTRITO = re.compile(r"^(\d{1,2}) (?:DISTRITO|DP|DPC)(?: CAPITAL)?$")


def limpar_chave(s: str) -> str:
    s = (s or "").replace("º", "").replace("°", "").replace("ª", "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def so_digitos(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def limpar_rg(rg_raw: str, cpf_digitos: str):
    """Retorna (rg_limpo, motivo_invalido|None)."""
    bruto = (rg_raw or "").strip()
    if not bruto:
        return "", None
    limpo = "".join(c for c in bruto.upper() if c.isalnum())
    digitos = so_digitos(limpo)
    # RG igual ao CPF -> erro de digitacao
    if digitos and digitos == cpf_digitos:
        return "", "RG igual ao CPF"
    # texto sem cara de RG (ex.: MESMA NUMERACAO)
    if not re.fullmatch(r"\d{5,12}X?", limpo):
        return "", f"RG invalido ({bruto!r})"
    return limpo, None


class Command(BaseCommand):
    help = "Zera o banco e recadastra estrutura PCPR 2026 (cidades, unidades, cargos, combustiveis, servidores)."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=CSV_PADRAO, help="Caminho do CSV de servidores.")
        parser.add_argument("--no-flush", action="store_true", help="Nao zera o banco antes.")
        parser.add_argument("--superuser", default="", help="Cria superusuario com este username apos o flush.")
        parser.add_argument("--senha", default="Mudar@123", help="Senha do superusuario criado.")
        parser.add_argument("--email", default="tiago2904santos@gmail.com", help="Email do superusuario.")

    def handle(self, *args, **opts):
        csv_path = Path(opts["csv"]).expanduser()
        if not csv_path.is_file():
            self.stderr.write(self.style.ERROR(f"CSV nao encontrado: {csv_path}"))
            return

        if not opts["no_flush"]:
            self.stdout.write(self.style.WARNING("Zerando TODAS as tabelas (TRUNCATE CASCADE)..."))
            self._flush_cascade()

        with transaction.atomic():
            estado = self._criar_estado()
            n_cid = self._criar_cidades(estado)
            unidades_por_sigla = self._criar_unidades()
            self._criar_combustiveis()
            n_serv, relatorio = self._criar_servidores(csv_path, unidades_por_sigla)

        self.stdout.write(self.style.SUCCESS("\n=== CONCLUIDO ==="))
        self.stdout.write(f"Estado: {estado}")
        self.stdout.write(f"Cidades: {n_cid}")
        self.stdout.write(f"Unidades: {len(UNIDADES)}")
        self.stdout.write(f"Cargos: {Cargo.objects.count()}")
        self.stdout.write(f"Combustiveis: {Combustivel.objects.count()}")
        self.stdout.write(f"Servidores criados: {n_serv}")
        self._imprimir_relatorio(relatorio)

        if opts["superuser"]:
            User = get_user_model()
            User.objects.filter(username=opts["superuser"]).delete()
            User.objects.create_superuser(opts["superuser"], opts["email"], opts["senha"])
            self.stdout.write(self.style.SUCCESS(
                f"\nSuperusuario '{opts['superuser']}' criado (senha: {opts['senha']}). TROQUE a senha!"
            ))

    def _flush_cascade(self) -> None:
        """Zera todas as tabelas de dados via TRUNCATE ... CASCADE.

        Preserva apenas a infraestrutura do Django (migrations, content types,
        permissions); auth_user/sessions/admin_log e todo o dominio sao zerados.
        """
        preservar = {"django_migrations", "django_content_type", "auth_permission"}
        with connection.cursor() as cursor:
            tabelas = connection.introspection.table_names(cursor)
            alvo = [t for t in tabelas if t not in preservar]
            if not alvo:
                return
            ids = ", ".join(connection.ops.quote_name(t) for t in alvo)
            cursor.execute(f"TRUNCATE {ids} RESTART IDENTITY CASCADE")

    def _criar_estado(self) -> Estado:
        nome, sigla, ibge = ESTADO_PR
        return Estado.objects.create(nome=nome, sigla=sigla, codigo_ibge=ibge)

    def _criar_cidades(self, estado: Estado) -> int:
        for nome, lat, lon in CIDADES:
            Cidade.objects.create(
                estado=estado,
                nome=nome,
                uf="PR",
                capital=(nome.upper() == "CURITIBA"),
                latitude=Decimal(lat),
                longitude=Decimal(lon),
            )
        return len(CIDADES)

    def _criar_unidades(self) -> dict:
        por_sigla: dict[str, Unidade] = {}
        for nome, sigla in UNIDADES:
            u = Unidade.objects.create(nome=nome, sigla=sigla)
            # chave normalizada da sigla (uppercase) para lookup do mapeamento
            por_sigla.setdefault(u.sigla, u)
        return por_sigla

    def _criar_combustiveis(self) -> None:
        for nome, padrao in COMBUSTIVEIS:
            Combustivel.objects.create(nome=nome, is_padrao=padrao)

    def _resolver_unidade(self, lotacao: str, unidades_por_sigla: dict):
        chave = limpar_chave(lotacao)
        m = RE_DISTRITO.match(chave)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 13:
                return unidades_por_sigla.get(f"{n}DP"), None
        if chave in LOTACAO_MAP:
            sigla = LOTACAO_MAP[chave]
            return unidades_por_sigla.get(sigla), None
        return None, chave  # nao mapeada

    def _criar_servidores(self, csv_path: Path, unidades_por_sigla: dict):
        cargo_cache: dict[str, Cargo] = {}

        def get_cargo(nome_cargo: str):
            chave = " ".join((nome_cargo or "").strip().split()).upper()
            if not chave:
                return None
            if chave not in cargo_cache:
                cargo, _ = Cargo.objects.get_or_create(
                    nome=chave, defaults={"is_padrao": chave == CARGO_PADRAO}
                )
                cargo_cache[chave] = cargo
            return cargo_cache[chave]

        usados_cpf, usados_rg, usados_tel, usados_nome = set(), set(), set(), set()
        criados = 0
        rel = {
            "sem_unidade": {},   # chave_lotacao -> [nomes]
            "duplicados": [],    # (nome, motivo)
            "cpf_suspeito": [],  # (nome, cpf)
            "rg_corrigido": [],  # (nome, motivo)
            "tel_em_branco": [], # (nome, motivo)
        }

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # cabecalho
            for row in reader:
                if not row or not (row[0].strip() or (len(row) > 1 and row[1].strip())):
                    continue
                lotacao = row[0].strip()
                nome = (row[1] if len(row) > 1 else "").strip()
                rg_raw = (row[2] if len(row) > 2 else "").strip()
                cpf_raw = (row[3] if len(row) > 3 else "").strip()
                cargo_raw = (row[4] if len(row) > 4 else "").strip()
                tel_raw = (row[5] if len(row) > 5 else "").strip()
                if not nome:
                    continue

                nome_norm = " ".join(nome.split()).upper()
                cpf = so_digitos(cpf_raw)

                # ---- deduplicacao (mesma pessoa) ----
                if cpf and cpf in usados_cpf:
                    rel["duplicados"].append((nome_norm, f"CPF repetido {cpf}"))
                    continue
                if (not cpf or len(cpf) != 11) and nome_norm in usados_nome:
                    rel["duplicados"].append((nome_norm, "nome repetido"))
                    continue

                # ---- CPF ----
                cpf_final = cpf
                if cpf and len(cpf) != 11:
                    rel["cpf_suspeito"].append((nome_norm, cpf_raw))
                    cpf_final = cpf[:11]

                # ---- RG ----
                rg_final, motivo_rg = limpar_rg(rg_raw, cpf)
                if motivo_rg:
                    rel["rg_corrigido"].append((nome_norm, motivo_rg))
                if rg_final and rg_final in usados_rg:
                    rel["rg_corrigido"].append((nome_norm, f"RG {rg_final} ja usado -> em branco"))
                    rg_final = ""

                # ---- Telefone ----
                tel = so_digitos(tel_raw)
                if len(tel) > 11:
                    tel = tel[-11:]
                if tel and tel in usados_tel:
                    rel["tel_em_branco"].append((nome_norm, f"telefone {tel} ja usado"))
                    tel = ""

                # ---- Unidade ----
                unidade, chave_nao_map = self._resolver_unidade(lotacao, unidades_por_sigla)
                if unidade is None:
                    rel["sem_unidade"].setdefault(chave_nao_map or limpar_chave(lotacao), []).append(nome_norm)

                # ---- cria ----
                Servidor.objects.create(
                    nome=nome_norm,
                    cargo=get_cargo(cargo_raw),
                    cpf=cpf_final,
                    rg=rg_final,
                    sem_rg=False,
                    telefone=tel,
                    unidade=unidade,
                )
                criados += 1
                if cpf_final:
                    usados_cpf.add(cpf)
                if rg_final:
                    usados_rg.add(rg_final)
                if tel:
                    usados_tel.add(tel)
                usados_nome.add(nome_norm)

        return criados, rel

    def _imprimir_relatorio(self, rel: dict) -> None:
        st = self.stdout
        st.write(self.style.MIGRATE_HEADING("\n--- RELATORIO ---"))

        sem_unidade = rel["sem_unidade"]
        total_sem = sum(len(v) for v in sem_unidade.values())
        st.write(self.style.WARNING(f"\nServidores SEM unidade (lotacao fora do docx): {total_sem}"))
        for chave in sorted(sem_unidade, key=lambda k: -len(sem_unidade[k])):
            nomes = sem_unidade[chave]
            st.write(f"  [{len(nomes):>2}] {chave}")
            for n in nomes:
                st.write(f"        - {n}")

        if rel["duplicados"]:
            st.write(self.style.WARNING(f"\nLinhas duplicadas ignoradas: {len(rel['duplicados'])}"))
            for nome, motivo in rel["duplicados"]:
                st.write(f"  - {nome} ({motivo})")

        if rel["cpf_suspeito"]:
            st.write(self.style.WARNING(f"\nCPF suspeito (diferente de 11 digitos, gravado mesmo assim): {len(rel['cpf_suspeito'])}"))
            for nome, cpf in rel["cpf_suspeito"]:
                st.write(f"  - {nome}: {cpf}")

        if rel["rg_corrigido"]:
            st.write(self.style.WARNING(f"\nRG ajustado/zerado: {len(rel['rg_corrigido'])}"))
            for nome, motivo in rel["rg_corrigido"]:
                st.write(f"  - {nome}: {motivo}")

        if rel["tel_em_branco"]:
            st.write(self.style.WARNING(f"\nTelefone zerado (duplicado): {len(rel['tel_em_branco'])}"))
            for nome, motivo in rel["tel_em_branco"]:
                st.write(f"  - {nome}: {motivo}")
