"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api,
  type Agenda,
  type AgendaItem,
  type Highlight,
  type HighlightTag,
  type Project,
  type Standings,
  type Thread,
} from "@/lib/api";
import { Icon, type IconName } from "./Icons";
import Emphasize from "./Emphasize";

/* The command deck — full-page overview. Each card answers one question:
   what's on fire · what to reply · what's interesting · what to note ·
   where each project stands. */

const TAG_STYLES: Record<HighlightTag, string> = {
  research: "text-blue border-blue/40",
  tools: "text-muted border-hairline-strong",
  money: "text-amber border-amber-dim",
  security: "text-red border-red/40",
  event: "text-green border-green/40",
  admin: "text-faint border-hairline",
};

export default function HomeDashboard({
  threads,
  projects,
  onOpenThread,
  onOpenProject,
  onOpenBriefing,
  onStateChanged,
}: {
  threads: Thread[];
  projects: Project[];
  onOpenThread: (id: number) => void;
  onOpenProject: (id: number) => void;
  onOpenBriefing: () => void;
  onStateChanged: () => void;
}) {
  const [agenda, setAgenda] = useState<Agenda | null>(null);
  const [agendaLoading, setAgendaLoading] = useState(false);
  const [highlights, setHighlights] = useState<Highlight[] | null>(null);
  const [standings, setStandings] = useState<Standings["standings"] | null>(null);
  const [standingsLoading, setStandingsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAgenda = useCallback(async (refresh: boolean) => {
    setAgendaLoading(true);
    setError(null);
    try {
      setAgenda(await api.agenda(refresh));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Agenda failed");
    } finally {
      setAgendaLoading(false);
    }
  }, []);

  const loadBriefing = useCallback(async (refresh: boolean) => {
    try {
      setHighlights((await api.digest(refresh)).highlights);
    } catch {
      setHighlights(null);
    }
  }, []);

  const loadStandings = useCallback(async (refresh: boolean) => {
    setStandingsLoading(true);
    try {
      setStandings((await api.standing(refresh)).standings);
    } catch {
      setStandings(null);
    } finally {
      setStandingsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgenda(false);
    loadBriefing(false);
    loadStandings(false);
  }, [loadAgenda, loadBriefing, loadStandings]);

  const removeFromAgenda = (id: number) =>
    setAgenda((a) =>
      a
        ? {
            ...a,
            urgent: a.urgent.filter((it) => it.id !== id),
            reply_queue: a.reply_queue.filter((it) => it.id !== id),
            fyi: a.fyi.filter((it) => it.id !== id),
          }
        : a,
    );

  const snooze = useCallback(async (id: number) => {
    try {
      await api.snooze(id);
      removeFromAgenda(id);
    } catch {}
  }, []);

  const complete = useCallback(
    async (id: number) => {
      removeFromAgenda(id);
      try {
        await api.done(id);
        onStateChanged();
      } catch {
        loadAgenda(false);
      }
    },
    [onStateChanged, loadAgenda],
  );

  const drafted = threads.filter((t) => t.status === "drafted").length;
  const owed = threads.filter((t) => t.status === "needs_reply").length;
  const filtered = threads.filter((t) => t.status === "ignored").length;
  const sent = threads.filter((t) => t.status === "sent").length;
  const workProjects = projects
    .filter((p) => !p.digest)
    .sort((a, b) => b.needs_attention - a.needs_attention || b.thread_count - a.thread_count);

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-[1500px]">
        {/* headline */}
        <header className="mb-6 flex items-end justify-between gap-6">
          <div className="min-w-0">
            <div className="eyebrow">
              {new Date().toLocaleDateString(undefined, {
                weekday: "long",
                month: "long",
                day: "numeric",
              })}
            </div>
            <h1 className="display mt-1.5 text-[1.75rem] leading-snug text-ink">
              {agenda?.headline ? <Emphasize>{agenda.headline}</Emphasize> : agendaLoading ? "Sizing up your day…" : "Your day"}
            </h1>
          </div>
          <button
            onClick={() => {
              loadAgenda(true);
              loadStandings(true);
            }}
            disabled={agendaLoading}
            className="btn btn-outline"
          >
            <Icon.sync size={13} className={agendaLoading ? "spin" : ""} />
            refresh
          </button>
        </header>

        {error && <p className="mb-4 text-sm text-red">{error}</p>}

        {/* stat row */}
        <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat icon="send" value={drafted} label="drafts ready" hot={drafted > 0} />
          <Stat icon="mail" value={owed} label="replies owed" hot={owed > 0} />
          <Stat icon="check" value={sent} label="replies sent" />
          <Stat icon="feed" value={filtered} label="junk filtered" dim />
        </div>

        {/* widget grid */}
        <div className="grid grid-cols-12 gap-4">
          <Box title="Urgent" icon="bell" tone="amber" hint="tick when handled" className="col-span-12 xl:col-span-6" meta={agenda?.urgent.length}>
            {agenda && agenda.urgent.length > 0 ? (
              agenda.urgent.map((it) => (
                <Item key={it.id} item={it} urgent onClick={() => onOpenThread(it.id)} onDone={() => complete(it.id)} onSnooze={() => snooze(it.id)} />
              ))
            ) : (
              <Empty>{agendaLoading ? "Checking…" : "No fires. Clear skies. ✈"}</Empty>
            )}
          </Box>

          <Box title="Reply queue" icon="mail" hint="drafts written — review & send" className="col-span-12 xl:col-span-6" meta={agenda?.reply_queue.length}>
            {agenda && agenda.reply_queue.length > 0 ? (
              agenda.reply_queue.map((it) => (
                <Item key={it.id} item={it} onClick={() => onOpenThread(it.id)} onDone={() => complete(it.id)} onSnooze={() => snooze(it.id)} />
              ))
            ) : (
              <Empty>{agendaLoading ? "Checking…" : "Nothing waiting on a reply."}</Empty>
            )}
          </Box>

          <Box title="Briefing" icon="sparkle" hint="feeds, distilled" className="col-span-12 xl:col-span-7">
            {highlights === null ? (
              <Empty>Loading…</Empty>
            ) : highlights.length === 0 ? (
              <Empty>Nothing worth your attention in the feeds.</Empty>
            ) : (
              highlights.map((h, i) => (
                <button key={i} onClick={onOpenBriefing} className="block w-full rounded-lg px-3 py-2 text-left transition-colors hover:bg-raised">
                  <span className="flex items-center gap-2">
                    <span className={`shrink-0 rounded border px-1.5 py-px font-mono text-[8.5px] uppercase tracking-wide ${TAG_STYLES[h.tag] ?? TAG_STYLES.admin}`}>
                      {h.tag}
                    </span>
                    <span className="truncate text-[13px] font-medium text-ink/90">{h.title}</span>
                  </span>
                  <p className="mt-0.5 pl-[52px] text-[11.5px] leading-snug text-faint"><Emphasize>{h.detail}</Emphasize></p>
                </button>
              ))
            )}
          </Box>

          <Box title="Notices" icon="inbox" hint="accounts & housekeeping" className="col-span-12 xl:col-span-5" meta={agenda?.fyi.length}>
            {agenda && agenda.fyi.length > 0 ? (
              agenda.fyi.map((it) => (
                <div key={it.id} onClick={() => onOpenThread(it.id)} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onOpenThread(it.id)} className="group flex w-full cursor-pointer items-start justify-between gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-raised">
                  <span className="min-w-0">
                    <span className="text-[12.5px] text-ink/85">{it.title}</span>
                    {it.note && <span className="ml-2 text-[11.5px] text-faint"><Emphasize>{it.note}</Emphasize></span>}
                  </span>
                  <button onClick={(e) => { e.stopPropagation(); complete(it.id); }} title="Handled" className="shrink-0 rounded p-0.5 text-faint opacity-0 transition-opacity hover:text-green group-hover:opacity-100">
                    <Icon.check size={13} />
                  </button>
                </div>
              ))
            ) : (
              <Empty>{agendaLoading ? "Checking…" : "No notices."}</Empty>
            )}
          </Box>

          <Box title="Upcoming" icon="bell" hint="deadlines from your mail" className="col-span-12 xl:col-span-7" meta={agenda?.deadlines.length}>
            {agenda && agenda.deadlines.length > 0 ? (
              [...agenda.deadlines]
                .sort((a, b) => String(a.date).localeCompare(String(b.date)))
                .map((d) => {
                  const when = deadlineWhen(d.date);
                  return (
                    <button key={d.id} onClick={() => onOpenThread(d.id)} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-raised">
                      <span className={`shrink-0 rounded border px-1.5 py-px font-mono text-[10px] ${when.cls}`}>{when.label}</span>
                      <span className="truncate text-[12.5px] text-ink/85">{d.title}</span>
                    </button>
                  );
                })
            ) : (
              <Empty>{agendaLoading ? "Checking…" : "No upcoming deadlines."}</Empty>
            )}
          </Box>

          <Box title="Waiting on" icon="send" hint="you replied — no answer yet" className="col-span-12 xl:col-span-5" meta={agenda?.waiting.length}>
            {agenda && agenda.waiting.length > 0 ? (
              agenda.waiting.map((w) => (
                <button key={w.id} onClick={() => onOpenThread(w.id)} className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-raised">
                  <span className="min-w-0">
                    <span className="block truncate text-[12.5px] text-ink/85">{w.title}</span>
                    <span className="font-mono text-[10px] text-faint">{w.sender}</span>
                  </span>
                  <span className={`shrink-0 rounded-full px-1.5 font-mono text-[10px] ${w.days >= 4 ? "bg-amber/15 text-amber" : "text-faint"}`}>
                    {w.days === 0 ? "today" : `${w.days}d`}
                  </span>
                </button>
              ))
            ) : (
              <Empty>Not waiting on anyone.</Empty>
            )}
          </Box>

          <Box title="Projects" icon="folder" hint="current standing" className="col-span-12" action={
            <button onClick={() => loadStandings(true)} disabled={standingsLoading} className="text-faint transition-colors hover:text-amber disabled:opacity-50">
              <Icon.sync size={12} className={standingsLoading ? "spin" : ""} />
            </button>
          }>
            <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
              {workProjects.map((p) => {
                const s = standings?.[String(p.id)];
                return (
                  <button key={p.id} onClick={() => onOpenProject(p.id)} className="card card-hover px-4 py-3 text-left">
                    <div className="flex items-center justify-between gap-3">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className={`dot ${p.needs_attention > 0 ? "bg-amber" : "bg-hairline-strong"}`} />
                        <span className="truncate text-[13px] font-medium text-ink">{p.name}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2 font-mono text-[10px]">
                        {p.needs_attention > 0 && <span className="rounded-full bg-amber/15 px-1.5 text-amber">{p.needs_attention} to do</span>}
                        <span className="text-faint">{p.thread_count}</span>
                      </span>
                    </div>
                    <p className="mt-1.5 text-[12px] leading-snug text-muted">
                      {s ? <Emphasize>{s.standing}</Emphasize> : standingsLoading ? "Assessing…" : "—"}
                    </p>
                    {s?.next && <p className="mt-1 flex items-start gap-1 text-[11.5px] text-amber/90"><Icon.arrow size={11} className="mt-0.5 shrink-0" /><span><Emphasize>{s.next}</Emphasize></span></p>}
                  </button>
                );
              })}
            </div>
            {workProjects.length === 0 && <Empty>No projects yet.</Empty>}
          </Box>
        </div>
      </div>
    </div>
  );
}

