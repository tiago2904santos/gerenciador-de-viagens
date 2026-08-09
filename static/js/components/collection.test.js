import { beforeEach, describe, expect, it, vi } from "vitest";

const registerEnhancer = vi.fn();
window.CV = {
  registerEnhancer,
  util: {
    debounce(fn) {
      fn.cancel = vi.fn();
      return fn;
    },
    normalize(value) {
      return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    },
  },
};
await import("./collection.js");
const registration = registerEnhancer.mock.calls[0];

function clientMarkup() {
  return `
    <section data-collection data-collection-mode="client">
      <input data-collection-filter="search" value="">
      <select data-collection-filter="status">
        <option value="">Todos</option><option value="ativo">Ativo</option>
      </select>
      <button data-collection-clear>Limpar</button>
      <output data-collection-count data-collection-count-template="{{visible}} de {{total}}"></output>
      <p data-collection-empty hidden>Nenhum</p>
      <article data-collection-item data-search-text="João Silva" data-status-value="ativo">João</article>
      <article data-collection-item data-search-text="Maria Souza" data-status-value="inativo">Maria</article>
    </section>`;
}

describe("CV.collection", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    delete window.CV.http;
  });

  it("se registra no coordenador global", () => {
    expect(registration).toEqual(["collection", window.CV.collection.init]);
  });

  it("filtra no cliente, atualiza contagem, vazio, estado e evento", () => {
    document.body.innerHTML = clientMarkup();
    const collection = document.querySelector("[data-collection]");
    const updated = vi.fn();
    collection.addEventListener("cv:collection:updated", updated);
    const search = collection.querySelector('[data-collection-filter="search"]');
    const status = collection.querySelector('[data-collection-filter="status"]');
    search.value = "joao silva";
    status.value = "ativo";

    const state = window.CV.collection.apply(collection);

    expect(state).toMatchObject({ visible: 1, hidden: 1, total: 2 });
    expect(collection.querySelector("[data-collection-count]").textContent).toBe("1 de 2");
    expect(collection.querySelector("[data-collection-empty]").hidden).toBe(true);
    expect(Array.from(collection.querySelectorAll("[data-collection-item]")).map((item) => item.hidden)).toEqual([false, true]);
    expect(window.CV.collection.getState(collection)).toBe(state);
    expect(updated).toHaveBeenCalledOnce();
  });

  it("inicializa uma vez, reage aos controles e limpa o modo cliente", () => {
    document.body.innerHTML = clientMarkup();
    const collection = document.querySelector("[data-collection]");
    expect(window.CV.collection.init(document)).toBe(1);
    expect(window.CV.collection.init(document)).toBe(1);
    expect(collection.getAttribute("data-collection-bound")).toBe("true");

    const search = collection.querySelector("input");
    search.value = "nao existe";
    search.dispatchEvent(new Event("input"));
    expect(collection.querySelector("[data-collection-empty]").hidden).toBe(false);

    collection.querySelector("[data-collection-clear]").click();
    expect(search.value).toBe("");
    expect(window.CV.collection.getState(collection).visible).toBe(2);
    expect(window.CV.collection.clear(collection).visible).toBe(2);
    expect(window.CV.collection.clear(null)).toBeNull();
  });

  it("normaliza e avalia filtros publicos", () => {
    const item = document.createElement("article");
    item.textContent = "Álvaro da Silva";
    item.dataset.statusValue = "Em análise";
    expect(window.CV.collection.normalize(" ÁÇÃO ")).toBe("acao");
    expect(window.CV.collection.matches(item, { searchTerms: ["alvaro", "silva"], status: "em analise" })).toBe(true);
    expect(window.CV.collection.matches(item, { searchTerms: ["maria"], status: "" })).toBe(false);
    expect(window.CV.collection.matches(item, { searchTerms: [], status: "ativo" })).toBe(false);
  });

  it("troca o painel no modo servidor e preserva URL e foco", async () => {
    document.body.innerHTML = `
      <section data-collection data-collection-mode="server">
        <form action="/pessoas" data-collection-form>
          <input name="q" data-collection-filter="search" value="inicial">
          <button data-collection-clear>Limpar</button>
        </form>
        <div class="list-panel"><p>Antigo</p></div>
      </section>`;
    const fetchText = vi.fn(async () => ({ ok: true, data: '<div class="list-panel"><p>Novo</p></div>' }));
    const destroy = vi.fn();
    window.CV.http = { fetchText };
    window.CV.registry = { destroy };
    const replaceState = vi.spyOn(window.history, "replaceState");
    const collection = document.querySelector("[data-collection]");
    const input = collection.querySelector("input");

    expect(window.CV.collection.init(collection)).toBe(1);
    input.value = "novo valor";
    input.focus();
    input.setSelectionRange(1, 3);
    input.dispatchEvent(new Event("input"));
    await vi.waitFor(() => expect(fetchText).toHaveBeenCalledOnce());
    await vi.waitFor(() => expect(collection.querySelector(".list-panel").textContent).toContain("Novo"));

    expect(fetchText).toHaveBeenCalledWith("/pessoas?q=novo+valor", { headers: { "X-Requested-With": "fetch" } });
    expect(destroy).toHaveBeenCalledOnce();
    expect(replaceState).toHaveBeenCalledWith({}, "", "/pessoas?q=novo+valor");
    expect(document.activeElement).toBe(input);
    expect(input.selectionStart).toBe(1);
    expect(input.selectionEnd).toBe(3);
  });

  it("recusa colecoes incompletas e limpa controles de servidor sem aplicar cliente", () => {
    document.body.innerHTML = `
      <section id="invalid" data-collection data-collection-mode="outro"></section>
      <section id="server" data-collection data-collection-mode="server">
        <form data-collection-form><input data-collection-filter="search" value="x"></form>
      </section>`;
    const server = document.querySelector("#server");
    expect(window.CV.collection.init(document)).toBe(2);
    expect(document.querySelector("#invalid").hasAttribute("data-collection-bound")).toBe(false);
    expect(server.hasAttribute("data-collection-bound")).toBe(false);
    expect(window.CV.collection.clear(server)).toBeNull();
    expect(server.querySelector("input").value).toBe("");
    expect(window.CV.collection.getState(document.createElement("section"))).toBeNull();
  });
});
