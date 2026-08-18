/* O quick add do `app.js`: quando o botão de rodapé salva e quando só recolhe.
 *
 * Vive num arquivo próprio porque `app.test.js` compartilha um `document` entre
 * os testes do registry, e o enhancer aqui prende estado no par
 * gatilho/painel — um painel deixado aberto por um teste mudaria o seguinte.
 *
 * O que se prova é `painelPreenchido` (`app.js:404`), que decide se um cadastro
 * incompleto vira POST. Antes dela bastava o PRIMEIRO campo ter valor: o botão
 * prometia "Salvar", o servidor recusava no `clean()` e quem estava cadastrando
 * descobria o que faltava depois de tentar. Ela entrou sem teste em `363461d`,
 * e a queda de cobertura passou despercebida porque dois testes vermelhos
 * abortavam a suíte antes do verificador de piso.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

await import("./app.js");

function montar(corpo, { submitWhenOpen = true } = {}) {
  document.body.innerHTML = `
    <form id="qa-panel" data-create-action="/criar/" hidden>${corpo}</form>
    <button
      data-inline-create-toggle
      ${submitWhenOpen ? "data-inline-create-submit-when-open" : ""}
      data-inline-create-save-label="Salvar cargo"
      aria-controls="qa-panel"
      aria-expanded="false"
    ><span class="inline-create__toggle-label">Cadastrar cargo</span></button>
  `;
  const panel = document.getElementById("qa-panel");
  const toggle = document.querySelector("[data-inline-create-toggle]");
  panel.requestSubmit = vi.fn();
  window.CV.registry.enhance(document.body);
  return { panel, toggle, rotulo: toggle.querySelector(".inline-create__toggle-label") };
}

function digitar(campo, valor) {
  campo.value = valor;
  campo.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("quick add: o botão só salva com o painel preenchido", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("com campos obrigatórios, um deles vazio recolhe em vez de enviar", () => {
    const { panel, toggle, rotulo } = montar(`
      <input name="nome" required>
      <input name="sigla" required>
    `);

    toggle.click();
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    digitar(panel.querySelector('[name="nome"]'), "Investigador");
    expect(toggle.classList.contains("is-filled")).toBe(false);
    expect(rotulo.textContent).toBe("Cadastrar cargo");

    toggle.click();
    expect(panel.requestSubmit).not.toHaveBeenCalled();
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("com todos os obrigatórios preenchidos, o botão vira Salvar e envia", () => {
    const { panel, toggle, rotulo } = montar(`
      <input name="nome" required>
      <input name="sigla" required>
    `);

    toggle.click();
    digitar(panel.querySelector('[name="nome"]'), "Investigador");
    digitar(panel.querySelector('[name="sigla"]'), "INV");

    expect(toggle.classList.contains("is-filled")).toBe(true);
    expect(rotulo.textContent).toBe("Salvar cargo");

    toggle.click();
    expect(panel.requestSubmit).toHaveBeenCalledOnce();
  });

  it("um campo opcional em branco não impede o envio", () => {
    const { panel, toggle } = montar(`
      <input name="nome" required>
      <input name="observacao">
    `);

    toggle.click();
    digitar(panel.querySelector('[name="nome"]'), "Investigador");

    expect(toggle.classList.contains("is-filled")).toBe(true);
    toggle.click();
    expect(panel.requestSubmit).toHaveBeenCalledOnce();
  });

  it("sem nenhum `required`, conta o conjunto visível", () => {
    // É o caso dos cadastros de uma palavra, que não declaram obrigatoriedade
    // no HTML: exigir `required` ali faria o botão nunca prometer salvar.
    const { panel, toggle } = montar(`
      <input name="nome">
      <input name="sigla">
    `);

    toggle.click();
    digitar(panel.querySelector('[name="nome"]'), "Investigador");
    expect(toggle.classList.contains("is-filled")).toBe(false);

    digitar(panel.querySelector('[name="sigla"]'), "INV");
    expect(toggle.classList.contains("is-filled")).toBe(true);
  });

  it("campo oculto e botão não contam, e caixa de seleção conta por marcada", () => {
    const { panel, toggle } = montar(`
      <input type="hidden" name="csrf" value="">
      <input type="submit" value="">
      <input type="button" value="">
      <input name="nome">
      <input type="checkbox" name="ativo">
    `);

    toggle.click();
    digitar(panel.querySelector('[name="nome"]'), "Investigador");
    expect(toggle.classList.contains("is-filled")).toBe(false);

    const caixa = panel.querySelector('[name="ativo"]');
    caixa.checked = true;
    caixa.dispatchEvent(new Event("input", { bubbles: true }));
    expect(toggle.classList.contains("is-filled")).toBe(true);
  });

  it("painel sem campo nenhum nunca conta como preenchido", () => {
    const { panel, toggle } = montar(`<p>Nada a preencher.</p>`);

    toggle.click();
    panel.dispatchEvent(new Event("input", { bubbles: true }));
    expect(toggle.classList.contains("is-filled")).toBe(false);

    toggle.click();
    expect(panel.requestSubmit).not.toHaveBeenCalled();
  });

  it("recolher devolve o rótulo original e limpa os campos", () => {
    const { panel, toggle, rotulo } = montar(`<input name="nome" required>`);

    toggle.click();
    digitar(panel.querySelector('[name="nome"]'), "Investigador");
    expect(rotulo.textContent).toBe("Salvar cargo");

    panel.querySelector('[name="nome"]').value = "";
    panel.dispatchEvent(new Event("input", { bubbles: true }));
    toggle.click();

    expect(panel.requestSubmit).not.toHaveBeenCalled();
    expect(rotulo.textContent).toBe("Cadastrar cargo");
    expect(toggle.classList.contains("is-filled")).toBe(false);
    expect(panel.querySelector('[name="nome"]').value).toBe("");
  });
});
