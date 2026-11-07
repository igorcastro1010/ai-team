import { expect, test } from "@playwright/test";

test("vídeo exige revisão, permite cancelar e isola os projetos", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Usuário", { exact: true }).fill("e2e");
  await page.getByLabel("Senha", { exact: true }).fill("somente-teste-e2e-8493");
  await page.getByRole("button", { name: "Entrar no workspace" }).click();
  await expect(page.getByRole("heading", { name: "Sua sala de operações." })).toBeVisible();
  const ids: string[] = [];
  for (const name of ["Vídeo A", "Vídeo B"]) {
    const response = await page.request.post("/api/control/projects", { headers: { origin: "http://localhost:3100" }, data: { name: `${name} ${Date.now()}` } });
    expect(response.status()).toBe(201); ids.push((await response.json()).id);
  }
  await page.goto("/videos");
  await page.getByLabel("Projeto dos vídeos").selectOption(ids[0]);
  await expect(page.getByRole("status")).toContainText("Vídeos atualizados");
  await page.getByLabel("Título do vídeo").fill("Apresentação do projeto");
  await page.getByLabel("Texto da cena 1").fill("Olá, equipe. Este é nosso projeto.");
  await page.getByLabel("Autorizo gerar este vídeo localmente após revisar o roteiro").check();
  await page.getByRole("button", { name: "Preparar revisão" }).click();
  const card = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Apresentação do projeto", exact: true }) });
  await expect(card).toContainText("Aguardando sua aprovação");
  await expect(card.getByText("Olá, equipe. Este é nosso projeto.")).toBeVisible();
  await expect(card.getByRole("link", { name: "Baixar MP4" })).toHaveCount(0);
  await card.getByRole("button", { name: "Recusar roteiro" }).click();
  await expect(card).toContainText("Cancelado");
  await page.getByLabel("Projeto dos vídeos").selectOption(ids[1]);
  await expect(page.getByText("Nenhum vídeo neste projeto.")).toBeVisible();
  await expect(card).toHaveCount(0);
});
