import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const source = readFileSync(resolve("static/js/pages/eventos-detalhe.js"), "utf8");

describe("documentos vinculados do evento", () => {
  let enhance;

  beforeEach(() => {
    document.body.innerHTML = `
      <form>
        <input type="hidden" data-cv-date-picker-start-value value="2026-08-10">
        <input type="hidden" data-cv-date-picker-end-value value="2026-08-12">
        <script id="evento-doc-summaries" type="application/json">{
          "oficios": [
            {"id": 1, "title": "Oficio perto", "meta": "10/08", "search_text": "oficio perto", "data_inicio": "2026-08-10", "data_fim": "2026-08-10"},
            {"id": 2, "title": "Oficio longe", "meta": "30/08", "search_text": "oficio longe", "data_inicio": "2026-08-30", "data_fim": "2026-08-30"}
          ]
        }</script>
        <div data-evento-doc-picker data-evento-periodo-inicio="2026-08-10" data-evento-periodo-fim="2026-08-12" data-evento-doc-tolerancia="5">
          <section data-doc-tab-panel="oficios">
            <div data-related-picker-root>
              <input type="search" data-related-picker-search>
              <select multiple data-evento-doc-field="oficios">
                <option value="1">Perto</option><option value="2">Longe</option>
              </select>
              <div data-related-picker-list></div>
              <p data-related-picker-empty hidden></p>
            </div>
          </section>
        </div>
      </form>
    `;
    window.CV = {
      util: { normalize: (value) => String(value || "").toLowerCase() },
      pickerParts: {
        createRelatedCard: ({ title, value }) => {
          const card = document.createElement("button");
          card.type = "button";
          card.dataset.value = String(value);
          card.textContent = title;
          return card;
        },
      },
      registerEnhancer: vi.fn((_name, callback) => { enhance = callback; }),
    };
    window.eval(source);
    enhance(document);
  });

  it("refiltra com o periodo ativo ainda nao salvo", () => {
    const list = document.querySelector("[data-related-picker-list]");
    expect(list.textContent).toContain("Oficio perto");
    expect(list.textContent).not.toContain("Oficio longe");

    const start = document.querySelector("[data-cv-date-picker-start-value]");
    const end = document.querySelector("[data-cv-date-picker-end-value]");
    start.value = "2026-08-29";
    end.value = "2026-08-31";
    end.dispatchEvent(new Event("change", { bubbles: true }));

    expect(list.textContent).not.toContain("Oficio perto");
    expect(list.textContent).toContain("Oficio longe");

    start.value = "";
    end.value = "";
    end.dispatchEvent(new Event("change", { bubbles: true }));

    expect(list.textContent).toContain("Oficio perto");
    expect(list.textContent).toContain("Oficio longe");
  });

  it("filtra pela busca do picker, sem botao de limpar proprio", () => {
    // O botão "×" desenhado à mão saiu com a migração para o `c-v2.related_picker`
    // (2026-08-18): o campo é `type="search"` e o navegador já entrega o dele.
    // O que o painel deve provar agora é o filtro, e que ninguém reintroduziu o
    // botão — se ele voltar, passam a existir dois "limpar" na mesma linha.
    const search = document.querySelector("[data-related-picker-search]");
    const list = document.querySelector("[data-related-picker-list]");

    expect(search.type).toBe("search");
    // Pelo GANCHO, nunca pela classe: `test_picker_contract` proíbe achar parte
    // de picker por classe CSS, e era por este atributo que o código bindava o
    // botão. Nenhum `<button>` genérico serve de trava aqui — as próprias
    // linhas do resultado são botões.
    expect(document.querySelector("[data-evento-doc-clear]")).toBeNull();

    search.value = "perto";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    expect(list.textContent).toContain("Oficio perto");
    expect(list.textContent).not.toContain("Oficio longe");
    expect(search.closest("[data-related-picker-root]").classList).toContain(
      "search-picker--has-query",
    );

    search.value = "";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    expect(list.textContent).toContain("Oficio perto");
    expect(search.closest("[data-related-picker-root]").classList).not.toContain(
      "search-picker--has-query",
    );
  });

  it("mantem um listener delegado quando o enhancer roda de novo", () => {
    const form = document.querySelector("form");
    const addSpy = vi.spyOn(form, "addEventListener");

    const original = document.querySelector("[data-evento-doc-picker]");
    const replacement = original.cloneNode(true);
    replacement.removeAttribute("data-evento-doc-picker-bound");
    original.replaceWith(replacement);
    enhance(replacement);

    expect(addSpy.mock.calls.filter(([name]) => name === "change")).toHaveLength(0);
    expect(form.dataset.eventoDocPeriodBound).toBe("true");
  });
});