/* relative label + color for a deadline date string (ISO or free text) */
function deadlineWhen(date: string | null): { label: string; cls: string } {
  if (!date) return { label: "soon", cls: "border-hairline-strong text-muted" };
  const d = new Date(date);
  if (isNaN(d.getTime())) return { label: date.slice(0, 14), cls: "border-hairline-strong text-muted" };
  const days = Math.ceil((d.getTime() - Date.now()) / 86_400_000);
  const label =
    days < 0 ? "overdue" : days === 0 ? "today" : days === 1 ? "tomorrow" : `${days}d`;
  const cls =
    days < 0
      ? "border-red/50 text-red"
      : days <= 3
        ? "border-amber-dim bg-amber/10 text-amber"
        : "border-hairline-strong text-muted";
  return { label, cls };
}

/* ── primitives ─────────────────────────────────────────────── */

function Stat({ icon, value, label, hot, dim }: { icon: IconName; value: number; label: string; hot?: boolean; dim?: boolean }) {
  const Glyph = Icon[icon];
  return (
    <div className={`card flex items-center justify-between px-5 py-4 ${hot ? "border-amber-dim/50" : ""}`}>
      <div>
        <div className={`display text-[1.9rem] leading-none ${hot ? "text-amber" : dim ? "text-faint" : "text-ink"}`}>{value}</div>
        <div className="mt-1.5 font-mono text-[9.5px] uppercase tracking-[0.13em] text-faint">{label}</div>
      </div>
      <Glyph size={20} className={hot ? "text-amber/70" : "text-faint"} />
    </div>
  );
}

