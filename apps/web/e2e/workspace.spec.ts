import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { views, type View } from "../lib/navigation";
import { execFileSync } from "node:child_process";
import path from "node:path";

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
  expect((await request.get("/api/control/vercel")).status()).toBe(401);
  expect((await request.post("/api/control/vercel/inspect", { headers: { origin: "https://evil.example" } })).status()).toBe(403);
});

test("agenda textual exige consentimento, persiste e permite cancelar", async ({ page }) => {
  await login(page);
  const project = await page.request.post('/api/control/projects', {
    headers: {origin:'http://localhost:3100'}, data:{name:'Recorrência E2E'},
  });
  expect(project.status()).toBe(201);
  await page.goto('/agendamentos');
  await page.getByLabel('Projeto do agendamento').selectOption({label:'Recorrência E2E'});
  await page.getByLabel('Solicitação recorrente').fill('Planeje uma revisão mensal do produto.');
  const localStart = new Date(Date.now() + 3600000 - 3 * 3600000).toISOString().slice(0,16);
  await page.getByLabel('Primeiro horário').fill(localStart);
  await page.getByLabel('Número de ocorrências').fill('2');
  await page.getByLabel('Modo das ocorrências').selectOption('automatic');
  await page.getByRole('checkbox', {name:/Autorizo esta recorrência/}).check();
  await page.getByRole('button', {name:'Autorizar agendamento',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Agendamento autorizado');
  await page.reload();
  const card = page.getByRole('article').filter({hasText:'Planeje uma revisão mensal do produto.'});
  await expect(card).toContainText('0 de 2 ocorrências');
  await card.getByRole('button',{name:'Cancelar recorrência'}).click();
  const confirmation=page.getByRole('dialog',{name:'Cancelar recorrência?'});
  await confirmation.getByRole('button',{name:'Manter agendamento'}).click();
  await expect(card).toContainText('Ativo');
  await card.getByRole('button',{name:'Cancelar recorrência'}).click();
  await confirmation.getByRole('button',{name:'Confirmar cancelamento'}).click();
  await expect(card).toContainText('Cancelado');
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);
});

test("relatório exporta totais e navega por todas as páginas", async ({ page }) => {
  await login(page);
  const response = await page.request.get('/api/control/reports?limit=1');
  expect(response.status()).toBe(200);
  const realReport = await response.json();
  let usedCursor=false;
  await page.route('**/api/control/reports*', route => {
    const query=new URL(route.request().url()).searchParams;
    usedCursor=query.has('before_id');
    return route.fulfill({contentType:'application/json', body:JSON.stringify({
      ...realReport, summary:{...realReport.summary, runs:{completed:205}},
      runs:[{id:usedCursor?'second-run':'first-run',project_id:'test',status:'completed',
        mode:'automatic',calls:5,input_tokens:20,output_tokens:10,created_at:1000,
        schedule_id:null,occurrence:null}],
      next_cursor:usedCursor?null:{before_created_at:1000,before_id:'first-run'},
    })});
  });
  await page.goto('/relatorios');
  await expect(page.getByText('205 execuções registradas')).toBeVisible();
  await expect(page.getByText('first-run',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Página seguinte'}).click();
  await expect(page.getByText('second-run',{exact:true})).toBeVisible();
  expect(usedCursor).toBe(true);
  const downloadEvent=page.waitForEvent('download');
  await page.getByRole('button',{name:'Exportar página JSON'}).click();
  const download=await downloadEvent;
  const stream=await download.createReadStream();
  const chunks:Buffer[]=[];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const exported=JSON.parse(Buffer.concat(chunks).toString('utf8'));
  expect(exported.summary.runs.completed).toBe(205);
  expect(exported.runs[0].id).toBe('second-run');
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);
});

test("Vercel mostra consultas e falhas sem oferecer publicação", async ({ page }) => {
  await login(page);
  await page.goto('/integracoes');
  const panel = page.getByRole('region', {name:'Consultas Vercel'});
  await page.route('**/api/control/vercel/inspect', route => route.fulfill({
    status:502,contentType:'application/json',body:JSON.stringify({detail:'Consulta indisponível de teste.'})}));
  await panel.getByRole('button',{name:'Consultar Vercel'}).click();
  await expect(panel.getByRole('alert')).toContainText('Consulta indisponível de teste.');
  await page.unroute('**/api/control/vercel/inspect');
  await page.route('**/api/control/vercel/inspect', route => route.fulfill({
    contentType:'application/json',body:JSON.stringify({verified_at:1793233759,
      project:{id:'prj_synthetic',name:'ai-team'},deployments:[]})}));
  await panel.getByRole('button',{name:'Consultar Vercel'}).click();
  await expect(panel.getByRole('heading',{name:'Projeto ai-team'})).toBeVisible();
  await expect(panel.getByText(/Sem deploys neste projeto/)).toBeVisible();
  await expect(panel.getByRole('button',{name:/publicar|deploy|domínio/i})).toHaveCount(0);
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);
});

test("proposta GitHub é revisada, cancelável e aprovada uma única vez", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Novo projeto", exact: true }).first().click();
  const creation = page.getByRole("dialog");
  await creation.getByLabel("Nome do projeto").fill("GitHub E2E");
  await creation.getByRole("button", { name: "Criar projeto" }).click();
  await expect(creation).not.toBeVisible();
  await page.getByRole("link", { name: "Integrações", exact: true }).click();
  await page.getByLabel("Projeto da proposta").selectOption({ label: "GitHub E2E" });
  await page.getByLabel("Título ou mensagem de commit").fill("Branch sintética E2E");
  await page.getByLabel("Branch de trabalho").fill("codex/ai-team/e2e");
  await page.getByLabel("SHA revisado da base").fill("a".repeat(40));
  await page.getByLabel(/Revisei o conteúdo e não incluí credenciais/).check();
  await page.getByRole("button", { name: "Registrar proposta", exact: true }).click();
  const action = page.getByTestId("github-action").filter({ hasText: "Branch sintética E2E" });
  await expect(action.getByText("Revisão pendente", { exact: true })).toBeVisible();
  await action.getByRole("button", { name: "Revisar aprovação" }).click();
  const approval = page.getByRole("dialog");
  await expect(approval).toContainText("codex/ai-team/e2e");
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: "../../artifacts/github-approval-desktop.png", fullPage: true });
  await approval.getByRole("button", { name: "Voltar à revisão" }).click();
  await expect(approval).not.toBeVisible();
  await action.getByRole("button", { name: "Revisar aprovação" }).click();
  await approval.getByRole("button", { name: "Autorizar execução" }).click();
  await expect(approval).not.toBeVisible();
  await expect(action.getByText("Autorizada · na fila", { exact: true })).toBeVisible();
  await page.reload();
  await expect(action.getByRole("button", { name: "Revisar aprovação" })).toHaveCount(0);
  const result = await page.request.get("/api/control/github");
  const actions = (await result.json()).actions.filter((item: { payload: { title: string } }) => item.payload.title === "Branch sintética E2E");
  expect(actions).toHaveLength(1);
  expect(actions[0].status).toBe("approved");
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
  await page.goto("/ceo");
  await expect(page.getByLabel("O que você quer construir?")).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
});

