import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const source = readFileSync(resolve("static/js/pages/ordens-servico-form.js"), "utf8");

describe("picker de ofícios da ordem de serviço", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <form data-os-form>
        <select name="oficios" multiple>
          <option value="1">Ofício 1</option>
          <option value="2">Ofício 2</option>
        </select>
        <input id="id_os_oficio_busca" type="search">
        <div id="os-oficio-lista"></div>
        <p id="os-oficio-lista-empty" hidden></p>
      </form>
    `;

    const summaries = {
      1: { id: 1, order: 1, label: "Ofício 1", search_text: "ofício 1" },
      2: { id: 2, order: 2, label: "Ofício 2", search_text: "ofício 2" },
    };
    window.CV = {
      documentSource: {
        read: vi.fn(() => summaries),
        selected: vi.fn(() => []),
        apply: vi.fn(),
      },
      documentSearch: { attach: vi.fn() },
      locationRows: { initManagedRows: vi.fn() },
      pickerParts: {
        createRouteCard: vi.fn((summary, config) => {
          const button = document.createElement("button");
          button.type = "button";
          button.dataset.value = String(summary.id);
          button.setAttribute("aria-pressed", config.active ? "true" : "false");
          button.textContent = summary.label;
          return button;
        }),
      },
      util: {
        normalize: (value) => String(value || "").toLowerCase(),
        debounce: (callback) => callback,
      },
    };
  });

  it("mantém a rolagem ao selecionar um ofício no meio da lista", () => {
    const list = document.querySelector("#os-oficio-lista");
    let virtualScrollTop = 0;
    const innerHTML = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
    Object.defineProperty(list, "scrollTop", {
      configurable: true,
      get: () => virtualScrollTop,
      set: (value) => { virtualScrollTop = value; },
    });
    Object.defineProperty(list, "innerHTML", {
      configurable: true,
      get: () => innerHTML.get.call(list),
      set: (value) => {
        innerHTML.set.call(list, value);
        if (value === "") virtualScrollTop = 0;
      },
    });

    window.eval(source);
    document.dispatchEvent(new Event("DOMContentLoaded"));
    virtualScrollTop = 180;

    list.querySelector("button[data-value='2']").click();

    expect(virtualScrollTop).toBe(180);
    expect(document.querySelector("select[name='oficios'] option[value='2']").selected).toBe(true);
  });
});
