export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/control${path}`, {
    ...options, cache: "no-store", headers: { "content-type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof data.detail === "string" ? data.detail : "Verifique os campos e tente novamente.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export type Project = { id: string; name: string; description: string; mode: string; created_at: number };
export type TaskStatus = "backlog" | "in_progress" | "review" | "done";
export type Task = { id: string; title: string; description: string; agent: string; status: TaskStatus; project_id: string; created_at: number };
export type Event = { id: string; kind: string; summary: string; actor: string; resource_id: string; created_at: number };
export type Agent = { id: string; name: string; role: string; description: string; tools: string[]; limit: string; status: string };
export type Integration = { id: string; name: string; status: string; description: string; verified_at: number | null };
export type Workspace = {
  version: string; owner: string; projects: Project[]; tasks: Task[]; events: Event[];
  agents: Agent[]; integrations: Integration[]; runs: unknown[]; approvals: unknown[];
  usage: { requests: number; tokens: number; cost_usd: number | null };
};

export const statusLabel: Record<TaskStatus, string> = {
  backlog: "A fazer", in_progress: "Em andamento", review: "Em revisão", done: "Concluído",
};
export const modes: Record<string, string> = { manual: "Manual", supervised: "Supervisionado", automatic: "Automático" };
export const dateTime = (value: number) => new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short", timeStyle: "short", timeZone: "America/Fortaleza",
}).format(new Date(value * 1000));
