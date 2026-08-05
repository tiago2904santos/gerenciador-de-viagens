"""Captura um album de screenshots de todas as telas do sistema.

Instrumento, nao gate: exige servidor de pe, Chromium e um banco com dados de
demonstracao, entao roda sob demanda e nunca no CI.

    python manage.py resetar_banco_demo
    python manage.py runserver 127.0.0.1:8000 --noreload &
    python scripts/album_telas.py

O catalogo em `TELAS` cobre toda rota que renderiza pagina. Ficam de fora, por
nao serem tela: endpoints de API/JSON, autosave, download de arquivo, rotas
POST-only (excluir, cancelar, definir padrao) e o fluxo publico de assinatura,
que exige token vivo.

Os catalogos (`unidades`, `cargos`, `combustiveis`, ...) nao tem pagina de
edicao propria — desde `P-02` a edicao acontece em linha, na propria lista. Por
isso essas telas entram como estado interativo (`ACOES`), capturado depois de
clicar no botao de editar da primeira linha.

Cada tela sai nos dois temas. Usuario e senha vem de ALBUM_USUARIO/ALBUM_SENHA.
Nao serve para ambiente com dado real.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("ALBUM_BASE", "http://127.0.0.1:8000")
SAIDA = Path(os.environ.get("ALBUM_SAIDA", "screenshots/album-sistema"))
USUARIO = os.environ.get("ALBUM_USUARIO", "demo")
SENHA = os.environ.get("ALBUM_SENHA", "demo-album-2026")
CHROMIUM = os.environ.get(
    "ALBUM_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
)
VIEWPORT = {"width": 1440, "height": 900}
TEMAS = ("light", "dark")
#: telas muito longas viram imagens gigantes; acima disso a captura e recortada.
ALTURA_MAX = 6000

# PKs do banco de demonstracao (`resetar_banco_demo`). Sao resolvidos em tempo
# de execucao por `_resolver_pks`, com estes valores como ponto de partida.
PKS = {
    "oficio": 6,
    "roteiro": 6,
    "plano": 6,
    "termo": 6,
    "ordem": 6,
    "prestacao_servidor": 11,
    "evento": 1,
    "servidor": 11,
    "viatura": 11,
}

UI_LAB2_SLUGS = [
    "shells", "headers", "steppers", "section-cards", "fields", "selects",
    "calendars", "buttons", "footers", "badges", "feedback", "modals",
    "domain-cards", "signatures", "documents",
]


def montar_telas(pk: dict) -> list[tuple[str, str, str]]:
    """(grupo, titulo, rota) de cada tela do album."""
    return [
        ("Acesso", "Login", "/login/"),
        ("Acesso", "Perfil do usuário", "/perfil/"),

        ("Painel", "Dashboard", "/"),

        ("Eventos", "Lista de eventos", "/eventos/"),
        ("Eventos", "Novo evento", "/eventos/novo/"),
        ("Eventos", "Detalhe do evento", f"/eventos/{pk['evento']}/"),
        ("Eventos", "Editar evento", f"/eventos/{pk['evento']}/editar/"),
        ("Eventos", "Fluxo guiado — etapa 1", f"/eventos/{pk['evento']}/guiado/"),
        ("Eventos", "Fluxo guiado — etapa 2", f"/eventos/{pk['evento']}/guiado/etapa-2/"),
        ("Eventos", "Fluxo guiado — etapa 3", f"/eventos/{pk['evento']}/guiado/etapa-3/"),
        ("Eventos", "Fluxo guiado — etapa 4", f"/eventos/{pk['evento']}/guiado/etapa-4/"),
        ("Eventos", "Fluxo guiado — termos", f"/eventos/{pk['evento']}/guiado_termos/"),
        ("Eventos", "Tipos de evento", "/eventos/tipos/"),

        ("Ofícios", "Lista de ofícios", "/oficios/"),
        ("Ofícios", "Novo ofício", "/oficios/novo/"),
        ("Ofícios", "Assistente — dados e viajantes", f"/oficios/{pk['oficio']}/dados-viajantes/"),
        ("Ofícios", "Assistente — transporte", f"/oficios/{pk['oficio']}/transporte/"),
        ("Ofícios", "Assistente — roteiro", f"/oficios/{pk['oficio']}/roteiro/"),
        ("Ofícios", "Assistente — justificativa", f"/oficios/{pk['oficio']}/justificativa/"),
        ("Ofícios", "Assistente — resumo", f"/oficios/{pk['oficio']}/resumo/"),
        ("Ofícios", "Assistente — documentos", f"/oficios/{pk['oficio']}/documentos/"),
        ("Ofícios", "Modelos de motivo", "/oficios/modelos-motivo/"),
        ("Ofícios", "Novo modelo de motivo", "/oficios/modelos-motivo/novo/"),

        ("Roteiros", "Lista de roteiros", "/roteiros/"),
        ("Roteiros", "Novo roteiro", "/roteiros/novo/"),
        ("Roteiros", "Editar roteiro", f"/roteiros/{pk['roteiro']}/editar/"),

        ("Termos", "Lista de termos", "/termos/"),
        ("Termos", "Novo termo", "/termos/novo/"),
        ("Termos", "Editar termo", f"/termos/{pk['termo']}/editar/"),

        ("Justificativas", "Lista de justificativas", "/justificativas/"),
        ("Justificativas", "Modelos de justificativa", "/justificativas/modelos/"),
        ("Justificativas", "Novo modelo de justificativa", "/justificativas/modelos/novo/"),

        ("Planos de trabalho", "Lista de planos", "/planos-trabalho/"),
        ("Planos de trabalho", "Assistente — efetivo e diárias", f"/planos-trabalho/{pk['plano']}/efetivo-diarias/"),
        ("Planos de trabalho", "Assistente — atividades", f"/planos-trabalho/{pk['plano']}/atividades/"),
        ("Planos de trabalho", "Assistente — documentos", f"/planos-trabalho/{pk['plano']}/documentos/"),
        ("Planos de trabalho", "Programas solicitantes", "/planos-trabalho/programas/"),
        ("Planos de trabalho", "Novo programa solicitante", "/planos-trabalho/programas/novo/"),
        ("Planos de trabalho", "Horários de atendimento", "/planos-trabalho/horarios/"),
        ("Planos de trabalho", "Novo horário de atendimento", "/planos-trabalho/horarios/novo/"),
        ("Planos de trabalho", "Atividades", "/planos-trabalho/atividades/"),
        ("Planos de trabalho", "Presets de atividades", "/planos-trabalho/presets/"),

        ("Ordens de serviço", "Lista de ordens de serviço", "/ordens-servico/"),
        ("Ordens de serviço", "Nova ordem de serviço", "/ordens-servico/nova/"),
        ("Ordens de serviço", "Editar ordem de serviço", f"/ordens-servico/{pk['ordem']}/editar/"),

        ("Prestações de contas", "Lista de prestações", "/prestacoes-contas/"),
        ("Prestações de contas", "Documentos do servidor", f"/prestacoes-contas/servidor-prestacao/{pk['prestacao_servidor']}/documentos/"),
        ("Prestações de contas", "Relatório de viagem", f"/prestacoes-contas/servidor-prestacao/{pk['prestacao_servidor']}/rt/"),
        ("Prestações de contas", "Diário de bordo", f"/prestacoes-contas/servidor-prestacao/{pk['prestacao_servidor']}/diario/"),
        ("Prestações de contas", "Diário — motorista", f"/prestacoes-contas/servidor-prestacao/{pk['prestacao_servidor']}/diario/motorista/"),
        ("Prestações de contas", "Diário — editar roteiro", f"/prestacoes-contas/servidor-prestacao/{pk['prestacao_servidor']}/diario/editar-roteiro/"),
        ("Prestações de contas", "Consolidado do servidor", f"/prestacoes-contas/servidor-prestacao/{pk['prestacao_servidor']}/consolidado/"),
        ("Prestações de contas", "Modelos de texto", "/prestacoes-contas/modelos-texto/"),
        ("Prestações de contas", "Novo modelo de texto", "/prestacoes-contas/modelos-texto/novo/"),

        ("Diário de bordo", "Lista do diário de bordo", "/diario-bordo/"),

        ("Documentos", "Central de documentos", "/documentos/"),

        ("Cadastros", "Índice de cadastros", "/cadastros/"),
        ("Cadastros", "Configuração — instituição", "/cadastros/configuracao/"),
        ("Cadastros", "Configuração — ofício", "/cadastros/configuracao/oficio/"),
        ("Cadastros", "Configuração — roteiros", "/cadastros/configuracao/roteiros/"),
        ("Cadastros", "Servidores", "/cadastros/servidores/"),
        ("Cadastros", "Novo servidor", "/cadastros/servidores/novo/"),
        ("Cadastros", "Editar servidor", f"/cadastros/servidores/{pk['servidor']}/editar/"),
        ("Cadastros", "Viaturas", "/cadastros/viaturas/"),
        ("Cadastros", "Nova viatura", "/cadastros/viaturas/nova/"),
        ("Cadastros", "Editar viatura", f"/cadastros/viaturas/{pk['viatura']}/editar/"),
        ("Cadastros", "Unidades", "/cadastros/unidades/"),
        ("Cadastros", "Nova unidade", "/cadastros/unidades/nova/"),
        ("Cadastros", "Cargos", "/cadastros/cargos/"),
        ("Cadastros", "Novo cargo", "/cadastros/cargos/novo/"),
        ("Cadastros", "Combustíveis", "/cadastros/combustiveis/"),
        ("Cadastros", "Novo combustível", "/cadastros/combustiveis/novo/"),
        ("Cadastros", "Cidades", "/cadastros/cidades/"),
        ("Cadastros", "Nova cidade", "/cadastros/cidades/nova/"),
        ("Cadastros", "Estados", "/cadastros/estados/"),

        ("Usuários e áreas", "Lista de usuários", "/usuarios/"),
        ("Usuários e áreas", "Áreas de trabalho", "/usuarios/areas/"),
        ("Usuários e áreas", "Detalhe da área", "/usuarios/areas/3/"),

        ("UI Lab", "Índice", "/dev/ui-lab/"),
        ("UI Lab", "Structures", "/dev/ui-lab/structures/"),
        ("UI Lab", "Lists", "/dev/ui-lab/lists/"),
        ("UI Lab", "Headers", "/dev/ui-lab/headers/"),
        ("UI Lab", "Buttons", "/dev/ui-lab/buttons/"),
        ("UI Lab", "Fields", "/dev/ui-lab/fields/"),
        ("UI Lab", "Selects e filtros", "/dev/ui-lab/selects-filters/"),
        ("UI Lab", "Status", "/dev/ui-lab/status/"),
        ("UI Lab", "Feedback", "/dev/ui-lab/feedback/"),
        ("UI Lab", "Cards", "/dev/ui-lab/cards/"),
        ("UI Lab", "Overlays", "/dev/ui-lab/overlays/"),
        ("UI Lab", "Tables", "/dev/ui-lab/tables/"),
        ("UI Lab", "Documents", "/dev/ui-lab/documents/"),
        ("UI Lab", "Signature", "/dev/ui-lab/signature/"),
        ("UI Lab", "Eventos — cadastro", "/dev/ui-lab/eventos/cadastro/"),
        ("UI Lab", "Eventos — lista", "/dev/ui-lab/eventos/lista/"),

        ("UI Lab 2", "Índice", "/dev/ui-lab-2/"),
    ] + [
        ("UI Lab 2", slug.replace("-", " ").capitalize(), f"/dev/ui-lab-2/{slug}/")
        for slug in UI_LAB2_SLUGS
    ]


#: (grupo, titulo, rota, seletor) — estados abertos por clique.
ACOES = [
    ("Cadastros", "Editar unidade (em linha)", "/cadastros/unidades/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Cadastros", "Editar cargo (em linha)", "/cadastros/cargos/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Cadastros", "Editar combustível (em linha)", "/cadastros/combustiveis/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Cadastros", "Editar estado (em linha)", "/cadastros/estados/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Cadastros", "Confirmar exclusão de servidor", "/cadastros/servidores/", '[data-overlay-target="delete-confirm-modal"]'),
    ("Ofícios", "Editar modelo de motivo (em linha)", "/oficios/modelos-motivo/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Justificativas", "Editar modelo (em linha)", "/justificativas/modelos/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Planos de trabalho", "Editar programa (em linha)", "/planos-trabalho/programas/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Planos de trabalho", "Editar horário (em linha)", "/planos-trabalho/horarios/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Planos de trabalho", "Editar atividade (em linha)", "/planos-trabalho/atividades/", "[data-quick-edit], [data-row-edit-modal]"),
    ("Usuários e áreas", "Novo usuário (em diálogo)", "/usuarios/", '[data-overlay-kind="dialog"]'),
    ("Usuários e áreas", "Nova área (em diálogo)", "/usuarios/areas/", '[data-overlay-kind="dialog"]'),
]


def slug(texto: str) -> str:
    texto = (
        texto.lower()
        .replace("ç", "c").replace("ã", "a").replace("á", "a").replace("à", "a")
        .replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o")
        .replace("ô", "o").replace("õ", "o").replace("ú", "u").replace("—", "-")
    )
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", texto)).strip("-")


def _resolver_pks(pagina) -> dict:
    """Le os PKs reais das listas — o banco demo nao reinicia as sequencias."""
    pks = dict(PKS)
    fontes = {
        "oficio": ("/oficios/", r"/oficios/(\d+)/"),
        "roteiro": ("/roteiros/", r"/roteiros/(\d+)/editar/"),
        "plano": ("/planos-trabalho/", r"/planos-trabalho/(\d+)/"),
        "termo": ("/termos/", r"/termos/(\d+)/editar/"),
        "ordem": ("/ordens-servico/", r"/ordens-servico/(\d+)/editar/"),
        "evento": ("/eventos/", r"/eventos/(\d+)/"),
        "servidor": ("/cadastros/servidores/", r"/cadastros/servidores/(\d+)/editar/"),
        "viatura": ("/cadastros/viaturas/", r"/cadastros/viaturas/(\d+)/editar/"),
        "prestacao_servidor": ("/prestacoes-contas/", r"/servidor-prestacao/(\d+)/"),
    }
    for chave, (rota, padrao) in fontes.items():
        try:
            pagina.goto(BASE + rota, wait_until="domcontentloaded", timeout=20000)
            achados = re.findall(padrao, pagina.content())
        except Exception:
            achados = []
        if achados:
            pks[chave] = int(sorted(set(int(a) for a in achados))[0])
    return pks


def _preparar(pagina, tema: str) -> None:
    """Fixa o tema e desliga o que faria a imagem variar entre execucoes."""
    pagina.evaluate(
        """(tema) => {
            document.documentElement.setAttribute('data-theme', tema);
            try { localStorage.setItem('theme', tema); } catch (e) {}
            const css = document.createElement('style');
            css.textContent =
              '*,*::before,*::after{animation:none!important;' +
              'transition:none!important;caret-color:transparent!important}';
            document.head.appendChild(css);
        }""",
        tema,
    )
    pagina.wait_for_timeout(250)


def _capturar(pagina, destino: Path) -> dict:
    altura = pagina.evaluate("document.documentElement.scrollHeight")
    if altura > ALTURA_MAX:
        pagina.screenshot(
            path=str(destino),
            clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": ALTURA_MAX},
        )
        return {"altura": ALTURA_MAX, "recortada": True}
    pagina.screenshot(path=str(destino), full_page=True)
    return {"altura": altura, "recortada": False}


def _entrar(contexto) -> None:
    pagina = contexto.new_page()
    pagina.goto(BASE + "/login/", wait_until="networkidle")
    pagina.fill("input[name=username]", USUARIO)
    pagina.fill("input[name=password]", SENHA)
    pagina.click("button[type=submit]")
    pagina.wait_for_load_state("networkidle")
    if "/login" in pagina.url:
        raise SystemExit(f"login falhou para {USUARIO!r} — veja ALBUM_USUARIO/ALBUM_SENHA")
    pagina.close()


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    registros: list[dict] = []

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        anonimo = navegador.new_context(viewport=VIEWPORT)
        logado = navegador.new_context(viewport=VIEWPORT)
        _entrar(logado)

        telas = montar_telas(_resolver_pks(logado.new_page()))
        print(f"{len(telas)} telas + {len(ACOES)} estados × {len(TEMAS)} temas")

        for tema in TEMAS:
            (SAIDA / tema).mkdir(parents=True, exist_ok=True)
            pagina_anonima = anonimo.new_page()
            pagina = logado.new_page()

            for i, (grupo, titulo, rota) in enumerate(telas, start=1):
                nome = f"{i:03d}-{slug(grupo)}-{slug(titulo)}.png"
                destino = SAIDA / tema / nome
                alvo = pagina_anonima if rota == "/login/" else pagina
                try:
                    resposta = alvo.goto(BASE + rota, wait_until="networkidle", timeout=30000)
                    status = resposta.status if resposta else 0
                    _preparar(alvo, tema)
                    medida = _capturar(alvo, destino)
                except Exception as erro:
                    print(f"  [ERRO] {tema} {rota} — {str(erro)[:90]}")
                    registros.append({
                        "ordem": i, "grupo": grupo, "titulo": titulo, "rota": rota,
                        "tema": tema, "arquivo": None, "status": "erro",
                        "detalhe": str(erro)[:200],
                    })
                    continue
                print(f"  [{status}] {tema} {nome}")
                registros.append({
                    "ordem": i, "grupo": grupo, "titulo": titulo, "rota": rota,
                    "tema": tema, "arquivo": f"{tema}/{nome}", "status": status,
                    "url_final": alvo.url.replace(BASE, ""), **medida,
                })

            for j, (grupo, titulo, rota, seletor) in enumerate(ACOES, start=len(telas) + 1):
                nome = f"{j:03d}-{slug(grupo)}-{slug(titulo)}.png"
                destino = SAIDA / tema / nome
                try:
                    pagina.goto(BASE + rota, wait_until="networkidle", timeout=30000)
                    _preparar(pagina, tema)
                    pagina.locator(seletor).first.click(timeout=8000)
                    pagina.wait_for_timeout(700)
                    medida = _capturar(pagina, destino)
                except Exception as erro:
                    print(f"  [ERRO] {tema} {titulo} — {str(erro)[:90]}")
                    registros.append({
                        "ordem": j, "grupo": grupo, "titulo": titulo, "rota": rota,
                        "tema": tema, "arquivo": None, "status": "erro",
                        "detalhe": str(erro)[:200], "interacao": seletor,
                    })
                    continue
                print(f"  [ok] {tema} {nome}")
                registros.append({
                    "ordem": j, "grupo": grupo, "titulo": titulo, "rota": rota,
                    "tema": tema, "arquivo": f"{tema}/{nome}", "status": 200,
                    "interacao": seletor, **medida,
                })

            pagina.close()
            pagina_anonima.close()

        navegador.close()

    (SAIDA / "_relatorio.json").write_text(
        json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    erros = [r for r in registros if r["status"] == "erro"]
    print(f"\n{len(registros) - len(erros)} capturas · {len(erros)} falhas · {SAIDA}")
    for r in erros:
        print(f"  falhou: [{r['tema']}] {r['titulo']} — {r.get('detalhe', '')[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
