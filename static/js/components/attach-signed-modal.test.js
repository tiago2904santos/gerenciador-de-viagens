import { beforeEach, describe, expect, it, vi } from "vitest";

const registerEnhancer = vi.fn();
const httpRequest = vi.fn();

function replaceFiles(input, files, dispatchChange) {
  Object.defineProperty(input, "files", {
    configurable: true,
    value: files,
  });
  if (dispatchChange) input.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

window.CV = {
  registerEnhancer,
  documentProgress: { begin: vi.fn() },
  filePicker: { replaceFiles },
  http: { request: httpRequest },
  log: { error: vi.fn() },
  overlay: {
    closeDialog(modal) { modal.hidden = true; },
    openDialog(modal) { modal.hidden = false; },
  },
};

await import("./attach-signed-modal.js");
const registration = registerEnhancer.mock.calls[0];

function montarModal() {
  document.body.innerHTML = `
    <button type="button" id="abrir" data-attach-signed-trigger></button>
    <dialog data-attach-signed-modal hidden>
      <div class="modal__shell"></div>
      <form id="attach-signed-form" data-attach-signed-form>
        <input type="hidden" name="csrfmiddlewaretoken" value="csrf">
        <input type="hidden" name="next" data-attach-signed-next>
        <span data-attach-signed-label></span>
        <span data-attach-signed-file-description></span>
        <span data-attach-signed-file-help></span>
        <div data-attach-signed-kind-selector hidden>
          <div data-attach-signed-kind-options></div>
        </div>
        <div data-file-picker>
          <input type="file">
          <span data-file-picker-action-label></span>
          <span data-attach-signed-current-name data-default-label="Nenhum arquivo selecionado"></span>
          <small data-attach-signed-current-meta hidden></small>
          <span data-attach-signed-current hidden></span>
          <a data-attach-signed-current-open></a>
        </div>
        <p data-attach-signed-error hidden></p>
        <button type="submit" data-file-upload-button disabled></button>
      </form>
    </dialog>`;

  const kinds = [
    { key: "oficio", option_label: "Ofício assinado", doc_label: "o ofício", url: "/oficio/" },
    { key: "despacho", option_label: "Despacho", doc_label: "o despacho", url: "/despacho/" },
    { key: "relatorio", option_label: "Relatório técnico", doc_label: "o relatório", url: "/relatorio/" },
  ];
  const trigger = document.querySelector("#abrir");
  trigger.setAttribute("data-attach-signed-kinds", JSON.stringify(kinds));
  trigger.setAttribute("data-attach-signed-upload-label", "Anexar arquivos");
  return { trigger, kinds };
}

function selecionarArquivo(nome) {
  const picker = document.querySelector("[data-file-picker]");
  const input = picker.querySelector('input[type="file"]');
  const file = new File([nome], nome, { type: "application/pdf" });
  replaceFiles(input, [file], false);
  picker.dispatchEvent(new CustomEvent("cv:file-picker:change", {
    bubbles: true,
    detail: { files: [file], input },
  }));
  return file;
}

describe("modal de anexos assinados", () => {
  beforeEach(() => {
    if (registration && registration[2]) registration[2](document);
    document.body.innerHTML = "";
    httpRequest.mockReset();
    window.CV.log.error.mockClear();
    window.CV.documentProgress.begin.mockClear();
  });

  it("mantém um arquivo por aba e envia todas as escolhas em uma única ação", async () => {
    const { trigger } = montarModal();
    registration[1](document);
    trigger.click();

    selecionarArquivo("oficio.pdf");
    document.querySelector('[data-attach-signed-kind="despacho"]').click();
    selecionarArquivo("despacho.pdf");
    document.querySelector('[data-attach-signed-kind="relatorio"]').click();
    selecionarArquivo("relatorio.pdf");

    expect(
      Array.from(document.querySelectorAll("[data-attach-signed-kind-status]"))
        .every((status) => !status.hidden)
    ).toBe(true);
    expect(document.querySelector("[data-file-upload-button]").textContent).toBe("Anexar arquivos");

    httpRequest
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce({ ok: false, status: 422 });

    document.querySelector("[data-attach-signed-form]").dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true })
    );

    await vi.waitFor(() => expect(httpRequest).toHaveBeenCalledTimes(3));
    expect(httpRequest.mock.calls.map((call) => call[0])).toEqual([
      "/oficio/",
      "/despacho/",
      "/relatorio/",
    ]);
    expect(httpRequest.mock.calls.map((call) => call[1].body.get("arquivo").name)).toEqual([
      "oficio.pdf",
      "despacho.pdf",
      "relatorio.pdf",
    ]);
    await vi.waitFor(() => {
      expect(document.querySelector("[data-attach-signed-error]").textContent).toContain(
        "2 de 3 arquivo(s) foram anexados"
      );
    });
  });

  it("restaura no seletor o arquivo da aba ao voltar para ela", () => {
    const { trigger } = montarModal();
    registration[1](document);
    trigger.click();

    selecionarArquivo("oficio.pdf");
    document.querySelector('[data-attach-signed-kind="despacho"]').click();
    selecionarArquivo("despacho.pdf");
    document.querySelector('[data-attach-signed-kind="oficio"]').click();

    expect(document.querySelector('input[type="file"]').files[0].name).toBe("oficio.pdf");
    expect(document.querySelector("[data-file-upload-button]").disabled).toBe(false);
  });
});
