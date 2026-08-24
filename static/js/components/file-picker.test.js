import { beforeEach, describe, expect, it, vi } from "vitest";

/* O picker com o botão de anexar FORA dele — a forma que o modal de anexar
   assinado usa: o `<button data-file-upload-button form="…">` mora no rodapé do
   diálogo, ligado ao formulário por `form=`. É o arranjo em que `setBusy`
   quebrava (`NOVO-20260824-133423-dd2bc58e8a2b`). */

const registerEnhancer = vi.fn();
window.CV = { registerEnhancer };

await import("./file-picker.js");
const [, init] = registerEnhancer.mock.calls[0];

function montar() {
  document.body.innerHTML = `
    <form id="form-anexo">
      <div data-file-picker>
        <input type="file" id="arquivo" name="arquivo" data-file-native="true">
        <span data-file-picker-action-label>Escolher PDF</span>
        <strong data-file-picker-name data-default-label="Nenhum documento escolhido">Nenhum documento escolhido</strong>
        <span data-file-inline-actions hidden></span>
        <span class="sr-only" id="arquivo-status" data-file-picker-status></span>
        <div data-file-selection-dropdown hidden>
          <button type="button" data-file-selection-toggle aria-expanded="false">
            <span data-file-selection-summary></span>
          </button>
          <div data-file-selection-menu hidden>
            <ul data-file-selection-list></ul>
          </div>
        </div>
        <template data-file-selection-template>
          <li data-file-selection-row>
            <strong data-file-selection-name></strong>
            <small data-file-selection-size></small>
            <a data-file-preview-selection></a>
            <button type="button" data-file-remove-selection></button>
          </li>
        </template>
      </div>
    </form>
    <button type="submit" form="form-anexo" data-file-upload-button disabled>Anexar PDF</button>`;
  init(document);
  const input = document.querySelector("#arquivo");
  ligarValueAosArquivos(input);
  return {
    form: document.querySelector("#form-anexo"),
    input,
    botao: document.querySelector("[data-file-upload-button]"),
  };
}

function definirArquivos(input, files) {
  Object.defineProperty(input, "files", { configurable: true, value: files });
}

/* No navegador, `input.value = ""` esvazia `input.files` — é assim que
   `replaceFiles` limpa a seleção. O jsdom não liga as duas coisas, e sem esta
   ponte o teste de limpar mediria uma seleção que continuava lá. */
function ligarValueAosArquivos(input) {
  let valor = "";
  Object.defineProperty(input, "value", {
    configurable: true,
    get: () => valor,
    set: (novo) => {
      valor = novo;
      if (!novo) definirArquivos(input, []);
    },
  });
  definirArquivos(input, []);
}

function escolher(input, nome) {
  const file = new File([nome], nome, { type: "application/pdf" });
  definirArquivos(input, [file]);
  input.dispatchEvent(new Event("change", { bubbles: true }));
  return file;
}

describe("file picker com botão de anexar fora do picker", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    globalThis.URL.createObjectURL = vi.fn(() => "blob:teste");
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  it("habilita o botão ligado por form= quando há arquivo escolhido", () => {
    const { input, botao } = montar();
    expect(botao.disabled).toBe(true);

    escolher(input, "oficio.pdf");

    expect(botao.disabled).toBe(false);
    expect(document.querySelector("[data-file-picker-name]").textContent).toBe("oficio.pdf");
  });

  it("marca o picker como ocupado no submit sem quebrar", () => {
    const { form, input, botao } = montar();
    escolher(input, "oficio.pdf");

    const erros = [];
    window.addEventListener("error", (evento) => erros.push(evento.error));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    // `setBusy` lia um `input` que não existia no seu escopo: todo submit deste
    // arranjo estourava `ReferenceError` e o picker nunca entrava em `is-busy`.
    expect(erros).toEqual([]);
    expect(document.querySelector("[data-file-picker]").classList.contains("is-busy")).toBe(true);
    expect(document.querySelector("[data-file-picker]").getAttribute("aria-busy")).toBe("true");
    expect(botao.disabled).toBe(true);
  });

  it("volta o botão a desabilitado quando a seleção é limpa", () => {
    const { input, botao } = montar();
    escolher(input, "oficio.pdf");

    window.CV.filePicker.replaceFiles(input, [], true);

    expect(botao.disabled).toBe(true);
  });
});
