import { beforeEach, describe, expect, it, vi } from "vitest";

const registerEnhancer = vi.fn();
window.CV = { registerEnhancer };
await import("./state-toggle.js");
const registration = registerEnhancer.mock.calls[0];

describe("CV.stateToggle", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("se registra no coordenador global", () => {
    expect(registration).toEqual(["stateToggle", window.CV.stateToggle.init]);
  });

  it("opera o toggle binario pelo contrato canonico e uma unica vez", () => {
    document.body.innerHTML = `
      <div data-cv-state-toggle data-cv-state-binary
           data-cv-state-input="#state-input"
           data-active-label="Ativo" data-inactive-label="Inativo">
        <input id="state-input" type="hidden" value="false">
        <button type="button" data-cv-state-trigger><span>Inativo</span></button>
      </div>`;
    const group = document.querySelector("[data-cv-state-toggle]");
    const input = document.querySelector("#state-input");
    const trigger = document.querySelector("[data-cv-state-trigger]");
    const changed = vi.fn();
    group.addEventListener("cv:state-toggle:change", changed);

    window.CV.stateToggle.init(document);
    window.CV.stateToggle.init(document);
    trigger.click();

    expect(group.getAttribute("data-cv-state-bound")).toBe("true");
    expect(input.value).toBe("true");
    expect(trigger.getAttribute("aria-pressed")).toBe("true");
    expect(trigger.classList.contains("is-active")).toBe(true);
    expect(trigger.querySelector("span").textContent).toBe("Ativo");
    expect(changed.mock.calls.at(-1)[0].detail).toMatchObject({
      fromUser: true,
      input,
      toggle: group,
      value: "true",
    });
  });
});
