// Typed client for the Adjutant backend.

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Status =
  | "new"
  | "classified"
  | "needs_reply"
  | "drafted"
  | "sent"
  | "ignored";

export interface Project {
  id: number;
  name: string;
  description: string;
  auto: boolean;
  digest: boolean;
  created_at: string;
  thread_count: number;
  needs_attention: number;
}

export interface Thread {
  id: number;
  provider: string;
  provider_thread_id: string;
  project_id: number | null;
  subject: string;
  last_sender: string;
  snippet: string;
  status: Status;
  urgency: "high" | "normal" | null;
  has_draft: boolean;
  updated_at: string;
}

export interface Message {
  sender_name: string;
  sender_email: string;
  date: string | null;
  body_text: string;
  is_from_me: boolean;
}

export interface ThreadDetail {
  thread: Thread;
  messages: Message[];
  draft_body: string | null;
  reply_to: string;
}

export interface SyncSummary {
  seen: number;
  skipped: number;
  classified: number;
  drafted: number;
  errors: { thread_id: string; error: string }[];
}

export interface OrganizeSummary {
  considered: number;
  new_projects: string[];
  assigned: number;
  skipped: number;
  unresolved: number;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  projects: () => req<Project[]>("/projects"),
  createProject: (name: string, description: string) =>
    req<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  threads: (filter: { projectId?: number; unclassified?: boolean; digest?: boolean }) => {
    const params = new URLSearchParams();
    if (filter.unclassified) params.set("unclassified", "true");
    else if (filter.digest) params.set("digest", "true");
    else if (filter.projectId != null)
      params.set("project_id", String(filter.projectId));
    const qs = params.toString();
    return req<Thread[]>(`/threads${qs ? `?${qs}` : ""}`);
  },
  threadDetail: (id: number) => req<ThreadDetail>(`/threads/${id}`),
  saveDraft: (id: number, body: string) =>
    req<Thread>(`/threads/${id}/draft`, {
      method: "PUT",
      body: JSON.stringify({ body }),
    }),
  redraft: (id: number) =>
    req<Thread>(`/threads/${id}/redraft`, { method: "POST", body: "{}" }),
  send: (id: number, body: string, to?: string) =>
    req<Thread>(`/threads/${id}/send`, {
      method: "POST",
      body: JSON.stringify({ body, to }),
    }),
  ignore: (id: number) =>
    req<Thread>(`/threads/${id}/ignore`, { method: "POST", body: "{}" }),
  snooze: (id: number, hours = 16) =>
    req<Thread>(`/threads/${id}/snooze`, {
      method: "POST",
      body: JSON.stringify({ hours }),
    }),
  sync: () => req<SyncSummary>("/sync", { method: "POST", body: "{}" }),
  organize: () => req<OrganizeSummary>("/organize", { method: "POST", body: "{}" }),
  digest: (refresh = false) =>
    req<Briefing>(`/digest${refresh ? "?refresh=true" : ""}`, {
      method: "POST",
      body: "{}",
    }),
  done: (id: number) =>
    req<Thread>(`/threads/${id}/done`, { method: "POST", body: "{}" }),
  undone: (id: number) =>
    req<Thread>(`/threads/${id}/undone`, { method: "POST", body: "{}" }),
  standing: (refresh = false) =>
    req<Standings>(`/standing${refresh ? "?refresh=true" : ""}`, {
      method: "POST",
      body: "{}",
    }),
  agenda: (refresh = false) =>
    req<Agenda>(`/agenda${refresh ? "?refresh=true" : ""}`, {
      method: "POST",
      body: "{}",
    }),
  ideas: (includeDismissed = false) =>
    req<Idea[]>(`/ideas${includeDismissed ? "?include_dismissed=true" : ""}`),
  generateIdeas: (focus: IdeaFocus = "balanced", n = 6) =>
    req<{ generated: number; date: string; used_web: boolean; ideas: Idea[] }>(
      `/ideas/generate?n=${n}&focus=${focus}`,
      { method: "POST", body: "{}" },
    ),
  saveIdea: (id: number) =>
    req<Idea>(`/ideas/${id}/save`, { method: "POST", body: "{}" }),
  dismissIdea: (id: number) =>
    req<Idea>(`/ideas/${id}/dismiss`, { method: "POST", body: "{}" }),
  jobs: (includeDismissed = false) =>
    req<Job[]>(`/jobs${includeDismissed ? "?include_dismissed=true" : ""}`),
  scoutJobs: (n = 8) =>
    req<{ found: number; date: string; used_web: boolean; jobs: Job[] }>(
      `/jobs/scout?n=${n}`,
      { method: "POST", body: "{}" },
    ),
  saveJob: (id: number) =>
    req<Job>(`/jobs/${id}/save`, { method: "POST", body: "{}" }),
  dismissJob: (id: number) =>
    req<Job>(`/jobs/${id}/dismiss`, { method: "POST", body: "{}" }),
  events: (city?: string, includeDismissed = false) => {
    const params = new URLSearchParams();
    if (city) params.set("city", city);
    if (includeDismissed) params.set("include_dismissed", "true");
    const qs = params.toString();
    return req<Event[]>(`/events${qs ? `?${qs}` : ""}`);
  },
  scoutEvents: (city: string, n = 10) =>
    req<{ found: number; city: string; date: string; used_web: boolean; events: Event[] }>(
      `/events/scout?city=${encodeURIComponent(city)}&n=${n}`,
      { method: "POST", body: "{}" },
    ),
  saveEvent: (id: number) =>
    req<Event>(`/events/${id}/save`, { method: "POST", body: "{}" }),
  dismissEvent: (id: number) =>
    req<Event>(`/events/${id}/dismiss`, { method: "POST", body: "{}" }),

