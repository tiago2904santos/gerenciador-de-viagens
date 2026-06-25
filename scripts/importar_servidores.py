"""
Importa unidades e servidores a partir dos CSVs.
Uso:
    python manage.py shell -c "exec(open(r'scripts/importar_servidores.py', encoding='utf-8').read())"
"""

import csv
import re

from cadastros.models import Cargo, Servidor, Unidade

UNIDADES_CSV = r"C:\Users\tiago\OneDrive\Documentos\Gerenciador de Viagens\lista de unidades.csv"
SERVIDORES_CSV = r"C:\Users\tiago\Downloads\PLANILHA DE VIAGENS COMPLETA 2.0 - Dados p_ Viagens (1).csv"


def normaliza(s):
    return re.sub(r"\s+", " ", (s or "").strip().upper())


def so_digitos(s):
    return re.sub(r"\D", "", s or "")


# ──────────────────────────────────────────────
# 1. Importar unidades
# ──────────────────────────────────────────────
print("=== Importando unidades ===")
unidades_por_sigla = {}

with open(UNIDADES_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        row = {k.strip(): v for k, v in row.items()}
        nome = normaliza(row.get("unidade") or row.get("Unidade", ""))
        sigla = normaliza(row.get("Sigla_da_unidade") or row.get("sigla_da_unidade", ""))
        if not nome or not sigla:
            continue
        obj = Unidade.objects.filter(sigla=sigla).first()
        if not obj:
            obj = Unidade.objects.create(sigla=sigla, nome=nome)
        unidades_por_sigla[sigla] = obj

print(f"  {len(unidades_por_sigla)} unidades do CSV prontas.")

# Recarrega TUDO do banco (inclui unidades cadastradas manualmente)
unidades_por_sigla = {u.sigla: u for u in Unidade.objects.all()}
unidades_por_nome = {u.nome: u for u in Unidade.objects.all()}
print(f"  {len(unidades_por_sigla)} unidades totais no banco.")

# ──────────────────────────────────────────────
# 2. Tentar casar LOTAÇÃO → Unidade
# ──────────────────────────────────────────────
# Mapeamento manual para abreviações da planilha que diferem das siglas
MAPA_LOTACAO = {
    "SECRET. EXEC.": "SE",
    "7º DISTRITO": "07DP",
    "7° DISTRITO": "07DP",
    "6° DP": "06DP",
    "6º DP": "06DP",
    "9° DISTRITO": "09DP",
    "9º DISTRITO": "09DP",
    "10º DISTRITO": "10DP",
    "10° DP": "10DP",
    "13° DP": "13DP",
    "13º DISTRITO": "13DP",
    "2º DISTRITO": "02DP",
    "3º DISTRITO": "03DP",
    "1° DP": "01DP",
    "4° DPC": "04DP",
    "5° DP CAPITAL": "05DP",
    "5° DP": "05DP",
    "ESTELIONATO": "DE",
    "DECC": "DECCOR-1",
    "DCCP": "DECCOR-1",
    "GAP": "GAP",
    "GAB. DGA": "DGA",
    "APOIO": None,
    "APO": None,
    "IIPR": "IIPR",
    "IIPR - PONTA GROSSA": "IIPR",
    "SDP - TOLEDO": "20SDP",
    "SRI - CASCAVEL": "15SDP",
    "SRI FOZ DO IGUAÇU": "06SDP",
    "SRI JACAREZINHO": "12SDP",
    "SRI-JACAREZINHO": "12SDP",
    "SRI PONTA GROSSA": "13SDP",
    "SRI - TOLEDO": "20SDP",
    "DELEGACIA DO ADOLESCENTE": "DA",
    "DEL. MULHER ARAUCÁRIA": "DM ARAUCÁRIA",
    "DP ALTO MARACANA": "DP ALTO MARACANA",
    "DP - PIQUARA": "DP - PIQUARA",
    "ALM. TAMANDARE (DPMETRO)": "DP-ALT",
    "DELEGACIA ELETRÔNICA": None,
    "SICRIDE": None,
    "DELCOI": "DELCON",
    "DPCAP": "DPCAP",
    "DIC": "DIC",
    "DFRV": "DFRV",
}


def resolver_lotacao(lotacao):
    lotacao = normaliza(lotacao)
    # mapa manual
    if lotacao in MAPA_LOTACAO:
        sigla = MAPA_LOTACAO[lotacao]
        return unidades_por_sigla.get(sigla) if sigla else None
    # tenta direto por sigla
    if lotacao in unidades_por_sigla:
        return unidades_por_sigla[lotacao]
    # tenta por nome
    if lotacao in unidades_por_nome:
        return unidades_por_nome[lotacao]
    return None


# ──────────────────────────────────────────────
# 3. Importar servidores
# ──────────────────────────────────────────────
print("\n=== Importando servidores ===")

importados = 0
ignorados_duplicados = 0
sem_unidade = {}  # lotacao → lista de nomes

with open(SERVIDORES_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        nome = normaliza(row["SERVIDOR (NOME COMPLETO)"])
        lotacao = normaliza(row["LOTAÇÃO"])
        cargo_nome = normaliza(row["CARGO"])
        cpf = so_digitos(row.get("CPF", ""))
        rg_raw = normaliza(row.get("RG", ""))
        rg = re.sub(r"\s+", "", rg_raw)
        telefone = so_digitos(row.get("TELEFONE", ""))[:11]

        if not nome:
            continue

        unidade = resolver_lotacao(lotacao)

        if unidade is None:
            sem_unidade.setdefault(lotacao, []).append(nome)
            continue

        cargo_obj = None
        if cargo_nome:
            cargo_obj, _ = Cargo.objects.get_or_create(nome=cargo_nome)

        try:
            Servidor.objects.get_or_create(
                nome=nome,
                defaults={
                    "cpf": cpf,
                    "rg": rg,
                    "telefone": telefone,
                    "cargo": cargo_obj,
                    "unidade": unidade,
                },
            )
            importados += 1
        except Exception as e:
            print(f"  ERRO ao importar {nome}: {e}")
            ignorados_duplicados += 1

print(f"\n  {importados} servidores importados.")
if ignorados_duplicados:
    print(f"  {ignorados_duplicados} ignorados por erro/duplicata.")

# ──────────────────────────────────────────────
# 4. Listar servidores sem unidade encontrada
# ──────────────────────────────────────────────
if sem_unidade:
    print(f"\n=== {sum(len(v) for v in sem_unidade.values())} servidores NÃO importados (unidade não encontrada) ===")
    for lotacao, nomes in sorted(sem_unidade.items()):
        print(f"\n  Lotação '{lotacao}' ({len(nomes)} servidores):")
        for n in nomes:
            print(f"    - {n}")
else:
    print("\nTodos os servidores foram importados!")
