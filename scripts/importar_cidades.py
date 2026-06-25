"""
Importa todos os estados e municípios brasileiros com lat/lng.
Fonte: dados-geo-br (https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv)

Uso:
    python manage.py runscript importar_cidades
  ou
    python manage.py shell < scripts/importar_cidades.py
"""

import csv
import io
import urllib.request

from cadastros.models import Cidade, Estado

ESTADOS = [
    ("ACRE", "AC", 12),
    ("ALAGOAS", "AL", 27),
    ("AMAPÁ", "AP", 16),
    ("AMAZONAS", "AM", 13),
    ("BAHIA", "BA", 29),
    ("CEARÁ", "CE", 23),
    ("DISTRITO FEDERAL", "DF", 53),
    ("ESPÍRITO SANTO", "ES", 32),
    ("GOIÁS", "GO", 52),
    ("MARANHÃO", "MA", 21),
    ("MATO GROSSO", "MT", 51),
    ("MATO GROSSO DO SUL", "MS", 50),
    ("MINAS GERAIS", "MG", 31),
    ("PARÁ", "PA", 15),
    ("PARAÍBA", "PB", 25),
    ("PARANÁ", "PR", 41),
    ("PERNAMBUCO", "PE", 26),
    ("PIAUÍ", "PI", 22),
    ("RIO DE JANEIRO", "RJ", 33),
    ("RIO GRANDE DO NORTE", "RN", 24),
    ("RIO GRANDE DO SUL", "RS", 43),
    ("RONDÔNIA", "RO", 11),
    ("RORAIMA", "RR", 14),
    ("SANTA CATARINA", "SC", 42),
    ("SÃO PAULO", "SP", 35),
    ("SERGIPE", "SE", 28),
    ("TOCANTINS", "TO", 17),
]

CAPITAIS = {
    "AC": "RIO BRANCO",
    "AL": "MACEIÓ",
    "AP": "MACAPÁ",
    "AM": "MANAUS",
    "BA": "SALVADOR",
    "CE": "FORTALEZA",
    "DF": "BRASÍLIA",
    "ES": "VITÓRIA",
    "GO": "GOIÂNIA",
    "MA": "SÃO LUÍS",
    "MT": "CUIABÁ",
    "MS": "CAMPO GRANDE",
    "MG": "BELO HORIZONTE",
    "PA": "BELÉM",
    "PB": "JOÃO PESSOA",
    "PR": "CURITIBA",
    "PE": "RECIFE",
    "PI": "TERESINA",
    "RJ": "RIO DE JANEIRO",
    "RN": "NATAL",
    "RS": "PORTO ALEGRE",
    "RO": "PORTO VELHO",
    "RR": "BOA VISTA",
    "SC": "FLORIANÓPOLIS",
    "SP": "SÃO PAULO",
    "SE": "ARACAJU",
    "TO": "PALMAS",
}

CSV_URL = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"


def run():
    print("Criando estados...")
    estados_map = {}
    for nome, sigla, codigo in ESTADOS:
        estado, _ = Estado.objects.get_or_create(
            sigla=sigla,
            defaults={"nome": nome, "codigo_ibge": codigo},
        )
        estados_map[sigla] = estado
    print(f"  {len(estados_map)} estados prontos.")

    print("Baixando CSV de municípios...")
    with urllib.request.urlopen(CSV_URL) as response:
        content = response.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    print(f"  {len(rows)} municípios encontrados.")

    if rows:
        print(f"  Colunas: {list(rows[0].keys())}")

    codigo_uf_map = {str(codigo): sigla for _, sigla, codigo in ESTADOS}

    print("Importando cidades...")
    criadas = 0
    for row in rows:
        codigo_ibge = int(row.get("codigo_ibge") or 0)
        codigo_uf = str(row.get("codigo_uf") or "").strip()
        uf = codigo_uf_map.get(codigo_uf, "")
        nome = (row.get("nome") or "").strip().upper()
        lat = row.get("latitude") or None
        lng = row.get("longitude") or None

        estado = estados_map.get(uf)
        if not estado:
            continue

        capital = CAPITAIS.get(uf) == nome

        Cidade.objects.get_or_create(
            codigo_ibge=codigo_ibge,
            defaults={
                "estado": estado,
                "nome": nome,
                "uf": uf,
                "capital": capital,
                "latitude": lat,
                "longitude": lng,
            },
        )
        criadas += 1

    print(f"  {criadas} cidades importadas com sucesso!")


run()
