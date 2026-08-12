import { describe, expect, it, vi } from "vitest";

await import("./app.js");

describe("CV registry", () => {
  it("publica utilitarios e ignora registros invalidos", () => {
    expect(document.documentElement.dataset.appReady).toBe("true");
    expect(window.CV.util.normalize("AÇÃO")).toBe("acao");
    expect(window.CV.util.escapeHtml('<a href="x">&')).toBe("&lt;a href=&quot;x&quot;&gt;&amp;");
    const before = window.CV.registry.registered();
    window.CV.registry.register("", vi.fn());
    window.CV.registry.register("sem-funcao", null);
    expect(window.CV.registry.registered()).toEqual(before);
  });

  it("registra, inicializa e substitui um enhancer pelo nome", () => {
    const first = vi.fn();
    const second = vi.fn();
    window.CV.registry.register("teste-registro", first);
    window.CV.registry.enhance(document.body);
    expect(first).toHaveBeenCalledWith(document.body);

    window.CV.registry.register("teste-registro", second);
    window.CV.registry.enhance(document.body);
    expect(second).toHaveBeenCalledWith(document.body);
    expect(window.CV.registry.registered().filter((name) => name === "teste-registro")).toHaveLength(1);
  });

  it("executa destroy apenas para raizes validas e captura falhas", () => {
    const destroy = vi.fn();
    const errors = [];
    document.addEventListener("cv:enhancer-error", (event) => errors.push(event.detail));
    window.CV.registry.register("com-destroy", vi.fn(), destroy);
    window.CV.registry.register("destroy-quebra", vi.fn(), () => { throw new Error("falhou"); });

    const root = document.createElement("section");
    window.CV.registry.destroy(root);
    window.CV.registry.destroy(document.createTextNode("texto"));
    window.CV.registry.destroy(null);

    expect(destroy).toHaveBeenCalledOnce();
    expect(destroy).toHaveBeenCalledWith(root);
    expect(errors).toContainEqual({ name: "destroy-quebra", phase: "destroy", message: "falhou" });
  });

  it("isola falha de inicializacao e continua os outros enhancers", () => {
    const healthy = vi.fn();
    const errors = [];
    document.addEventListener("cv:enhancer-error", (event) => errors.push(event.detail));
    window.CV.registry.register("init-quebra", () => { throw new Error("inicializacao falhou"); });
    window.CV.registry.register("init-saudavel", healthy);

    window.CV.enhance(document.body);

    expect(healthy).toHaveBeenCalledWith(document.body);
    expect(errors).toContainEqual({ name: "init-quebra", message: "inicializacao falhou" });
  });

  it("aplica enhancer em nos inseridos e destroy nos removidos", async () => {
    const init = vi.fn();
    const destroy = vi.fn();
    window.CV.registry.register("dom-dinamico", init, destroy);
    init.mockClear();

    const root = document.createElement("section");
    document.body.append(root);
    await new Promise((resolve) => window.queueMicrotask(resolve));
    expect(init).toHaveBeenCalledWith(root);

    root.remove();
    await new Promise((resolve) => window.queueMicrotask(resolve));
    expect(destroy).toHaveBeenCalledWith(root);
  });

  it("debounce conserva contexto e argumentos e pode ser cancelado", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = window.CV.util.debounce(fn, 50);
    const context = { debounced };
    context.debounced("primeiro");
    context.debounced("segundo");
    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledOnce();
    expect(fn).toHaveBeenCalledWith("segundo");
    expect(fn.mock.instances[0]).toBe(context);

    context.debounced("cancelado");
    debounced.cancel();
    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });
});
