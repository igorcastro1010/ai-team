import { test, expect } from "@playwright/test";

async function openOffice(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  await page.goto("/escritorio");
}

test("mapa vivo permite pausar, ampliar e selecionar sem inventar atividade", async ({ page }) => {
  await openOffice(page);
  const map = page.getByRole("region", { name: "Mapa do escritório virtual" });
  await expect(map).toBeVisible();
  await expect(page.getByText("0 em execução", { exact: true })).toBeVisible();
  const walker = page.locator(".office-actor.is-walking .actor-travel").first();
  await expect(walker).toBeVisible();
  const start = await walker.evaluate(el => getComputedStyle(el).transform);
  await expect.poll(() => walker.evaluate(el => getComputedStyle(el).transform)).not.toBe(start);
  await page.getByRole("button", { name: "Pausar animações" }).click();
  await expect(page.locator(".office-campus")).toHaveAttribute("data-motion", "paused");
  await expect(walker).toHaveCSS("animation-play-state", "paused");
  await page.getByRole("button", { name: "Ampliar mapa" }).click();
  await expect(page.getByRole("button", { name: "Restaurar zoom" })).toHaveText("115%");
  await page.getByRole("button", { name: "Restaurar zoom" }).click();
  await expect(page.getByRole("button", { name: "Restaurar zoom" })).toHaveText("100%");
  await page.getByRole("button", { name: /Abrir detalhes de DESIGNER:/ }).click();
  await expect(page.getByRole("heading", { name: "Produto e experiência", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retomar animações" }).click();
  await page.getByLabel("Buscar agente").fill("pesquisador");
  await expect(page.getByRole("button", { name: /Abrir detalhes de/ })).toHaveCount(1);
});

test("movimento reduzido e perda de conexão congelam a cena", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openOffice(page);
  await expect(page.locator(".office-campus")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator(".actor-travel").first()).toHaveCSS("animation-name", "none");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.locator(".office-campus")).toHaveAttribute("data-motion", "running");
  await page.route("**/api/control/workspace", route => route.abort());
  await expect(page.locator(".office-campus")).toHaveAttribute("data-motion", "paused", { timeout: 12000 });
  await expect(page.locator(".office-actor.is-working")).toHaveCount(0);
});

test("zoom mobile amplia a cena de verdade e mantém rolagem dentro do mapa", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 900 });
  await openOffice(page);
  const world = page.locator(".office-map-world");
  const before = (await world.boundingBox())!.width;
  await page.getByRole("button", { name: "Ampliar mapa" }).click();
  await expect.poll(async () => (await world.boundingBox())!.width).toBeGreaterThan(before * 1.1);
  const map = page.getByRole("region", { name: "Mapa do escritório virtual" });
  const offset = await map.evaluate(el => { el.scrollLeft = el.scrollWidth; return el.scrollLeft; });
  expect(offset).toBeGreaterThan(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("execução confirmada fica na mesa e aba oculta pausa as animações", async ({ page }) => {
  await page.route("**/api/control/workspace", async route => {
    const response = await route.fetch();
    const data = await response.json();
    // UI fixture only: no real tasks, model calls or changes to the backend DB.
    data.office_observed_at = Math.floor(Date.now() / 1000);
    data.office.find((agent: { id: string }) => agent.id === "DEV").status = "working";
    data.office.find((agent: { id: string }) => agent.id === "DEV").animate = true;
    await route.fulfill({ response, json: data });
  });
  await openOffice(page);
  await expect(page.getByText("1 em execução", { exact: true })).toBeVisible();
  const worker = page.locator(".office-actor.is-working");
  await expect(worker).toHaveCount(1);
  await expect(worker).not.toHaveClass(/is-walking/);
  await expect(worker.getByText("Trabalhando", { exact: false })).toBeVisible();
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(page.locator(".office-campus")).toHaveAttribute("data-motion", "paused");
  await expect(worker.locator(".sprite-arm-left")).toHaveCSS("animation-play-state", "paused");
});
