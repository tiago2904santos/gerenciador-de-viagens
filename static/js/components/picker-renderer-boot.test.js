import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const appSource = readFileSync(resolve("static/js/core/app.js"), "utf8");
const fieldsSource = readFileSync(resolve("static/js/components/fields-init.js"), "utf8");
const pickerSource = readFileSync(resolve("static/js/components/picker.js"), "utf8");
const selectSource = readFileSync(resolve("static/js/components/picker-select.js"), "utf8");

describe("picker select renderer boot", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <label for="id_tipos">Tipo do evento</label>
      <div data-entity-picker data-entity-picker-renderer="select" data-entity-picker-mode="multi">
        <select id="id_tipos" name="tipos" multiple>
          <option value="1">PCPR na Comunidade</option>
          <option value="2">Operacao Policial</option>
        </select>
      </div>
    `;
    window.CV = {};
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("aplica renderer carregado depois do primeiro passe do shell", () => {
    vi.spyOn(document, "readyState", "get").mockReturnValue("interactive");

    window.eval(appSource);
    window.CV.overlay = {
      attachDismiss: () => ({ destroy() {} }),
      attachDropdown: () => null,
    };

    // Ordem real: fields-init esta no shell; picker e renderer chegam depois.
    window.eval(fieldsSource);
    window.eval(pickerSource);
    expect(document.querySelector(".custom-select__trigger")).toBeNull();

    window.eval(selectSource);

    const native = document.querySelector("select[multiple]");
    expect(native.classList.contains("custom-select__native")).toBe(true);
    expect(native.getAttribute("aria-hidden")).toBe("true");
    expect(document.querySelectorAll(".custom-select__trigger")).toHaveLength(1);
    expect(document.querySelector('[role="listbox"]')).not.toBeNull();
  });
});
