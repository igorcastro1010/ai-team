import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  await page.goto("/escritorio");
}

for (const width of [360, 390, 430, 1440]) {
  test(`escritório acessível com estados reais em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await login(page);
    await expect(page.getByRole("heading", { name: "Um escritório. Sete especialidades." })).toBeVisible();
    await expect(page.getByRole("button", { name: /Abrir detalhes de/ })).toHaveCount(7);
    await expect(page.locator(".pixel-station.is-working")).toHaveCount(0);
    await page.getByRole("button", { name: /Abrir detalhes de PESQUISADOR/ }).click();
    await expect(page.getByRole("heading", { name: "Pesquisa e fontes", exact: true })).toBeVisible();
    await expect(page.getByText("Perfil Hermes ainda não provisionado.", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
    await page.getByRole("heading", { name: "Um escritório. Sete especialidades." }).click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `../../artifacts/office-${width}.png`, fullPage: true });
  });
}

test("Hermes diagnóstico e consentimento por executor", async ({ page }) => {
  await login(page);
  await page.goto("/integracoes");
  await page.getByRole("button", { name: "Verificar Hermes" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Diagnóstico registrado" })).toBeVisible();
  await expect(page.getByText("Inferência ainda não homologada.", { exact: true })).toBeVisible();
  const project = await page.request.post("/api/control/projects", {
    headers: { origin: "http://localhost:3100" }, data: { name: "Hermes E2E" },
  });
  expect(project.status()).toBe(201);
  await page.goto("/ceo");
  await page.getByLabel("Projeto da solicitação").selectOption({ label: "Hermes E2E" });
  await page.getByLabel("Executor da solicitação").selectOption("hermes");
  await page.getByLabel("O que você quer construir?").fill("Proponha um plano de revisão da interface.");
  await page.getByRole("checkbox", { name: /Autorizo enviar esta solicitação ao Hermes/ }).check();
  await page.getByRole("button", { name: "Enviar ao CEO" }).click();
  await expect(page.getByRole("status")).toContainText("Solicitação registrada");
  const runs = await (await page.request.get("/api/control/runs")).json();
  expect(runs.find((r: { prompt: string }) => r.prompt.includes("revisão da interface"))?.executor).toBe("hermes");
});
