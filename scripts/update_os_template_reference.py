"""Torna dinâmica a referência do modelo DOCX especial de Ordem de Serviço."""

from pathlib import Path

from docx import Document


def main() -> None:
    path = Path("documentos/resources/ordem_servico_modelos.docx")
    document = Document(path)
    replacements = 0
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if "Diligências" in run.text:
                run.text = run.text.replace("Diligências", "{{ referencia }}")
                replacements += 1
    if replacements != 1:
        raise RuntimeError(
            f"Esperava substituir uma referência fixa; encontrei {replacements}.",
        )
    document.save(path)


if __name__ == "__main__":
    main()
