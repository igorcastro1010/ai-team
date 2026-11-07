import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import path from "node:path";

test("produção local real revisa quatro cenas, aprova digest e entrega MP4", async ({ page }) => {
  test.setTimeout(120000);
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const created = await page.request.post("/api/control/projects", { headers: { origin: "http://localhost:3100" }, data: { name: `Fábrica ${Date.now()}` } });
  const project = (await created.json()).id;
  await page.goto("/videos");
  await page.getByLabel("Projeto dos vídeos").selectOption(project);
  await page.getByLabel("Descreva o vídeo que deseja criar").fill("Crie um Reels de 15 segundos com a logo FORTALAKA. Preto, branco e vermelho.");
  await page.getByLabel("Importar logo, foto, vídeo ou áudio").setInputFiles({ name: "fixture.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jGv8AAAAASUVORK5CYII=", "base64") });
  await expect(page.getByRole("checkbox", { name: "fixture.png" })).toBeChecked();
  await page.getByRole("button", { name: "Iniciar produção", exact: true }).click();
  const card = page.getByTestId("factory-production").first();
  await expect(card).toBeVisible();
  const root = path.resolve(__dirname, "../../..");
  const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  function advance(count: number) {
    execFileSync(python, ["-c", `from ai_team.db import Database; from ai_team.config import Settings; from ai_team.video_store import VideoStore; from ai_team.video_worker import VideoWorker; w=VideoWorker(VideoStore(Database(Settings()))); [w.once() for _ in range(${count})]`], { cwd: root, timeout: 60000, env: { ...process.env, AI_TEAM_DATABASE_URL: process.env.AI_TEAM_E2E_DB, AI_TEAM_ENVIRONMENT: "test" } });
  }
  advance(3);
  await expect(card.getByText("Revise e aprove o roteiro", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(card.getByLabel("Texto automático da cena 4")).toBeVisible();
  const workspace = await (await page.request.get("/api/control/workspace")).json();
  expect(workspace.office.find((agent: { id: string }) => agent.id === "DESIGNER").executor).toBe("local");
  await page.goto("/escritorio");
  await page.getByRole("button", { name: /Abrir detalhes de DESIGNER:/ }).click();
  await expect(page.getByText("Executor autorizado: Processamento determinístico local, sem IA.")).toBeVisible();
  await page.getByRole("link", { name: "Abrir produção", exact: true }).click();
  await page.getByLabel("Projeto dos vídeos").selectOption(project);
  const composite = card.locator(".studio-composite");
  await expect(composite).toHaveCSS("opacity", "1");
  await expect(card.locator(".studio-text-anchor span")).toHaveCSS("opacity", "1");
  await expect(card.getByRole("img", { name: "Mídia da cena" })).toBeVisible();
  expect(await card.getByRole("img", { name: "Mídia da cena" }).evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
  await card.getByLabel("Texto automático da cena 1").fill("Minha revisão aprovada");
  await card.getByRole("button", { name: "Salvar revisão do roteiro" }).click();
  await expect(card.getByRole("button", { name: "Salvar revisão do roteiro" })).toBeDisabled();
  await page.reload();
  await page.getByLabel("Projeto dos vídeos").selectOption(project);
  await expect(card.getByLabel("Texto automático da cena 1")).toHaveValue("Minha revisão aprovada");
  await card.getByRole("checkbox", { name: /Revisei este roteiro/ }).check();
  await card.getByRole("button", { name: "Aprovar e renderizar" }).click();
  await expect(card.getByRole("button", { name: "Aprovar e renderizar" })).toBeDisabled();
  advance(5);
  await expect(card.getByRole("link", { name: "Baixar MP4 validado" })).toBeVisible({ timeout: 15000 });
  const file = await page.request.get((await card.getByRole("link", { name: "Baixar MP4 validado" }).getAttribute("href"))!);
  expect(file.status()).toBe(200);
  expect(file.headers()["content-type"]).toContain("video/mp4");
  expect((await file.body()).length).toBeGreaterThan(1000);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "../../artifacts/v09-factory-mobile.png", fullPage: true });
});

test("fábrica exige sessão e origem para mutações", async ({ request }) => {
  const id = "11111111-1111-4111-8111-111111111111";
  expect((await request.get(`/api/control/content-factory/${id}`)).status()).toBe(401);
  expect((await request.post("/api/control/content-factory", { data: {} })).status()).toBe(403);
  expect((await request.get(`/api/control/content-factory/${id}/arbitrary`)).status()).toBe(404);
});
