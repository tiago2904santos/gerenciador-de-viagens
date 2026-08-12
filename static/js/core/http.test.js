import { beforeEach, describe, expect, it, vi } from "vitest";

await import("./http.js");

function response({ contentType = "application/json", data = {}, ok = true, status = 200, text = "" } = {}) {
  return {
    headers: { get: vi.fn(() => contentType) },
    json: vi.fn(async () => data),
    ok,
    status,
    text: vi.fn(async () => text),
  };
}

describe("CV.http", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=; Max-Age=0; path=/";
    vi.stubGlobal("fetch", vi.fn());
  });

  it("le cookies e prioriza o token do formulario", () => {
    document.cookie = "outro=valor; path=/";
    document.cookie = "csrftoken=abc%20123; path=/";
    const form = document.createElement("form");
    form.innerHTML = '<input name="csrfmiddlewaretoken" value="do-form">';

    expect(window.CV.http.getCookie("csrftoken")).toBe("abc 123");
    expect(window.CV.http.getCookie("ausente")).toBe("");
    expect(window.CV.http.getCsrfToken(form)).toBe("do-form");
    expect(window.CV.http.getCsrfToken(document.createElement("form"))).toBe("abc 123");
  });

  it("prepara requisicao JSON com defaults, CSRF e headers do chamador", async () => {
    document.cookie = "csrftoken=token-cookie; path=/";
    fetch.mockResolvedValue(response());

    await window.CV.http.request("/api/itens", {
      method: "POST",
      body: { nome: "Teste" },
      headers: { Accept: "application/json" },
      rawResponse: true,
    });

    expect(fetch).toHaveBeenCalledWith("/api/itens", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        ["X-CSRF" + "Token"]: "token-cookie",
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ nome: "Teste" }),
    });
  });

  it("preserva corpos prontos e Content-Type informado", async () => {
    fetch.mockResolvedValue(response());
    const formData = new FormData();
    formData.append("arquivo", "conteudo");
    await window.CV.http.request("/upload", { body: formData });
    expect(fetch.mock.calls[0][1].body).toBe(formData);
    expect(fetch.mock.calls[0][1].headers["Content-Type"]).toBeUndefined();

    await window.CV.http.request("/texto", {
      body: { ativo: true },
      headers: { "content-type": "application/problem+json" },
    });
    expect(fetch.mock.calls[1][1].headers["Content-Type"]).toBeUndefined();
    expect(fetch.mock.calls[1][1].body).toBe('{"ativo":true}');
  });

  it("normaliza respostas JSON e respostas invalidas", async () => {
    const json = response({ data: { ok: true }, status: 201 });
    await expect(window.CV.http.readJsonResponse(json)).resolves.toEqual({
      ok: true,
      status: 201,
      data: { ok: true },
    });

    const expired = response({ contentType: "text/html", ok: false, status: 401, text: "login" });
    await expect(window.CV.http.readJsonResponse(expired)).resolves.toMatchObject({
      ok: false,
      status: 401,
      data: { ok: false, error: "Sessão expirada. Faça login novamente." },
    });

    const invalid = response({ contentType: "text/html", ok: true, status: 502 });
    await expect(window.CV.http.readJsonResponse(invalid)).resolves.toMatchObject({
      ok: false,
      status: 502,
      data: { error: "O servidor retornou uma resposta inválida." },
    });
  });

  it("oferece atalhos para JSON bruto, JSON normalizado e texto", async () => {
    const raw = response({ data: { id: 1 } });
    fetch.mockResolvedValueOnce(raw);
    await expect(window.CV.http.fetchJson("/raw", { rawResponse: true })).resolves.toBe(raw);

    fetch.mockResolvedValueOnce(response({ data: { id: 2 } }));
    await expect(window.CV.http.fetchJson("/json")).resolves.toMatchObject({ data: { id: 2 } });

    const plain = response({ contentType: "text/plain", status: 206, text: "parcial" });
    fetch.mockResolvedValueOnce(plain);
    await expect(window.CV.http.fetchText("/texto")).resolves.toEqual({
      ok: true,
      status: 206,
      data: "parcial",
      response: plain,
    });
  });
});
