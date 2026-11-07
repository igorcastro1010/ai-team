import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.setTimeout(60000);

test("login abre escritório e ferramentas preservam mapa e zoom", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  const campus = page.locator(".office-campus");
  await expect(campus).toBeVisible({ timeout: 20000 });
  const original = await campus.elementHandle();
  await page.getByRole("button", { name: "Ampliar mapa" }).click();
  await page.getByRole("button", { name: "Selecionar DESIGNER no mapa", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Estúdio de vídeo" })).toBeVisible();
  await expect(campus.locator("..")).toHaveAttribute("inert", "");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await expect(page).toHaveURL(/\/videos$/);
  await page.getByRole("button", { name: "Fechar ferramenta" }).click();
  await expect(page.getByRole("button", { name: "Restaurar zoom" })).toHaveText("115%");
  expect(await original!.evaluate(el => el.isConnected)).toBe(true);
  await page.screenshot({ path: "../../artifacts/pixel-integrated-desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Selecionar CEO no mapa", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Conversa com CEO" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await original!.evaluate(el => el.isConnected)).toBe(true);
});

test("link direto móvel mantém ferramenta acessível e volta ao escritório", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.locator(".office-campus")).toBeVisible({ timeout: 20000 });
  await page.goto("/memoria");
  const panel = page.getByRole("dialog", { name: "Memória e contexto" });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Conhecimento que acompanha o projeto." })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/pixel-integrated-mobile.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Fechar ferramenta" }).click();
  await expect(page.getByRole("region", { name: "Mapa do escritório virtual" })).toBeVisible();
});
