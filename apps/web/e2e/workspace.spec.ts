import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { views, type View } from "../lib/navigation";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
}

test("dados privados exigem login e mutações bloqueiam CSRF", async ({ request }) => {
  expect((await request.get("/api/control/workspace")).status()).toBe(401);
  expect((await request.post("/api/control/projects", { data: { name: "indevido" }, headers: { origin: "https://evil.example" } })).status()).toBe(403);
});

test("cria projeto e tarefa, move quadro e preserva após recarregar", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Novo projeto", exact: true }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Nome do projeto").fill("Operação E2E");
  await dialog.getByLabel("Descrição").fill("Projeto criado pelo fluxo real do navegador.");
  await dialog.getByRole("button", { name: "Criar projeto" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("link", { name: "Projetos", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Operação E2E" })).toBeVisible();
  await page.getByRole("link", { name: "Tarefas", exact: true }).click();
  await page.getByRole("button", { name: "Nova tarefa", exact: true }).first().click();
  await dialog.getByLabel("Título da tarefa").fill("Revisar acessibilidade");
  await dialog.getByLabel("Agente responsável").selectOption("QA");
  await dialog.getByRole("button", { name: "Criar tarefa" }).click();
  const task = page.getByTestId("task-card").filter({ hasText: "Revisar acessibilidade" });
  await expect(task).toBeVisible();
  await task.getByRole("button", { name: "Iniciar tarefa" }).click();
  await expect(task.getByRole("button", { name: "Enviar para revisão" })).toBeVisible();
  await page.reload();
  await expect(task.getByRole("button", { name: "Enviar para revisão" })).toBeVisible();
  await page.getByRole("link", { name: "Histórico", exact: true }).click();
  await expect(page.getByText("Tarefa criada: Revisar acessibilidade")).toBeVisible();
});

test("navegação móvel sem overflow e links preservados", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await login(page);
  for (const route of ["/", "/projetos", "/tarefas", "/agentes", "/ceo", "/execucoes", "/aprovacoes", "/relatorios", "/integracoes"]) {
    await page.goto(route);
    const view = route === "/" ? "overview" : route.slice(1) as View;
    await expect(page.getByRole("heading", { name: views[view].title, exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Abrir navegação" }).click();
    await expect(page.getByRole("link", { name: "Integrações", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Fechar navegação" }).click();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const clipped = await page.locator("main button, main input, main select").evaluateAll(elements => elements.filter(element => {
      const rect = element.getBoundingClientRect();
      return rect.width && (rect.left < -1 || rect.right > innerWidth + 1);
    }).map(element => element.textContent));
    expect(clipped).toEqual([]);
  }
});

test("login e painel sem violações WCAG A/AA detectadas", async ({ page }) => {
  await page.goto("/login");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await login(page);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "../../artifacts/overview-desktop.png", fullPage: true });
});

test("logout revoga acesso e encerra sessão no navegador", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Sair do workspace" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/api/control/workspace")).status()).toBe(401);
});
