/**
 * NOVO-85: a armadilha de foco da gaveta vazava no tema escuro.
 *
 * O seletor antigo era
 *   'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
 * e `button:not([disabled])` casa com botao `tabindex="-1"`, que o navegador
 * nunca alcanca por Tab. Como o seletor de tema e o ultimo bloco da barra e e um
 * radiogroup rotativo, o `last` calculado deixava de ser o ultimo tabulavel
 * exatamente quando o tema escuro estava ativo.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const MARCACAO = `
  <div data-sidebar>
    <a href="/inicio">Início</a>
    <a href="/oficios">Ofícios</a>
    <div class="sidebar-theme" role="group">
      <div class="app-theme-grid" role="radiogroup">
        <button type="button" data-theme-mode="dark" tabindex="-1">Escuro</button>
        <button type="button" data-theme-mode="light" tabindex="-1">Claro</button>
      </div>
    </div>
  </div>
`;

/** Aplica o tabindex rotativo do jeito que `theme-toggle.js:19` aplica. */
function aplicarTema(tema) {
  document.querySelectorAll("[data-theme-mode]").forEach((btn) => {
    const ativo = btn.getAttribute("data-theme-mode") === tema;
    btn.setAttribute("tabindex", ativo ? "0" : "-1");
  });
}

async function montarSidebar() {
  document.body.innerHTML = MARCACAO;
  document.body.classList.add("has-sidebar-open");
  window.matchMedia = vi.fn().mockReturnValue({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  });
  vi.resetModules();
  await import("./sidebar.js");
  document.dispatchEvent(new Event("DOMContentLoaded"));
}

/** O que o navegador faria: quem realmente recebe foco por Tab. */
function tabulaveis() {
  return Array.from(
    document.querySelectorAll("[data-sidebar] a[href], [data-sidebar] button"),
  ).filter((el) => !el.disabled && el.tabIndex >= 0);
}

function pressionarTab(shift = false) {
  const evento = new KeyboardEvent("keydown", {
    key: "Tab",
    shiftKey: shift,
    bubbles: true,
    cancelable: true,
  });
  document.dispatchEvent(evento);
  return evento;
}

describe("armadilha de foco da gaveta", () => {
  beforeEach(() => {
    document.body.className = "";
    document.body.innerHTML = "";
    localStorage.clear();
  });

  it("no tema ESCURO, o Tab a partir do ultimo tabulavel volta para o primeiro", async () => {
    await montarSidebar();
    aplicarTema("dark");

    const lista = tabulaveis();
    const ultimo = lista[lista.length - 1];
    // no escuro, o ultimo tabulavel e o botao "Escuro" — e nao o "Claro",
    // que e o ultimo do DOM. Era exatamente essa a confusao do defeito.
    expect(ultimo.getAttribute("data-theme-mode")).toBe("dark");

    ultimo.focus();
    const evento = pressionarTab();

    expect(evento.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(lista[0]);
  });

  it("no tema CLARO continua funcionando como antes", async () => {
    await montarSidebar();
    aplicarTema("light");

    const lista = tabulaveis();
    const ultimo = lista[lista.length - 1];
    expect(ultimo.getAttribute("data-theme-mode")).toBe("light");

    ultimo.focus();
    const evento = pressionarTab();

    expect(evento.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(lista[0]);
  });

  it("vale antes de o theme-toggle rodar, com os dois botoes em tabindex -1", async () => {
    // o template nasce assim, e `theme-toggle.js` desiste cedo se CV.theme faltar
    await montarSidebar();

    const lista = tabulaveis();
    expect(lista.every((el) => el.tagName === "A")).toBe(true);

    const ultimo = lista[lista.length - 1];
    ultimo.focus();
    const evento = pressionarTab();

    expect(evento.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(lista[0]);
  });

  it("Shift+Tab a partir do primeiro vai para o ultimo TABULAVEL, nao para o ultimo do DOM", async () => {
    await montarSidebar();
    aplicarTema("dark");

    const lista = tabulaveis();
    lista[0].focus();
    const evento = pressionarTab(true);

    expect(evento.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(lista[lista.length - 1]);
    expect(document.activeElement.getAttribute("data-theme-mode")).toBe("dark");
  });

  it("botao desabilitado nao entra na conta", async () => {
    await montarSidebar();
    aplicarTema("dark");
    const extra = document.createElement("button");
    extra.disabled = true;
    document.querySelector("[data-sidebar]").appendChild(extra);

    const lista = tabulaveis();
    lista[lista.length - 1].focus();
    const evento = pressionarTab();

    expect(evento.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(lista[0]);
  });
});
