import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const source = readFileSync(resolve("static/js/components/overlay.js"), "utf8");

describe("CV.overlay.attachDismiss", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="test-root"><button>abrir</button></div>
      <div class="test-panel"><button>opcao</button></div>
      <button class="test-outside">fora</button>
    `;
    window.CV = { registerEnhancer: vi.fn() };
    window.eval(source);
  });

  it("fecha por clique fora e preserva raiz e painel portalizado", () => {
    const root = document.querySelector(".test-root");
    const panel = document.querySelector(".test-panel");
    const onDismiss = vi.fn();
    const binding = window.CV.overlay.attachDismiss({
      inside: [root, panel],
      isOpen: () => true,
      onDismiss,
    });

    root.querySelector("button").click();
    panel.querySelector("button").click();
    expect(onDismiss).not.toHaveBeenCalled();

    document.querySelector(".test-outside").click();
    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss.mock.calls[0][0]).toBe("outside");

    binding.destroy();
    document.querySelector(".test-outside").click();
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("fecha por Escape apenas quando o consumidor autoriza", () => {
    const root = document.querySelector(".test-root");
    const onDismiss = vi.fn();
    window.CV.overlay.attachDismiss({
      inside: [root],
      isOpen: () => true,
      escapeWhen: (event) => root.contains(event.target),
      onDismiss,
    });

    const outsideEvent = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    document.querySelector(".test-outside").dispatchEvent(outsideEvent);
    expect(onDismiss).not.toHaveBeenCalled();

    const insideEvent = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    root.querySelector("button").dispatchEvent(insideEvent);
    expect(insideEvent.defaultPrevented).toBe(true);
    expect(onDismiss).toHaveBeenCalledWith("escape", insideEvent);
  });
});
