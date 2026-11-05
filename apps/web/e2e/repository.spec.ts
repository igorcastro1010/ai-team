import { test, expect } from "@playwright/test";

test("Repositório: autorização explícita persiste sem executar no HTTP", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  await page.request.post("/api/control/projects", { headers: { origin: "http://localhost:3100" },
    data: { name: "Repositório autorizado E2E", mode: "supervised" } });
  await page.goto("/ceo");
  await expect(page.getByLabel("Limite de tokens autorizado")).toHaveValue("100000");
  await page.getByLabel("Projeto do executor").selectOption({ label: "Repositório autorizado E2E" });
  await page.getByLabel("Pedido para o repositório").fill("Valide o orçamento e escreva testes de erros.");
  await page.getByLabel("SHA de origem").fill("a".repeat(40));
  await page.getByLabel("Pasta autorizada").fill("tools");
  await page.getByLabel("Arquivos para leitura").fill("budget.py");
  await page.getByLabel("Arquivos para escrita").fill("budget.py, test_budget.py, guide.md");
  await page.getByRole("checkbox", { name: /Autorizo estes caminhos/ }).check();
  await page.getByRole("button", { name: "Criar tarefa isolada" }).click();
  await expect(page.getByTestId("repository-card").first()).toContainText("Na fila");
  await expect(page.getByTestId("repository-card").first()).toContainText("0/6");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByTestId("repository-card").first().getByRole("button", { name: "Cancelar tarefa isolada" }).click();
  await expect(page.getByTestId("repository-card").first()).toContainText("Cancelada");
});
