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
          <span data-attach-signed-current hidden>
            <button type="button" data-attach-signed-remove>Excluir</button>
          </span>
          <a data-attach-signed-current-open></a>
          <ul data-attach-signed-current-list hidden></ul>
          <template data-attach-signed-current-template>
            <li data-attach-signed-current-row>
              <strong data-attach-signed-list-name></strong>
              <a data-attach-signed-list-open></a>
              <button type="button" data-attach-signed-remove>Excluir</button>
            </li>
          </template>
        </div>
        <p data-attach-signed-error hidden></p>
        <button type="submit" data-file-upload-button disabled></button>
      </form>
    </dialog>`;

  const kinds = [
    { key: "oficio", option_label: "Ofício assinado", doc_label: "o ofício", url: "/oficio/" },
    {
      key: "despacho",
      option_label: "Despacho",
      doc_label: "o despacho",
      url: "/despacho/",
      current_name: "despacho-assinado.pdf",
      current_view_url: "/despacho/abrir/",
      current_remove_url: "/despacho/excluir/",
      current_attachments: [{
        name: "despacho-assinado.pdf",
        view_url: "/despacho/abrir/",
        remove_url: "/despacho/excluir/",
      }],
    },
    { key: "relatorio", option_label: "Relatório técnico", doc_label: "o relatório", url: "/relatorio/" },
  ];
  const trigger = document.querySelector("#abrir");
  trigger.setAttribute("data-attach-signed-kinds", JSON.stringify(kinds));
  trigger.setAttribute("data-attach-signed-upload-label", "Anexar arquivos");
  return { trigger, kinds };
}

function selecionarArquivos(...nomes) {
  const picker = document.querySelector("[data-file-picker]");
  const input = picker.querySelector('input[type="file"]');
  const files = nomes.map((nome) => new File([nome], nome, { type: "application/pdf" }));
  replaceFiles(input, files, false);
  picker.dispatchEvent(new CustomEvent("cv:file-picker:change", {
    bubbles: true,
    detail: { files, input },
  }));
  return files;
}

describe("modal de anexos assinados", () => {
  beforeEach(() => {
    if (registration && registration[2]) registration[2](document);
    document.body.innerHTML = "";
    httpRequest.mockReset();
    window.CV.log.error.mockClear();
    window.CV.documentProgress.begin.mockClear();
  });

  it("mantém vários arquivos por aba e envia todas as escolhas em uma única ação", async () => {
    const { trigger } = montarModal();
    registration[1](document);
    trigger.click();

    selecionarArquivos("oficio.pdf", "oficio-anexo.png");
    document.querySelector('[data-attach-signed-kind="despacho"]').click();
    selecionarArquivos("despacho.pdf");
    document.querySelector('[data-attach-signed-kind="relatorio"]').click();
    selecionarArquivos("relatorio.pdf");

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
    expect(httpRequest.mock.calls.map((call) => call[1].body.getAll("arquivo").map((f) => f.name))).toEqual([
      ["oficio.pdf", "oficio-anexo.png"],
      ["despacho.pdf"],
      ["relatorio.pdf"],
    ]);
    expect(httpRequest.mock.calls[0][1].body.getAll("arquivo").map((f) => f.name)).toEqual([
      "oficio.pdf",
      "oficio-anexo.png",
    ]);
    await vi.waitFor(() => {
      expect(document.querySelector("[data-attach-signed-error]").textContent).toContain(
        "3 de 4 arquivo(s) foram anexados"
      );
    });
  });

  it("mostra o motivo que o servidor deu para recusar o arquivo", async () => {
    const { trigger } = montarModal();
    registration[1](document);
    trigger.click();

    selecionarArquivos("oficio.pdf");
    document.querySelector('[data-attach-signed-kind="despacho"]').click();
    selecionarArquivos("despacho.pdf");

    httpRequest.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: () => Promise.resolve({
        ok: false,
        error: "O conteúdo não corresponde a um PDF válido.",
      }),
    });

    document.querySelector("[data-attach-signed-form]").dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true })
    );

    await vi.waitFor(() => {
      expect(document.querySelector("[data-attach-signed-error]").textContent).toContain(
        "O conteúdo não corresponde a um PDF válido."
      );
    });
    // O número do status não substitui o motivo: era só isso que a faixa dizia.
    expect(document.querySelector("[data-attach-signed-error]").textContent).not.toContain(
      "HTTP 400"
    );
  });

  it("restaura no seletor o arquivo da aba ao voltar para ela", () => {
    const { trigger } = montarModal();
    registration[1](document);
    trigger.click();

    selecionarArquivos("oficio.pdf", "oficio-2.pdf");
    document.querySelector('[data-attach-signed-kind="despacho"]').click();
    selecionarArquivos("despacho.pdf");
    document.querySelector('[data-attach-signed-kind="oficio"]').click();

    expect(Array.from(document.querySelector('input[type="file"]').files).map((f) => f.name))
      .toEqual(["oficio.pdf", "oficio-2.pdf"]);
    expect(document.querySelector("[data-file-upload-button]").disabled).toBe(false);
  });

  it("mantém o modal aberto e pronto para substituir o anexo excluído", async () => {
    const { trigger } = montarModal();
    registration[1](document);
    trigger.click();
    document.querySelector('[data-attach-signed-kind="despacho"]').click();

    expect(document.querySelector("[data-attach-signed-list-name]").textContent)
      .toBe("despacho-assinado.pdf");
    expect(document.querySelector("[data-attach-signed-current-list]").hidden).toBe(false);
    httpRequest.mockResolvedValueOnce({ ok: true, status: 200 });

    document.querySelector("[data-attach-signed-current-list] [data-attach-signed-remove]").click();

    await vi.waitFor(() => expect(httpRequest).toHaveBeenCalledTimes(1));
    expect(document.querySelector("[data-attach-signed-modal]").hidden).toBe(false);
    expect(document.querySelector("[data-attach-signed-current-name]").textContent)
      .toBe("Nenhum arquivo selecionado");
    expect(document.querySelector("[data-attach-signed-current-list]").hidden).toBe(true);
    expect(document.querySelector("[data-file-upload-button]").disabled).toBe(true);

    const tiposAtualizados = JSON.parse(
      trigger.getAttribute("data-attach-signed-kinds")
    );
    const despacho = tiposAtualizados.find((item) => item.key === "despacho");
    expect(despacho.current_name).toBe("");
    expect(despacho.current_remove_url).toBe("");
    expect(despacho.current_attachments).toEqual([]);
  });
});
