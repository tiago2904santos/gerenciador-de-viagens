"""Acha (e apaga) a regra de CSS que nenhum seletor pode alcancar (NOVO-30 fase 5a).

POR QUE ESTE INSTRUMENTO EXISTE

A fase 5 do plano diz "apagar o CSS antigo". Medindo em 04/08 nao havia **arquivo**
orfao: os 63 estao vivos, 35 pelo bundle e 28 por `{% block extra_css %}`. O que
sobra de verdade e regra cuja classe nenhum template, JS ou Python emite. Isso a
suite nao ve — CSS morto nao quebra teste, so pesa.

O CRITERIO (deliberadamente conservador: na duvida, a classe vive)

Uma classe `.foo-bar` esta viva se o texto `foo-bar` aparece em qualquer arquivo de
codigo **em fronteira de palavra a esquerda**, sem exigir fronteira a direita. Isso
cobre de uma vez:

  - emissao literal .................. `class="foo-bar"`
  - filho/modificador BEM ............ `class="foo-bar__item"` mantem `.foo-bar`
  - composicao dinamica .............. `class="cv-btn cv-btn--{{ v }}"` mantem toda
                                        `.cv-btn--*`, porque o literal `cv-btn--`
                                        casa como prefixo

E ainda: se a classe tem sufixo BEM, o sufixo com o separador (`__identity`,
`--accent`) tambem e procurado sozinho, para pegar concatenacao em JS do tipo
`base + '__identity'`.

O QUE E APAGADO

- seletor cuja classe (fora de `:is()`/`:where()`/`:has()`) esta morta;
- regra que ficou sem nenhum seletor vivo;
- regra sem declaracao nenhuma — `.a {}` — que a fase 4 deixou para tras ao tirar
  os `!important`;
- `@media`/`@supports`/`@layer` que ficaram vazios.

Seletor sem classe alguma (`button`, `[data-x]`) nunca e tocado.

Uso:

    python scripts/css_classes_mortas.py             # relatorio
    python scripts/css_classes_mortas.py --lista     # so os nomes, um por linha
    python scripts/css_classes_mortas.py --aplicar   # reescreve os arquivos

Depois de `--aplicar`, `scripts/medir_estilos.py --diff` tem de dar **0**: se uma
propriedade computada mudou, a regra nao estava morta. Esse e o gate desta fase, e
nao a suite — a suite fica verde de qualquer jeito.
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(RAIZ, "static", "css")

# Onde uma classe pode nascer. Fora de proposito: o proprio CSS (citar a si mesmo
# nao e prova de vida) e `docs/` (documentacao cita nome de classe o tempo todo,
# inclusive a lista de classes mortas — que se marcaria viva sozinha).
CODIGO_EXT = (".html", ".py", ".js", ".svg", ".json")
IGNORA_DIR = {".git", "__pycache__", "node_modules", "venv", ".venv", "staticfiles",
              "htmlcov", "media", "docs"}

# Diretorios de CSS que este instrumento nao toca: sao artefatos gerados.
CSS_GERADO = {"shell.bundle.css"}


_PALAVRA = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


class Corpus:
    """Todo nome que o codigo emite, indexado para consulta em tempo de log.

    `.foo` viva sse alguma palavra do codigo comeca por `foo` — a lista ordenada
    mais uma busca binaria responde isso sem varrer megabytes por classe.
    """

    def __init__(self):
        palavras, sufixos = set(), set()
        for base, dirs, arqs in os.walk(RAIZ):
            dirs[:] = [d for d in dirs if d not in IGNORA_DIR]
            if os.path.abspath(base).startswith(CSS):
                continue
            for a in arqs:
                if not a.endswith(CODIGO_EXT):
                    continue
                try:
                    with open(os.path.join(base, a), encoding="utf-8",
                              errors="ignore") as fh:
                        palavras.update(_PALAVRA.findall(fh.read()))
                except OSError:
                    pass
        for p in palavras:
            for m in re.finditer(r"(?=(__|--))", p):   # `a__b--c` -> `__b--c`, `--c`
                sufixos.add(p[m.start():])
        self.ordenadas = sorted(palavras)
        self.sufixos = sufixos
        # Prefixo de composicao: `class="...item-icon--{{ tone }}"` deixa no
        # arquivo a palavra `...item-icon--`, que e MENOR que a classe final. Sem
        # esta lista o instrumento matava `.cv-action-menu__item-icon--docx`, que
        # esta viva — foi o unico falso positivo que a suite pegou na fase 5a.
        self.composicao = tuple(p for p in palavras if p.endswith(("-", "_")))
        self.cache = {}

    def viva(self, classe):
        if classe not in self.cache:
            self.cache[classe] = self._viva(classe)
        return self.cache[classe]

    def _viva(self, classe):
        import bisect
        i = bisect.bisect_left(self.ordenadas, classe)
        if i < len(self.ordenadas) and self.ordenadas[i].startswith(classe):
            return True
        if classe.startswith(self.composicao):
            return True
        # Concatenacao em JS: `base + '__identity'` nunca forma a palavra inteira.
        m = re.search(r"(__|--)[A-Za-z0-9_-]+$", classe)
        return bool(m) and m.group(0) in self.sufixos


# --- leitura do CSS -------------------------------------------------------

def sem_comentario(css):
    """Troca cada comentario por espacos de mesmo tamanho: as posicoes nao andam."""
    saida = list(css)
    for m in re.finditer(r"/\*.*?\*/", css, re.S):
        for i in range(m.start(), m.end()):
            if saida[i] != "\n":
                saida[i] = " "
    return "".join(saida)


ANINHADAS = ("@media", "@supports", "@layer", "@container", "@scope")


def regras(css, ini=0, fim=None):
    """Percorre o CSS e devolve (inicio_prelude, inicio_bloco, fim_regra, prelude).

    Entra em @media/@supports/@layer; pula @keyframes e afins por inteiro.
    """
    fim = len(css) if fim is None else fim
    saida = []
    i, marco = ini, ini
    while i < fim:
        c = css[i]
        if c in "\"'":
            j = i + 1
            while j < fim and css[j] != c:
                j += 2 if css[j] == "\\" else 1
            i = j + 1
            continue
        if c == ";":
            marco = i + 1
        elif c == "{":
            prelude = css[marco:i].strip()
            j, prof = i + 1, 1
            while j < fim and prof:
                if css[j] in "\"'":
                    q, j = css[j], j + 1
                    while j < fim and css[j] != q:
                        j += 2 if css[j] == "\\" else 1
                elif css[j] == "{":
                    prof += 1
                elif css[j] == "}":
                    prof -= 1
                j += 1
            if prelude.startswith(ANINHADAS):
                saida.extend(regras(css, i + 1, j - 1))
            elif not prelude.startswith("@"):
                saida.append((marco, i, j, prelude))
            i, marco = j, j
            continue
        i += 1
    return saida


# Classe fora de pseudo-classe funcional: `:is(.a, .b)` nao mata a regra, porque
# basta um dos ramos casar.
def classes_decisivas(seletor):
    plano, prof = [], 0
    for c in seletor:
        if c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
        elif prof == 0:
            plano.append(c)
    return re.findall(r"\.(-?[A-Za-z_][\w-]*)", "".join(plano))


def separar_seletores(prelude):
    """Quebra a lista de seletores nas virgulas de topo — e so nelas.

    Regex nao serve aqui. `:is(\n .a,\n .b)` tem virgula DENTRO do parenteses, e
    uma heuristica que erre isso parte o `:is(` no meio: sobra parenteses aberto,
    o navegador declara o arquivo invalido e descarta todas as regras dali em
    diante. Foi o que aconteceu na primeira aplicacao — 1.162 regras sobreviveram
    de ~4.000, e os icones sumiram do sistema inteiro.
    """
    partes, atual, prof = [], [], 0
    for c in prelude:
        if c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
        if c == "," and prof == 0:
            partes.append("".join(atual))
            atual = []
            continue
        atual.append(c)
    partes.append("".join(atual))
    return [p.strip() for p in partes if p.strip()]


def tem_declaracao(bloco):
    return bool(re.search(r"[\w-]\s*:", sem_comentario(bloco)))


def arquivos_css():
    for base, dirs, arqs in os.walk(CSS):
        dirs[:] = [d for d in dirs if d not in IGNORA_DIR]
        for a in sorted(arqs):
            if a.endswith(".css") and a not in CSS_GERADO:
                yield os.path.join(base, a)


def analisar(corpo):
    """Devolve, por arquivo: cortes (inicio, fim), classes mortas, linhas."""
    resultado = {}
    for caminho in arquivos_css():
        with open(caminho, encoding="utf-8") as fh:
            bruto = fh.read()
        limpo = sem_comentario(bruto)
        cortes, mortas = [], {}
        for pre_ini, bloco_ini, fim, prelude in regras(limpo):
            bloco = bruto[bloco_ini + 1:fim - 1]
            seletores = separar_seletores(prelude)
            vivos = []
            for s in seletores:
                cls = classes_decisivas(s)
                morta = [c for c in cls if not corpo.viva(c)]
                if morta:
                    for c in morta:
                        mortas[c] = mortas.get(c, 0) + 1
                else:
                    vivos.append(s)
            if not tem_declaracao(bloco):
                vivos = []          # `.a {}` nao pinta nada; sai inteira
            if not vivos:
                cortes.append((pre_ini, fim, ""))            # a regra inteira sai
            elif len(vivos) != len(seletores):
                # Aqui a regra fica: so o seletor morto sai. O recuo antes do
                # prelude e preservado — sem isso o `}` da regra anterior cola no
                # seletor seguinte.
                recuo = len(limpo[pre_ini:bloco_ini]) - len(limpo[pre_ini:bloco_ini].lstrip())
                cortes.append((pre_ini + recuo, bloco_ini, ",\n".join(vivos) + " "))
        if cortes:
            linhas = sum(bruto.count("\n", i, f) for i, f, _ in cortes)
            resultado[caminho] = (cortes, mortas, linhas)
    return resultado


def aplicar(caminho, cortes):
    """Troca de tras para frente, para os offsets do comeco continuarem validos."""
    with open(caminho, encoding="utf-8") as fh:
        bruto = fh.read()
    for ini, fim, troca in sorted(cortes, reverse=True):
        # Rede de seguranca: prelude com parenteses aberto invalida o arquivo
        # INTEIRO no navegador, e nem a suite nem o balanco de chaves acusam.
        if troca.count("(") != troca.count(")"):
            raise SystemExit(f"{caminho}: corte deixaria parenteses aberto: {troca!r}")
        bruto = bruto[:ini] + troca + bruto[fim:]
    # Comentario que ficou orfao (a regra que ele explicava saiu) e linha em branco
    # sobrando entram no mesmo pente.
    bruto = re.sub(r"\n{3,}", "\n\n", bruto)
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(bruto)


if __name__ == "__main__":
    achado = analisar(Corpus())
    if "--lista" in sys.argv:
        nomes = sorted({c for _, (_, m, _) in achado.items() for c in m})
        print("\n".join(nomes))
        sys.exit(0)

    total_l = total_r = 0
    for caminho, (cortes, mortas, linhas) in sorted(achado.items()):
        total_l += linhas
        total_r += len(cortes)
        print(f"{linhas:6d} linhas  {len(cortes):4d} cortes  "
              f"{os.path.relpath(caminho, RAIZ)}")
    nomes = sorted({c for _, (_, m, _) in achado.items() for c in m})
    print(f"\n{total_r} cortes, ~{total_l} linhas, {len(nomes)} classes sem emissor")

    if "--aplicar" in sys.argv:
        for caminho, (cortes, _, _) in achado.items():
            aplicar(caminho, cortes)
        print("aplicado.")