function Box({ title, icon, tone, meta, hint, action, className, children }: {
  title: string; icon: IconName; tone?: "amber"; meta?: number; hint?: string; action?: React.ReactNode; className?: string; children: React.ReactNode;
}) {
  const Glyph = Icon[icon];
  return (
    <section className={`card flex flex-col ${tone === "amber" ? "border-amber-dim/40" : ""} ${className ?? ""}`}>
      <header className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
        <span className="flex items-center gap-2">
          <Glyph size={14} className={tone === "amber" ? "text-amber" : "text-faint"} />
          <h2 className={`font-mono text-[10.5px] uppercase tracking-[0.15em] ${tone === "amber" ? "text-amber" : "text-muted"}`}>{title}</h2>
          {hint && <span className="text-[11px] text-faint">{hint}</span>}
        </span>
        <span className="flex items-center gap-3">
          {action}
          {meta != null && <span className="font-mono text-[10.5px] text-faint">{meta}</span>}
        </span>
      </header>
      <div className="max-h-[340px] flex-1 space-y-1 overflow-y-auto p-2.5">{children}</div>
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="px-3 py-7 text-center text-[12.5px] text-faint">{children}</p>;
}

function Item({ item, urgent, onClick, onDone, onSnooze }: {
  item: AgendaItem; urgent?: boolean; onClick: () => void; onDone?: () => void; onSnooze?: () => void;
}) {
  return (
    <div onClick={onClick} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onClick()}
      className={`fade-up group flex w-full cursor-pointer items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
        urgent ? "border-amber-dim/40 bg-amber/[0.04] hover:bg-amber/[0.08]" : "border-hairline bg-raised/30 hover:bg-raised"
      }`}>
      {onDone && (
        <button onClick={(e) => { e.stopPropagation(); onDone(); }} title="Mark as handled"
          className="mt-0.5 flex h-[17px] w-[17px] shrink-0 items-center justify-center rounded-full border border-hairline-strong text-transparent transition-colors hover:border-green hover:text-green">
          <Icon.check size={10} />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-medium text-ink">{item.title}</span>
          <span className="flex shrink-0 items-center gap-2">
            {item.deadline && (
              <span className="rounded border border-amber-dim bg-amber/10 px-1.5 py-px font-mono text-[10px] uppercase tracking-wide text-amber">{item.deadline}</span>
            )}
            {onSnooze && (
              <button onClick={(e) => { e.stopPropagation(); onSnooze(); }} title="Not today" className="rounded px-1 font-mono text-[10.5px] text-faint opacity-0 transition-opacity hover:text-muted group-hover:opacity-100">zzz</button>
            )}
          </span>
        </div>
        {item.why && <p className="mt-0.5 text-[11.5px] text-muted"><Emphasize>{item.why}</Emphasize></p>}
      </div>
    </div>
  );
}
