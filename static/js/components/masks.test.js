import { beforeEach, describe, expect, it, vi } from "vitest";

window.CV = { registerEnhancer: vi.fn() };
await import("./masks.js");
const registration = window.CV.registerEnhancer.mock.calls[0];

describe("CV.masks", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("se registra no coordenador global", () => {
    expect(registration).toEqual(["masks", window.CV.masks.scan]);
  });

  it.each([
    ["cpf", "12345678901", "123.456.789-01"],
    ["rg", "12345678X", "12.345.678-X"],
    ["placa", "abc-1d23", "ABC1D23"],
    ["cep", "70040900", "70040-900"],
    ["date", "2026-08-09", "09/08/2026"],
    ["date", "09082026", "09/08/2026"],
    ["time", "0930", "09:30"],
    ["telefone", "61987654321", "(61) 98765-4321"],
    ["telefone", "6133334444", "(61) 3333-4444"],
    ["protocolo", "123456789", "12.345.678-9"],
    ["milhar", "001234567", "1.234.567"],
    ["upper", "ação 12", "AÇÃO 12"],
    ["inexistente", 123, "123"],
  ])("formata %s", (mask, value, expected) => {
    expect(window.CV.masks.format(value, mask)).toBe(expected);
  });

  it("cobre formatos parciais sem fabricar separadores finais", () => {
    expect(window.CV.masks.format("12", "cpf")).toBe("12");
    expect(window.CV.masks.format("1234", "cpf")).toBe("123.4");
    expect(window.CV.masks.format("1234567", "cpf")).toBe("123.456.7");
    expect(window.CV.masks.format("1", "rg")).toBe("1");
    expect(window.CV.masks.format("123", "rg")).toBe("1.23");
    expect(window.CV.masks.format("123456", "rg")).toBe("1.234.56");
    expect(window.CV.masks.format("12345678", "rg")).toBe("1.234.567-8");
    expect(window.CV.masks.format("123", "cep")).toBe("123");
    expect(window.CV.masks.format("1", "date")).toBe("1");
    expect(window.CV.masks.format("123", "date")).toBe("12/3");
    expect(window.CV.masks.format("1", "time")).toBe("1");
    expect(window.CV.masks.format("1", "protocolo")).toBe("1");
    expect(window.CV.masks.format("1234", "protocolo")).toBe("12.34");
    expect(window.CV.masks.format("123456", "protocolo")).toBe("12.345.6");
    expect(window.CV.masks.format("1", "telefone")).toBe("(1");
    expect(window.CV.masks.format("1234", "telefone")).toBe("(12) 34");
    expect(window.CV.masks.format("", "milhar")).toBe("");
    expect(window.CV.masks.onlyDigits("CPF 123.4")).toBe("1234");
  });

  it("aplica e vincula mascaras uma unica vez em DOM dinamico", () => {
    document.body.innerHTML = `
      <section id="scope">
        <input id="cpf" data-mask="cpf" value="12345678901">
        <textarea id="upper" data-mask="upper">texto</textarea>
        <input id="disabled" data-mask="cpf" value="123" disabled>
      </section>`;
    const scope = document.querySelector("#scope");

    window.CV.masks.scan(scope);
    window.CV.masks.scan(scope);

    const cpf = document.querySelector("#cpf");
    expect(cpf.value).toBe("123.456.789-01");
    expect(cpf.getAttribute("data-mask-bound")).toBe("true");
    expect(document.querySelector("#upper").value).toBe("TEXTO");
    expect(document.querySelector("#disabled").getAttribute("data-mask-bound")).toBeNull();

    cpf.value = "98765432100";
    cpf.dispatchEvent(new Event("input"));
    expect(cpf.value).toBe("987.654.321-00");
  });

  it("aceita como raiz o proprio campo e ignora alvos nao editaveis", () => {
    const input = document.createElement("input");
    input.dataset.mask = "cep";
    input.value = "70040900";
    window.CV.masks.scan(input);
    expect(input.value).toBe("70040-900");

    const readonly = document.createElement("input");
    readonly.dataset.mask = "cpf";
    readonly.readOnly = true;
    window.CV.masks.apply(readonly);
    window.CV.masks.apply(null);
    expect(readonly.value).toBe("");
  });
});
