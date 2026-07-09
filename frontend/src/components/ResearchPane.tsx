"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Brief, type Finding, type Topic } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";
import Emphasize, { emphasize } from "./Emphasize";
import { EmptyState, Field } from "./IdeasPane";

// Render one brief bullet: pull out markdown [label](url) links, emphasize the rest.
function renderLine(line: string, key: number) {
  const parts: React.ReactNode[] = [];
  const re = /\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) parts.push(<span key={i++}>{emphasize(line.slice(last, m.index))}</span>);
    parts.push(
      <a key={i++} href={m[2]} target="_blank" rel="noopener noreferrer" className="text-blue hover:underline">
        {m[1]}
      </a>,
    );
    last = m.index + m[0].length;
  }
  if (last < line.length) parts.push(<span key={i++}>{emphasize(line.slice(last))}</span>);
  return <p key={key} className="text-[12.5px] leading-relaxed text-muted">{parts}</p>;
}

export default function ResearchPane() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [cadence, setCadence] = useState<"once" | "daily">("daily");
  const [track, setTrack] = useState<"you" | "venture">("you");
  const [running, setRunning] = useState(false);
  const [briefing, setBriefing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, b] = await Promise.all([api.research(), api.researchBrief()]);
      setTopics(t);
      setBrief(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load research");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    const q = query.trim();
    if (q.length < 3 || running) return;
    setRunning(true);
    setError(null);
    try {
      const t = await api.addTopic(q, cadence, track, true);
      setTopics((prev) => [t, ...prev.filter((p) => p.id !== t.id)]);
      setQuery("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Research failed");
    } finally {
      setRunning(false);
    }
  };

  const generateBrief = async () => {
    setBriefing(true);
    setError(null);
    try {
      const b = await api.runBrief();
      setBrief({ day: b.day, for_you: b.for_you, ventures: b.ventures });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Brief failed");
    } finally {
      setBriefing(false);
    }
  };

  const rerun = async (id: number) => {
    setTopics((prev) => prev.map((t) => (t.id === id ? { ...t, status: "running" } : t)));
    try {
      const t = await api.runTopic(id);
      setTopics((prev) => prev.map((p) => (p.id === id ? t : p)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
      load();
    }
  };

  const archive = async (id: number) => {
    await api.archiveTopic(id);
    setTopics((prev) => prev.filter((t) => t.id !== id));
  };

  const actFinding = async (topicId: number, fid: number, fn: (id: number) => Promise<Finding>) => {
    const updated = await fn(fid);
    setTopics((prev) =>
      prev.map((t) =>
        t.id !== topicId
          ? t
          : { ...t, findings: t.findings.map((f) => (f.id === fid ? updated : f)) },
      ),
    );
  };

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-[1100px]">
        <PageHeader
          eyebrow="Research agent"
          title="Overnight deep-dives"
          subtitle="Drop in a question; the agent searches the open web (papers, filings, industry press) and reports back sourced findings. Daily topics re-run each night and feed your morning brief."
          actions={
            <button onClick={generateBrief} disabled={briefing} className="btn btn-outline">
              <Icon.sync size={13} className={briefing ? "spin" : ""} />
              {briefing ? "Briefing…" : "Generate brief"}
            </button>
          }
        />

        {/* pinned morning brief */}
        {brief && (brief.for_you || brief.ventures) && (
          <div className="card mb-6 p-5">
            <div className="mb-3 flex items-center gap-2">
              <Icon.bell size={14} className="text-amber" />
              <h2 className="font-mono text-[10.5px] uppercase tracking-[0.15em] text-muted">
                Morning brief
              </h2>
              <span className="font-mono text-[10px] text-faint">{brief.day} · pushed to you</span>
            </div>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              {brief.for_you && (
                <div>
                  <h3 className="mb-1.5 text-[12.5px] font-semibold text-ink">🔬 For you</h3>
                  <div className="space-y-1.5">
                    {brief.for_you.split("\n").filter(Boolean).map((l, i) => renderLine(l, i))}
                  </div>
                </div>
              )}
              {brief.ventures && (
                <div>
                  <h3 className="mb-1.5 text-[12.5px] font-semibold text-ink">🚀 Your ventures</h3>
                  <div className="space-y-1.5">
                    {brief.ventures.split("\n").filter(Boolean).map((l, i) => renderLine(l, i))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* add a topic */}
        <div className="card mb-6 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="e.g. a market or research area to track: who's raising, what shipped, what's regulated"
            className="min-w-0 flex-1 rounded-lg border border-hairline-strong bg-panel px-3 py-2 text-[13px] text-ink placeholder:text-faint focus:border-amber focus:outline-none"
          />
          <div className="flex shrink-0 items-center gap-2">
            <div className="flex rounded-lg border border-hairline-strong p-0.5" title="Which section of the brief this feeds">
              {([["you", "For you"], ["venture", "Venture"]] as const).map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setTrack(v)}
                  className={`rounded-md px-2.5 py-1 text-[11.5px] transition-colors ${
                    track === v ? "bg-amber text-white" : "text-muted hover:text-ink"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg border border-hairline-strong p-0.5">
              {(["once", "daily"] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => setCadence(c)}
                  className={`rounded-md px-2.5 py-1 text-[11.5px] capitalize transition-colors ${
                    cadence === c ? "bg-amber text-white" : "text-muted hover:text-ink"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
            <button onClick={add} disabled={running || query.trim().length < 3} className="btn btn-primary">
              <Icon.search size={14} className={running ? "spin" : ""} />
              {running ? "Researching…" : "Research"}
            </button>
          </div>
        </div>

        {error && <p className="mb-4 text-sm text-red">{error}</p>}
        {running && (
          <div className="card mb-4 flex items-center gap-2.5 border-amber-dim/40 px-5 py-3.5 text-[13px] text-amber">
            <Icon.search size={15} className="spin" />
            Searching the web and reading sources — this takes a moment…
          </div>
        )}

        {loading ? (
          <p className="px-1 text-[13px] text-faint">Loading…</p>
        ) : topics.length === 0 ? (
          <EmptyState label="No research topics yet." hint="Add a question above to start your first deep-dive." />
        ) : (
          <div className="space-y-6">
            {topics.map((t) => (
              <TopicBlock
                key={t.id}
                topic={t}
                onRerun={() => rerun(t.id)}
                onArchive={() => archive(t.id)}
                onSave={(fid) => actFinding(t.id, fid, api.saveFinding)}
                onDismiss={(fid) => actFinding(t.id, fid, api.dismissFinding)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const STATUS_STYLE: Record<Topic["status"], string> = {
  queued: "text-faint border-hairline-strong",
  running: "text-amber border-amber-dim",
  done: "text-green border-green/40",
  error: "text-red border-red/40",
};

function TopicBlock({
  topic,
  onRerun,
  onArchive,
  onSave,
  onDismiss,
}: {
  topic: Topic;
  onRerun: () => void;
  onArchive: () => void;
  onSave: (id: number) => void;
  onDismiss: (id: number) => void;
}) {
  const findings = topic.findings.filter((f) => f.status !== "dismissed");
  return (
    <section className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2">
            <span className={`rounded-md border px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-wide ${STATUS_STYLE[topic.status]}`}>
              {topic.status}
            </span>
            <span className="rounded-md border border-hairline-strong px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-wide text-faint">
              {topic.track === "venture" ? "🚀 venture" : "🔬 for you"}
            </span>
            {topic.cadence === "daily" && (
              <span className="font-mono text-[9.5px] uppercase tracking-wide text-faint">· nightly</span>
            )}
          </div>
          <h2 className="display text-[1.15rem] leading-snug text-ink">{topic.query}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <button onClick={onRerun} disabled={topic.status === "running"} title="Run again" className="btn btn-ghost px-2 py-1">
            <Icon.sync size={13} className={topic.status === "running" ? "spin" : ""} />
          </button>
          <button onClick={onArchive} title="Archive" className="btn btn-ghost px-2 py-1">
            <Icon.trash size={13} />
          </button>
        </div>
      </div>

      {topic.last_error && <p className="mt-2 text-[12px] text-red">{topic.last_error}</p>}
      {topic.last_summary && (
        <p className="mt-2 text-[13px] leading-relaxed text-muted"><Emphasize>{topic.last_summary}</Emphasize></p>
      )}

      {findings.length > 0 && (
        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          {findings.map((f) => (
            <FindingCard key={f.id} f={f} onSave={() => onSave(f.id)} onDismiss={() => onDismiss(f.id)} />
          ))}
        </div>
      )}
      {topic.status === "done" && findings.length === 0 && (
        <p className="mt-3 text-[12.5px] text-faint">No findings this run.</p>
      )}
    </section>
  );
}

function FindingCard({ f, onSave, onDismiss }: { f: Finding; onSave: () => void; onDismiss: () => void }) {
  return (
    <article className="fade-up flex flex-col rounded-lg border border-hairline bg-raised/30 p-4">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex shrink-0 gap-0.5" title={`importance ${f.importance}/5`}>
          {[1, 2, 3, 4, 5].map((n) => (
            <span key={n} className={`dot ${n <= f.importance ? "bg-amber" : "bg-hairline-strong"}`} />
          ))}
        </span>
        <h3 className="text-[13.5px] font-medium leading-snug text-ink"><Emphasize>{f.title}</Emphasize></h3>
      </div>
      <div className="mt-2 space-y-1.5 text-[12px] leading-relaxed">
        {f.detail && <p className="text-muted"><Emphasize>{f.detail}</Emphasize></p>}
        {f.why_matters && <Field label="Why" tone="amber">{f.why_matters}</Field>}
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-hairline pt-2.5">
        {f.url ? (
          <a href={f.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 truncate pr-3 font-mono text-[10px] text-blue hover:underline">
            {f.source || "source"} <Icon.external size={10} />
          </a>
        ) : (
          <span className="truncate pr-3 font-mono text-[10px] text-faint">{f.source}</span>
        )}
        {f.status === "saved" ? (
          <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-green"><Icon.star size={10} /> saved</span>
        ) : (
          <span className="flex shrink-0 items-center gap-1.5">
            <button onClick={onDismiss} className="btn btn-ghost px-1.5 py-0.5 font-mono text-[10.5px]">dismiss</button>
            <button onClick={onSave} className="btn rounded-md border border-amber-dim px-2 py-0.5 text-[11px] text-amber hover:bg-amber/10"><Icon.star size={10} /> save</button>
          </span>
        )}
      </div>
    </article>
  );
}
