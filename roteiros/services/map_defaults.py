from cadastros.models import ConfiguracaoSistema
from core.errors import capture


MAPA_UF_FALLBACK = "PR"
MAPA_UF_CENTERS = {
    "AC": {"lat": -8.77, "lng": -70.55, "zoom": 6},
    "AL": {"lat": -9.62, "lng": -36.82, "zoom": 7},
    "AP": {"lat": 1.41, "lng": -51.77, "zoom": 6},
    "AM": {"lat": -3.47, "lng": -65.1, "zoom": 5},
    "BA": {"lat": -12.96, "lng": -41.7, "zoom": 6},
    "CE": {"lat": -5.2, "lng": -39.53, "zoom": 7},
    "DF": {"lat": -15.8, "lng": -47.86, "zoom": 9},
    "ES": {"lat": -19.57, "lng": -40.65, "zoom": 7},
    "GO": {"lat": -15.98, "lng": -49.86, "zoom": 6},
    "MA": {"lat": -4.96, "lng": -45.27, "zoom": 6},
    "MT": {"lat": -12.64, "lng": -55.42, "zoom": 6},
    "MS": {"lat": -20.51, "lng": -54.54, "zoom": 6},
    "MG": {"lat": -18.51, "lng": -44.55, "zoom": 6},
    "PA": {"lat": -3.79, "lng": -52.48, "zoom": 6},
    "PB": {"lat": -7.12, "lng": -36.72, "zoom": 7},
    "PR": {"lat": -24.89, "lng": -51.55, "zoom": 7},
    "PE": {"lat": -8.38, "lng": -37.86, "zoom": 7},
    "PI": {"lat": -7.72, "lng": -42.73, "zoom": 6},
    "RJ": {"lat": -22.25, "lng": -42.66, "zoom": 8},
    "RN": {"lat": -5.81, "lng": -36.59, "zoom": 7},
    "RS": {"lat": -30.17, "lng": -53.5, "zoom": 6},
    "RO": {"lat": -10.83, "lng": -63.34, "zoom": 6},
    "RR": {"lat": 1.99, "lng": -61.33, "zoom": 6},
    "SC": {"lat": -27.33, "lng": -50.44, "zoom": 7},
    "SP": {"lat": -22.19, "lng": -48.79, "zoom": 7},
    "SE": {"lat": -10.57, "lng": -37.45, "zoom": 8},
    "TO": {"lat": -10.25, "lng": -48.25, "zoom": 6},
}
MAPA_CEP_RANGES = (
    ("AC", ((69900000, 69999999),)),
    ("AL", ((57000000, 57999999),)),
    ("AP", ((68900000, 68999999),)),
    ("AM", ((69000000, 69299999), (69400000, 69899999))),
    ("BA", ((40000000, 48999999),)),
    ("CE", ((60000000, 63999999),)),
    ("DF", ((70000000, 72799999), (73000000, 73699999))),
    ("ES", ((29000000, 29999999),)),
    ("GO", ((72800000, 72999999), (73700000, 76799999))),
    ("MA", ((65000000, 65999999),)),
    ("MT", ((78000000, 78899999),)),
    ("MS", ((79000000, 79999999),)),
    ("MG", ((30000000, 39999999),)),
    ("PA", ((66000000, 68899999),)),
    ("PB", ((58000000, 58999999),)),
    ("PR", ((80000000, 87999999),)),
    ("PE", ((50000000, 56999999),)),
    ("PI", ((64000000, 64999999),)),
    ("RJ", ((20000000, 28999999),)),
    ("RN", ((59000000, 59999999),)),
    ("RS", ((90000000, 99999999),)),
    ("RO", ((76800000, 76999999),)),
    ("RR", ((69300000, 69399999),)),
    ("SC", ((88000000, 89999999),)),
    ("SP", ((1000000, 19999999),)),
    ("SE", ((49000000, 49999999),)),
    ("TO", ((77000000, 77999999),)),
)


def resolve_uf_from_cep(cep: str) -> str:
    cep_digits = "".join(c for c in (cep or "") if c.isdigit())
    if len(cep_digits) != 8:
        return MAPA_UF_FALLBACK
    cep_int = int(cep_digits)
    for uf, ranges in MAPA_CEP_RANGES:
        for start, end in ranges:
            if start <= cep_int <= end:
                return uf
    return MAPA_UF_FALLBACK


def build_roteiro_map_defaults():
    try:
        config = ConfiguracaoSistema.get_singleton()
        uf = resolve_uf_from_cep(config.cep)
    except Exception as exc:
        capture(exc, "roteiros.mapa_defaults.configuracao")
        uf = MAPA_UF_FALLBACK
    center = MAPA_UF_CENTERS.get(uf) or MAPA_UF_CENTERS[MAPA_UF_FALLBACK]
    return {
        "uf": uf,
        "default_center": [center["lat"], center["lng"]],
        "default_zoom": center["zoom"],
    }
