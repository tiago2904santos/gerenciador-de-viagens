import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

await import("./server-filter.js");

describe("filtros automáticos das listagens", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.sessionStorage.clear();
    document.body.innerHTML = `
      <form data-server-filter-form>
        <input name="q" data-server-filter-search>
        <select data-server-filter-control></select>
      </form>`;
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("envia após 1000 ms sem digitação", () => {
    const form = document.querySelector("form");
    const search = form.querySelector("input");
    form.requestSubmit = vi.fn();

    window.CV.serverFilter.init(document);
    search.dispatchEvent(new Event("input", { bubbles: true }));

    vi.advanceTimersByTime(999);
    expect(form.requestSubmit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(form.requestSubmit).toHaveBeenCalledOnce();
  });

  it("reinicia a espera quando a pessoa continua digitando", () => {
    const form = document.querySelector("form");
    const search = form.querySelector("input");
    form.requestSubmit = vi.fn();

    window.CV.serverFilter.init(document);
    search.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(700);
    search.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(999);

    expect(form.requestSubmit).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(form.requestSubmit).toHaveBeenCalledOnce();
  });

  it("restaura foco e cursor depois da navegação", () => {
    const search = document.querySelector("input");
    search.value = "ademar";
    const key = "cv:server-filter:focus:" + window.location.pathname + ":q";
    window.sessionStorage.setItem(key, "true");

    window.CV.serverFilter.init(document);

    expect(document.activeElement).toBe(search);
    expect(search.selectionStart).toBe(search.value.length);
  });
});