test("logout revoga acesso e encerra sessão no navegador", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Sair do workspace" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/api/control/workspace")).status()).toBe(401);
});

test("CEO registra pedido e permite revisar, aprovar e cancelar com confirmação", async ({ page }) => {
  await login(page);
  const created = await page.request.post("/api/control/projects", {
    headers: { origin: "http://localhost:3100" }, data: { name: "Projeto CEO E2E", mode: "manual" },
  });
  expect(created.status()).toBe(201);
  await page.goto("/ceo");
  await page.getByLabel("Projeto da solicitação").selectOption({ label: "Projeto CEO E2E" });
  await page.getByLabel("O que você quer construir?").fill("Planejar interface de exemplo para revisão E2E.");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Enviar ao CEO" }).click();
  const runCard = page.getByTestId("run-card").filter({ hasText: "Planejar interface de exemplo" });
  await expect(runCard.getByText("Na fila", { exact: true })).toBeVisible();
  const root = path.resolve(__dirname, "../../..");
  const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  execFileSync(python, ["-c", "import sys; sys.path.insert(0, 'services/api/tests'); from test_workflow import TestProvider; from ai_team.worker import Worker; from ai_team.db import Database; from ai_team.config import Settings; s=Settings(); assert Worker(Database(s),s,TestProvider()).once()"], {
    cwd: root, env: { ...process.env, AI_TEAM_DATABASE_URL: process.env.AI_TEAM_E2E_DB, AI_TEAM_ENVIRONMENT: "test" },
  });
  await page.goto("/aprovacoes");
  await expect(page.getByText("Proposta textual, sem execução externa.")).toBeVisible();
  await page.screenshot({ path: "../../artifacts/approval-desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Aprovar próxima etapa" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Voltar", exact: true }).click();
  await expect(page.getByText("Aguarda aprovação", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Aprovar próxima etapa" }).click();
  await dialog.getByRole("button", { name: "Autorizar elaboração", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.goto("/execucoes");
  await expect(runCard.getByText("Na fila", { exact: true })).toBeVisible();
  await runCard.getByRole("button", { name: "Cancelar execução", exact: true }).click();
  await dialog.getByRole("button", { name: "Cancelar execução", exact: true }).click();
  await expect(runCard.getByText("Cancelada", { exact: true })).toBeVisible();
});
