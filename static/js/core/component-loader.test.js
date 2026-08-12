import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const source = readFileSync(resolve("static/js/core/component-loader.js"), "utf8");

describe("CV.lazyComponents", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <script
        data-cv-lazy-components
        data-cv-lazy-card-toggle-src="/static/card-toggle.js"
        data-cv-lazy-file-picker-src="/static/file-picker.js"
        data-cv-lazy-form-components-src="/static/form-components.bundle.js"
      ></script>
      <div data-card-toggle></div>
    `;
    window.CV = {};
  });

  afterEach(() => {
    if (window.CV.lazyComponents) window.CV.lazyComponents.destroy();
  });

  it("carrega somente o componente cujo marcador existe e apenas uma vez", () => {
    const appended = [];
    vi.spyOn(document.head, "appendChild").mockImplementation((node) => {
      appended.push(node.src);
      return node;
    });

    window.eval(source);
    window.CV.lazyComponents.scan(document);

    expect(appended).toEqual(["http://localhost:3000/static/card-toggle.js"]);
  });

  it("observa conteúdo inserido depois do shell", async () => {
    const appended = [];
    vi.spyOn(document.head, "appendChild").mockImplementation((node) => {
      appended.push(node.src);
      return node;
    });

    window.eval(source);
    const picker = document.createElement("div");
    picker.dataset.filePicker = "";
    document.body.appendChild(picker);
    await new Promise((resolvePromise) => window.setTimeout(resolvePromise, 0));

    expect(appended).toContain("http://localhost:3000/static/file-picker.js");
  });
  it("carrega o bundle de formularios quando um picker aparece", () => {
    document.body.insertAdjacentHTML(
      "beforeend",
      '<select data-entity-picker><option value="">Escolha</option></select>',
    );
    const appended = [];
    vi.spyOn(document.head, "appendChild").mockImplementation((node) => {
      appended.push(node.src);
      return node;
    });

    window.eval(source);

    expect(appended).toContain("http://localhost:3000/static/form-components.bundle.js");
  });

  it("nao requisita o bundle ja declarado pelo template", () => {
    document.body.insertAdjacentHTML(
      "beforeend",
      '<script data-cv-component-bundle="forms" src="/static/form-components.bundle.js"></script>',
    );
    const picker = document.createElement("div");
    picker.dataset.cvDatePicker = "";
    document.body.appendChild(picker);
    const appended = [];
    vi.spyOn(document.head, "appendChild").mockImplementation((node) => {
      appended.push(node.src);
      return node;
    });

    window.eval(source);

    expect(appended).not.toContain("http://localhost:3000/static/form-components.bundle.js");
  });

  it("carrega o seletor de arquivo antes do modal que depende dele", () => {
    const config = document.querySelector("[data-cv-lazy-components]");
    config.dataset.cvLazyAttachSignedModalSrc = "/static/attach-signed-modal.js";
    document.body.insertAdjacentHTML(
      "beforeend",
      '<div data-file-picker></div><div data-attach-signed-modal></div>',
    );
    const appended = [];
    vi.spyOn(document.head, "appendChild").mockImplementation((node) => {
      appended.push(node.src);
      return node;
    });

    window.eval(source);

    expect(appended).toEqual([
      "http://localhost:3000/static/card-toggle.js",
      "http://localhost:3000/static/file-picker.js",
      "http://localhost:3000/static/attach-signed-modal.js",
    ]);
  });
});
