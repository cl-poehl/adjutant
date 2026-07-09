"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Idea, type IdeaFocus } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";
import Emphasize from "./Emphasize";

const FOCUS_OPTIONS: { value: IdeaFocus; label: string }[] = [
  { value: "balanced", label: "Balanced" },
  { value: "core", label: "Core" },
  { value: "adjacent", label: "Adjacent" },
  { value: "broad", label: "Broad" },
  { value: "wildcard", label: "Wildcard" },
];

export default function IdeasPane() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [tab, setTab] = useState<"fresh" | "saved">("fresh");
  const [focus, setFocus] = useState<IdeaFocus>("balanced");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setIdeas(await api.ideas());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load ideas");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const r = await api.generateIdeas(focus, 6);
      setIdeas((prev) => [...r.ideas, ...prev]);
      setTab("fresh");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const act = async (id: number, fn: (id: number) => Promise<Idea>) => {
    const updated = await fn(id);
    setIdeas((prev) => prev.map((i) => (i.id === id ? updated : i)));
  };

  const fresh = ideas.filter((i) => i.status === "new");
  const saved = ideas.filter((i) => i.status === "saved");
  const shown = tab === "saved" ? saved : fresh;

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-[1400px]">
        <PageHeader
          eyebrow="Idea engine"
          title="Startup ideas for you"
          subtitle="Mined from your AI-newsletter feed and live web search, matched to your founder edge. Each rides a current shift — save the ones worth a weekend."
          actions={
            <button onClick={generate} disabled={generating} className="btn btn-primary">
              <Icon.sparkle size={14} className={generating ? "spin" : ""} />
              {generating ? "Scouting…" : "Generate ideas"}
            </button>
          }
        />

        {/* focus segmented control */}
        <div className="mb-4 inline-flex items-center gap-1 rounded-xl border border-hairline bg-panel/60 p-1">
          {FOCUS_OPTIONS.map((o) => (
            <button
              key={o.value}
              onClick={() => setFocus(o.value)}
              className={`rounded-lg px-3 py-1.5 text-[11.5px] transition-colors ${
                focus === o.value ? "bg-raised text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>

        <div className="mb-5 flex items-center gap-1 border-b border-hairline">
          <Tab active={tab === "fresh"} onClick={() => setTab("fresh")} label="Fresh" n={fresh.length} />
          <Tab active={tab === "saved"} onClick={() => setTab("saved")} label="Saved" n={saved.length} />
        </div>

        {error && <p className="mb-4 text-sm text-red">{error}</p>}

        {generating && (
          <div className="card mb-4 flex items-center gap-2.5 border-amber-dim/40 px-5 py-3.5 text-[13px] text-amber">
            <Icon.sparkle size={15} className="spin" />
            Reading the latest signals and searching the web for openings in your areas…
          </div>
        )}

        {loading && ideas.length === 0 ? (
          <SkeletonGrid />
        ) : shown.length === 0 ? (
          <EmptyState
            label={tab === "saved" ? "No saved ideas yet." : "No fresh ideas yet."}
            hint="Generate ideas — the more newsletter signal in your feed, the sharper they get."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {shown.map((idea) => (
              <IdeaCard
                key={idea.id}
                idea={idea}
                onSave={() => act(idea.id, api.saveIdea)}
                onDismiss={() => act(idea.id, api.dismissIdea)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Tab({ active, onClick, label, n }: { active: boolean; onClick: () => void; label: string; n: number }) {
  return (
    <button
      onClick={onClick}
      className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-[12.5px] transition-colors ${
        active ? "border-amber text-ink" : "border-transparent text-muted hover:text-ink"
      }`}
    >
      {label}
      <span className={`font-mono text-[10px] ${active ? "text-amber" : "text-faint"}`}>{n}</span>
    </button>
  );
}

function ScoreDots({ score }: { score: number }) {
  return (
    <span className="flex items-center gap-0.5" title={`${score}/5 fit × timing × buildability`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={`dot ${n <= score ? "bg-amber" : "bg-hairline-strong"}`} />
      ))}
    </span>
  );
}

function IdeaCard({
  idea,
  onSave,
  onDismiss,
}: {
  idea: Idea;
  onSave: () => void;
  onDismiss: () => void;
}) {
  return (
    <article className="card card-hover fade-up flex flex-col p-5">
      <div className="mb-2 flex items-center gap-2">
        {idea.domain && <span className="chip">{idea.domain}</span>}
        <ScoreDots score={idea.score} />
      </div>
      <h2 className="display text-[1.2rem] leading-snug text-ink">{idea.title}</h2>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink/85"><Emphasize>{idea.pitch}</Emphasize></p>

      <div className="mt-3.5 space-y-2 text-[12px] leading-relaxed">
        <Field label="Why now" tone="amber">{idea.why_now}</Field>
        <Field label="Why you" tone="blue">{idea.why_you}</Field>
        <Field label="First wedge" tone="green">{idea.first_step}</Field>
        {idea.market && <Field label="Market">{idea.market}</Field>}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-hairline pt-3">
        <span className="truncate pr-3 font-mono text-[10px] text-faint">{idea.signal}</span>
        {idea.status === "saved" ? (
          <span className="flex shrink-0 items-center gap-1 font-mono text-[10.5px] text-green">
            <Icon.star size={11} /> saved
          </span>
        ) : (
          <span className="flex shrink-0 items-center gap-1.5">
            <button onClick={onDismiss} className="btn btn-ghost px-2 py-1 font-mono text-[11px]">
              dismiss
            </button>
            <button
              onClick={onSave}
              className="btn rounded-md border border-amber-dim px-3 py-1 text-[11.5px] text-amber hover:bg-amber/10"
            >
              <Icon.star size={11} /> save
            </button>
          </span>
        )}
      </div>
    </article>
  );
}

export function Field({
  label,
  tone,
  children,
}: {
  label: string;
  tone?: "amber" | "blue" | "red" | "green";
  children: React.ReactNode;
}) {
  const color =
    tone === "amber"
      ? "text-amber"
      : tone === "blue"
        ? "text-blue"
        : tone === "red"
          ? "text-red"
          : tone === "green"
            ? "text-green"
            : "text-faint";
  return (
    <div className="flex gap-2.5">
      <span className={`w-[72px] shrink-0 font-mono text-[9.5px] uppercase tracking-wide ${color}`}>
        {label}
      </span>
      <span className="text-muted">
        {typeof children === "string" ? <Emphasize>{children}</Emphasize> : children}
      </span>
    </div>
  );
}

export function EmptyState({ label, hint }: { label: string; hint: string }) {
  return (
    <div className="rounded-xl border border-dashed border-hairline-strong px-6 py-14 text-center">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1.5 text-xs text-faint">{hint}</p>
    </div>
  );
}

export function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="card h-52 p-5">
          <div className="skeleton h-3 w-24 rounded" />
          <div className="skeleton mt-3 h-5 w-3/4 rounded" />
          <div className="skeleton mt-3 h-3 w-full rounded" />
          <div className="skeleton mt-2 h-3 w-5/6 rounded" />
        </div>
      ))}
    </div>
  );
}
