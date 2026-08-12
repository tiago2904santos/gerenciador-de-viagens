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
              <input data-evento-doc-search="oficios">
              <button type="button" data-evento-doc-clear="oficios">x</button>
              <select multiple data-evento-doc-field="oficios">
                <option value="1">Perto</option><option value="2">Longe</option>
              </select>
              <div data-evento-doc-list="oficios"></div>
              <p data-evento-doc-empty="oficios" hidden></p>
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
    const list = document.querySelector('[data-evento-doc-list="oficios"]');
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

  it("mostra e executa o limpar da busca padrao", () => {
    const root = document.querySelector("[data-related-picker-root]");
    const search = document.querySelector('[data-evento-doc-search="oficios"]');
    search.value = "perto";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    expect(root.classList.contains("search-picker--has-query")).toBe(true);

    document.querySelector('[data-evento-doc-clear="oficios"]').click();

    expect(search.value).toBe("");
    expect(root.classList.contains("search-picker--has-query")).toBe(false);
    expect(document.activeElement).toBe(search);
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
