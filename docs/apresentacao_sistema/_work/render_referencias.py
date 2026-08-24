from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "apresentacao_sistema" / "_work" / "referencias_render"
OUT.mkdir(parents=True, exist_ok=True)

REFERENCIAS = {
    "guia": Path.home() / "Downloads" / "Guia_Rapido_Relatorio_Tecnico_Viagem_PCPR_VERSAO_FINAL.pdf",
    "manual": Path.home() / "Downloads" / "Manual_Diarias_PCPR_FINAL_07-05-2026.pdf",
}


def renderizar() -> None:
    escolhas = {"guia": [0], "manual": [0, 1, 2, 3, 4, 7, 18, 28, 39, 49]}
    miniaturas: list[tuple[str, Image.Image]] = []
    for chave, caminho in REFERENCIAS.items():
        pdf = pdfium.PdfDocument(str(caminho))
        for indice in escolhas[chave]:
            if indice >= len(pdf):
                continue
            imagem = pdf[indice].render(scale=1.6).to_pil().convert("RGB")
            destino = OUT / f"{chave}_{indice + 1:02d}.png"
            imagem.save(destino, quality=92)
            thumb = imagem.copy()
            thumb.thumbnail((420, 300))
            miniaturas.append((f"{chave} · p. {indice + 1}", thumb))

    largura, altura_celula = 940, 350
    folha = Image.new("RGB", (largura, altura_celula * ((len(miniaturas) + 1) // 2)), "#eceff3")
    draw = ImageDraw.Draw(folha)
    for pos, (rotulo, imagem) in enumerate(miniaturas):
        coluna, linha = pos % 2, pos // 2
        x, y = coluna * 470 + 25, linha * altura_celula + 32
        folha.paste(imagem, (x, y + 28))
        draw.text((x, y), rotulo, fill="#152238")
    folha.save(OUT / "contato_referencias.png")


if __name__ == "__main__":
    renderizar()
