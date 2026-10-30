import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Synthetic browser fixtures verify controls, not native runtime execution.
test("jobs exigem confirmação e monitor não representa trabalho de agentes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const workspace = await (await page.request.get("/api/control/workspace")).json();
  const job = { id: "abcdef123456", name: "Relatório de teste", enabled: true, state: "scheduled",
    schedule_kind: "interval", next_run_at: null, last_run_at: null, repeat_times: 1, repeat_completed: 0 };
  const jobs = { status: "reachable", checked_at: 123, items: [job], truncated: false, last_pause: null as object | null };
  let pauses = 0;
  await page.route("**/api/control/workspace", route => route.fulfill({ json: {
    ...workspace, hermes: { ...workspace.hermes, jobs, monitor: {
      connection: { status: "running", checked_at: 123, recent: false }, pending: 2, failed: 1,
    } },
  } }));
  await page.route("**/api/control/hermes/jobs", route => route.fulfill({ json: jobs }));
  await page.route("**/api/control/hermes/jobs/inspect", route => route.fulfill({ json: jobs }));
  await page.route("**/api/control/hermes/jobs/abcdef123456/pause", async route => {
    expect(route.request().postDataJSON()).toEqual({ confirm: true });
    pauses += 1; job.enabled = false; job.state = "paused";
    jobs.last_pause = { job_id: job.id, status: "confirmed", checked_at: 123 };
    await route.fulfill({ json: jobs.last_pause });
  });
  await page.goto("/integracoes");
  await expect(page.getByText("Sem sinal recente do monitor.")).toBeVisible();
  await expect(page.getByText("Pendentes de observação: 2. Com falha de consulta: 1.")).toBeVisible();
  await page.getByRole("button", { name: "Consultar jobs no Hermes" }).click();
  await expect(page.getByText("Inventário consultado. Nenhuma execução iniciada.")).toBeVisible();
  await page.getByRole("button", { name: "Pausar este job", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Pausar este agendamento?" });
  await expect(dialog).toContainText(job.id);
  await expect(dialog).toContainText("Execuções em andamento continuam");
  await dialog.getByRole("button", { name: "Voltar", exact: true }).click();
  expect(pauses).toBe(0);
  await page.getByRole("button", { name: "Pausar este job", exact: true }).click();
  await dialog.getByRole("button", { name: "Confirmar pausa deste job" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Pausa do agendamento confirmada no Hermes.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Pausar este job", exact: true })).toHaveCount(0);
  expect(pauses).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations).toEqual([]);
});

test("BFF limita jobs a inventário e pausa autenticados", async ({ request }) => {
  expect((await request.get("/api/control/hermes/jobs")).status()).toBe(401);
  expect((await request.post("/api/control/hermes/jobs/abcdef123456/pause", {
    data: { confirm: true }, headers: { origin: "https://evil.test" },
  })).status()).toBe(403);
  for (const operation of ["resume", "run", "delete"]) {
    expect((await request.post(`/api/control/hermes/jobs/abcdef123456/${operation}`)).status()).toBe(404);
  }
  expect((await request.get("/api/control/hermes/api/jobs")).status()).toBe(404);
});