  // research agent
  research: () => req<Topic[]>("/research"),
  researchBrief: () => req<Brief | null>("/research/brief"),
  runBrief: () =>
    req<{ day: string; for_you: string; ventures: string; pushed: unknown }>(
      "/research/brief/run",
      { method: "POST", body: "{}" },
    ),
  addTopic: (query: string, cadence: "once" | "daily", track: "you" | "venture", runNow = true) =>
    req<Topic>("/research/topics", {
      method: "POST",
      body: JSON.stringify({ query, cadence, track, run_now: runNow }),
    }),
  runTopic: (id: number) => req<Topic>(`/research/${id}/run`, { method: "POST", body: "{}" }),
  archiveTopic: (id: number) =>
    req<Topic>(`/research/${id}/archive`, { method: "POST", body: "{}" }),
  deleteTopic: (id: number) =>
    req<{ deleted: number }>(`/research/${id}`, { method: "DELETE" }),
  saveFinding: (id: number) =>
    req<Finding>(`/research/findings/${id}/save`, { method: "POST", body: "{}" }),
  dismissFinding: (id: number) =>
    req<Finding>(`/research/findings/${id}/dismiss`, { method: "POST", body: "{}" }),

  // habits + journal
  habits: (days = 30) => req<Habit[]>(`/habits?days=${days}`),
  createHabit: (name: string, emoji: string) =>
    req<Habit>("/habits", { method: "POST", body: JSON.stringify({ name, emoji }) }),
  toggleHabit: (id: number, day?: string) =>
    req<Habit>(`/habits/${id}/toggle${day ? `?day=${day}` : ""}`, { method: "POST", body: "{}" }),
  deleteHabit: (id: number) =>
    req<{ archived: number }>(`/habits/${id}`, { method: "DELETE" }),
  getJournal: (day: string) => req<JournalEntry>(`/journal/${day}`),
  putJournal: (day: string, text: string, mood: string) =>
    req<JournalEntry>(`/journal/${day}`, {
      method: "PUT",
      body: JSON.stringify({ text, mood }),
    }),
  journalRecent: (limit = 14) => req<JournalEntry[]>(`/journal?limit=${limit}`),

