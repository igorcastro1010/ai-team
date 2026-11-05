import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function enter(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const stamp = `${Date.now()}-${test.info().testId.slice(-6)}`;
  const ids: string[] = [];
  for (const name of [`Conhecimento A ${stamp}`, `Conhecimento B ${stamp}`]) {
    const response = await page.request.post("/api/control/projects", { headers: { origin: "http://localhost:3100" }, data: { name } });
    expect(response.status()).toBe(201);
    ids.push((await response.json()).id);
  }
  await page.goto("/memoria");
  await expect(page.getByRole("heading", { name: "Conhecimento que acompanha o projeto." })).toBeVisible();
  await page.getByLabel("Projeto do conhecimento").selectOption(ids[0]);
  await expect(page.getByRole("status")).toContainText("Conhecimento atualizado");
  return ids;
}

test("memória cria, busca, revisa histórico e isola projetos no backend real", async ({ page }) => {
  const ids = await enter(page);
  await page.getByLabel("Título da memória").fill("Direção do catálogo");
  await page.getByLabel("Conteúdo da memória").fill("Catálogo deve usar cores verdes e preservar identidade.");
  await page.getByRole("button", { name: "Salvar memória", exact: true }).click();
  const card = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Direção do catálogo", exact: true }) });
  await expect(card).toContainText("Versão 1");
  const unrelated = await page.request.post(`/api/control/memory/${ids[0]}`, { headers: { origin: "http://localhost:3100" }, data: { title: "Nota sem relação", content: "A infraestrutura possui workers isolados." } });
  expect(unrelated.status()).toBe(201);
  await page.getByLabel("Buscar memórias").fill("catálogo");
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Busca concluída");
  await expect(card).toBeVisible();
  await expect(page.getByRole("heading", { name: "Nota sem relação", exact: true })).toHaveCount(0);
  await page.getByLabel("Buscar memórias").fill("");
  await page.getByRole("button", { name: "Buscar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Nota sem relação", exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Editar memória" }).click();
  await page.getByLabel("Conteúdo da memória").fill("Catálogo preserva cores verdes, identidade e acessibilidade.");
  await page.getByRole("button", { name: "Salvar revisão" }).click();
  await expect(card).toContainText("Versão 2");
  await card.getByRole("button", { name: "Ver histórico" }).click();
  await expect(page.getByRole("region", { name: "Histórico da memória" })).toContainText("Versão 1");
  await page.getByLabel("Projeto do conhecimento").selectOption(ids[1]);
  await expect(page.getByRole("status")).toContainText("Conhecimento atualizado");
  await expect(page.getByText("Nenhuma memória neste projeto.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Direção do catálogo", exact: true })).toHaveCount(0);
  await page.getByLabel("Projeto do conhecimento").selectOption(ids[0]);
  await expect(card).toContainText("Versão 2");
  expect((await new AxeBuilder({ page }).include(".knowledge-panel").withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
});

test("resposta inicial antiga não apaga memória salva enquanto o grafo carrega", async ({ page }) => {
  const ids = await enter(page);
  await page.getByLabel("Projeto do conhecimento").selectOption(ids[1]);
  await expect(page.getByRole("status")).toContainText("Conhecimento atualizado");
  let release!: () => void;
  let captured!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const started = new Promise<void>(resolve => { captured = resolve; });
  let first = true;
  const graphUrl = `**/api/control/knowledge/${ids[0]}/graph`;
  await page.route(graphUrl, async route => {
    if (!first) { await route.continue(); return; }
    first = false;
    const response = await route.fetch();
    captured();
    await held;
    await route.fulfill({ response });
  });
  try {
    await page.getByLabel("Projeto do conhecimento").selectOption(ids[0]);
    await started;
    await page.getByLabel("Título da memória").fill("Decisão durante carregamento");
    await page.getByLabel("Conteúdo da memória").fill("Preservar o snapshot mais recente.");
    await page.getByRole("button", { name: "Salvar memória", exact: true }).click();
    const card = page.getByRole("heading", { name: "Decisão durante carregamento", exact: true });
    await expect(card).toBeVisible();
    const returned = page.waitForResponse(response => response.url().endsWith(`/knowledge/${ids[0]}/graph`));
    release();
    await returned;
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(card).toBeVisible();
  } finally { release(); }
});

test("Issues usa proposta persistente e revisão explícita, otimizador estima sem inferência", async ({ page }) => {
  const [projectId] = await enter(page);
  await page.getByRole("button", { name: "Issues", exact: true }).click();
  await page.getByLabel("Título da issue").fill("Revisar navegação acessível");
  await page.getByLabel("Descrição da issue").fill("Validar foco por teclado antes de publicar qualquer alteração.");
  await page.getByRole("button", { name: "Preparar proposta local" }).click();
  const card = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Revisar navegação acessível", exact: true }) });
  await expect(card).toContainText("Aguardando revisão");
  await expect(page.getByLabel("Filtrar agente")).toBeVisible({ timeout: 1000 });
  await page.getByLabel("Filtrar agente").selectOption("QA");
  await expect(card).toHaveCount(0);
  await page.getByLabel("Filtrar agente").selectOption("DEV");
  await expect(card).toBeVisible();
  await page.getByLabel("Filtrar prioridade").selectOption("low");
  await expect(card).toHaveCount(0);
  await page.getByLabel("Filtrar prioridade").selectOption("medium");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Validar foco por teclado");
  const response = await page.request.get(`/api/control/issues?project_id=${projectId}`);
  const issue = (await response.json()).issues[0];
  expect(issue.action.status).toBe("pending");
  await page.reload();
  await page.getByLabel("Projeto do conhecimento").selectOption(projectId);
  await page.getByRole("button", { name: "Issues", exact: true }).click();
  await expect(card).toContainText(issue.request_id);
  await page.getByRole("button", { name: "Otimizador", exact: true }).click();
  await page.getByLabel("Solicitação para prévia").fill("Revisar catálogo com identidade verde");
  await page.getByRole("button", { name: "Calcular prévia local" }).click();
  await expect(page.getByRole("region", { name: "Resultado da prévia" })).toContainText("Estimativa");
  await expect(page.getByText("Economia medida: indisponível sem comparação autorizada no provedor.")).toBeVisible();
  await page.getByRole("button", { name: "Calcular prévia local" }).click();
  await expect(page.getByRole("region", { name: "Resultado da prévia" })).toContainText("Cache reutilizado");
  await page.getByLabel("Limite do orçamento").fill("12000");
  await page.getByRole("button", { name: "Salvar limite" }).click();
  await expect(page.getByRole("status")).toContainText("Orçamento atualizado");
  await page.getByRole("button", { name: "Relações", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Relações do projeto" })).toBeVisible();
  await page.setViewportSize({ width: 360, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).include(".knowledge-panel").withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
});
