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
export type Run = {
  artifact_digest?: string;
  executor: "codex" | "hermes";
  id: string; project_id: string; prompt: string; mode: string; scope: string; status: string;
  stage: number; calls: number; input_tokens: number; output_tokens: number; error: string;
  created_at: number; steps: { stage: number; agent: string; summary: string; deliverable: string; input_tokens: number; output_tokens: number; execution_started?: boolean; test_result?: { status: string; exit_code: number | null; output: string } }[];
};
export type Workspace = {
  office: OfficeAgent[];
  office_observed_at: number;
  hermes: { connection: HermesObservation | null; executions: HermesPage; monitor?: HermesMonitor; jobs?: HermesJobsSnapshot };
  version: string; owner: string; projects: Project[]; tasks: Task[]; events: Event[];
  agents: Agent[]; integrations: Integration[]; runs: Run[]; approvals: Run[];
  usage: { requests: number; tokens: number; cost_usd: number | null; worker_online: boolean };
  github: { connection: { repository: string; default_branch: string; head_sha?: string; verified_at: number } | null; actions: GitHubAction[] };
  vercel: { connection: VercelObservation | null };
  schedules: Schedule[];
};

export type HermesObservation = {
  status: "not_configured" | "unavailable" | "unsafe_configuration" | "reachable";
  checked_at: number | null; inference_verified: false; text_only: true;
};
export type HermesAttempt = {
  id: string; run_id: string; stage: number; remote_id: string; remote_status: string;
  bridge_status: string; stop_status: string; local_status: string;
  input_tokens: number | null; output_tokens: number | null;
  created_at: number; updated_at: number;
};
export type HermesPage = { items: HermesAttempt[]; next_cursor: string | null };
export type OfficeAgent = {
  activity?: string;
  id: string; name: string; role: string; enabled: boolean;
  status: "available" | "working" | "awaiting_approval" | "completed" | "error";
  animate: boolean; run_id: string | null; executor: string | null;
  run_status: string | null; error: string;
  history: { run_id: string; executor: string; created_at: number; summary: string; deliverable: string }[];
};

export type Schedule = {
  id: string; project_id: string; prompt: string; mode: string;
  interval_seconds: number; next_run_at: number; expires_at: number;
  max_runs: number; emitted: number; status: string; created_at: number;
};

export type VercelObservation = {
  verified_at: number; project: { id: string; name: string } | null;
  deployments: { id: string | null; state: string | null; created_at: number | null }[];
};

export type GitHubAction = {
  id: string; project_id: string; digest: string; status: string; created_at: number; error: string;
  payload: { project_id: string; operation: string; title: string; branch: string; expected_sha: string; path: string; content: string; body: string; draft: boolean };
  result: { url?: string; sha?: string; number?: number };
};

export const statusLabel: Record<TaskStatus, string> = {
  backlog: "A fazer", in_progress: "Em andamento", review: "Em revisão", done: "Concluído",
};
export const modes: Record<string, string> = { manual: "Manual", supervised: "Supervisionado", automatic: "Automático" };
export const dateTime = (value: number) => new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short", timeStyle: "short", timeZone: "America/Fortaleza",
}).format(new Date(value * 1000));

export type HermesJob = {
  id: string; name: string; enabled: boolean;
  state: "scheduled" | "paused" | "completed" | "error" | "unknown";
  schedule_kind: "once" | "interval" | "cron" | "unknown";
  next_run_at: number | null; last_run_at: number | null;
  repeat_times: number | null; repeat_completed: number;
};
export type HermesJobPause = { job_id: string; status: "confirmed" | "uncertain"; checked_at: number };
export type HermesJobsSnapshot = {
  status: "not_configured" | "unavailable" | "reachable";
  checked_at: number | null; items: HermesJob[]; truncated: boolean;
  last_pause: HermesJobPause | null;
};

export type HermesMonitor = {
  connection: { status: "not_started" | "not_configured" | "running"; checked_at: number | null; recent: boolean };
  pending: number; failed: number;
};