  // second brain
  notes: () => req<Note[]>("/notes"),
  addNote: (n: { kind: "note" | "bookmark"; title?: string; content?: string; url?: string; tags?: string }) =>
    req<Note>("/notes", { method: "POST", body: JSON.stringify(n) }),
  deleteNote: (id: number) =>
    req<{ deleted: number }>(`/notes/${id}`, { method: "DELETE" }),
  brainAsk: (question: string) =>
    req<BrainAnswer>("/brain/ask", { method: "POST", body: JSON.stringify({ question }) }),

  // notifications
  notifyStatus: () => req<{ channels: string[] }>("/notify/status"),
  notifyTest: () => req<{ channels: string[]; sent: string[]; failed: string[] }>("/notify/test", { method: "POST", body: "{}" }),

  founder: () => req<{ profile: string }>("/founder"),
  saveFounder: (profile: string) =>
    req<{ profile: string }>("/founder", {
      method: "PUT",
      body: JSON.stringify({ profile }),
    }),

  automations: () => req<Automations>("/settings/automations"),
  saveAutomations: (a: Automations) =>
    req<Automations>("/settings/automations", {
      method: "PUT",
      body: JSON.stringify(a),
    }),
};

export interface Automations {
  ideas: boolean;
  jobs: boolean;
  research: boolean;
}

export interface Job {
  id: number;
  found_date: string;
  title: string;
  company: string;
  location: string;
  comp: string;
  url: string;
  fit_score: number;
  trajectory: number;
  why_fit: string;
  why_step_up: string;
  readiness: string;
  watch_outs: string;
  source: string;
  status: "new" | "saved" | "dismissed";
  created_at: string;
}

export interface Event {
  id: number;
  found_date: string;
  city: string;
  title: string;
  category: string;
  venue: string;
  when: string;
  deadline: string;
  price: string;
  url: string;
  fit_score: number;
  why_fit: string;
  description: string;
  source: string;
  status: "new" | "saved" | "dismissed";
  created_at: string;
}

export type IdeaFocus = "balanced" | "core" | "adjacent" | "broad" | "wildcard";

export interface Idea {
  id: number;
  created_date: string;
  title: string;
  pitch: string;
  domain: string;
  score: number;
  why_now: string;
  why_you: string;
  first_step: string;
  market: string;
  signal: string;
  status: "new" | "saved" | "dismissed";
  created_at: string;
}

export interface Finding {
  id: number;
  title: string;
  detail: string;
  why_matters: string;
  url: string;
  source: string;
  importance: number;
  status: "new" | "saved" | "dismissed";
  run_date: string;
}

export interface Topic {
  id: number;
  query: string;
  track: "you" | "venture";
  cadence: "once" | "daily";
  status: "queued" | "running" | "done" | "error";
  last_summary: string;
  last_error: string;
  last_run_at: string | null;
  findings: Finding[];
}

export interface Brief {
  day: string;
  for_you: string;
  ventures: string;
}

export interface Habit {
  id: number;
  name: string;
  emoji: string;
  streak: number;
  days: string[];
}

export interface JournalEntry {
  day: string;
  text: string;
  mood: string;
}

export interface Note {
  id: number;
  kind: "note" | "bookmark";
  title: string;
  content: string;
  url: string;
  tags: string;
  created_at: string;
}

export interface BrainAnswer {
  answer: string;
  sources: { id: number; kind: string; title: string; url: string }[];
}

export type HighlightTag = "research" | "tools" | "money" | "security" | "event" | "admin";

export interface Highlight {
  title: string;
  detail: string;
  tag: HighlightTag;
}

export interface Briefing {
  highlights: Highlight[];
  threads: number;
  generated_at: string;
}

export interface Standings {
  standings: Record<string, { standing: string; next: string | null }>;
  generated_at: string;
}

export interface AgendaItem {
  id: number;
  title: string | null;
  why?: string | null;
  note?: string | null;
  deadline?: string | null;
}

export interface Deadline {
  id: number;
  title: string | null;
  date: string | null;
}

export interface Waiting {
  id: number;
  title: string;
  sender: string;
  days: number;
}

export interface Agenda {
  headline: string;
  urgent: AgendaItem[];
  reply_queue: AgendaItem[];
  fyi: AgendaItem[];
  deadlines: Deadline[];
  waiting: Waiting[];
  generated_at: string;
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "now";
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
