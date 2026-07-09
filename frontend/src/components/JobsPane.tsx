"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Job } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";
import { EmptyState, Field, SkeletonGrid } from "./IdeasPane";

export default function JobsPane() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [scouting, setScouting] = useState(false);
  const [tab, setTab] = useState<"fresh" | "saved">("fresh");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setJobs(await api.jobs());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const scout = async () => {
    setScouting(true);
    setError(null);
    try {
      const r = await api.scoutJobs(8);
      setJobs((prev) => [...r.jobs, ...prev]);
      setTab("fresh");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scouting failed");
    } finally {
      setScouting(false);
    }
  };

  const act = async (id: number, fn: (id: number) => Promise<Job>) => {
    const updated = await fn(id);
    setJobs((prev) => prev.map((j) => (j.id === id ? updated : j)));
  };

  const fresh = jobs.filter((j) => j.status === "new");
  const saved = jobs.filter((j) => j.status === "saved");
  const shown = tab === "saved" ? saved : fresh;

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-[1400px]">
        <PageHeader
          eyebrow="Career scout"
          title="Roles worth your move"
          subtitle="Live-scouted openings scored on two axes: how well they fit your profile, and their long-term career value — equity, signal and optionality, not lateral moves."
          actions={
            <button onClick={scout} disabled={scouting} className="btn btn-primary">
              <Icon.compass size={14} className={scouting ? "spin" : ""} />
              {scouting ? "Scouting…" : "Scout jobs"}
            </button>
          }
        />

        <div className="mb-5 flex items-center gap-1 border-b border-hairline">
          <Tab active={tab === "fresh"} onClick={() => setTab("fresh")} label="Fresh" n={fresh.length} />
          <Tab active={tab === "saved"} onClick={() => setTab("saved")} label="Saved" n={saved.length} />
        </div>

        {error && <p className="mb-4 text-sm text-red">{error}</p>}

        {scouting && (
          <div className="card mb-4 flex items-center gap-2.5 border-amber-dim/40 px-5 py-3.5 text-[13px] text-amber">
            <Icon.compass size={15} className="spin" />
            Searching career pages, LinkedIn and comp benchmarks for roles that fit you…
          </div>
        )}

        {loading && jobs.length === 0 ? (
          <SkeletonGrid />
        ) : shown.length === 0 ? (
          <EmptyState
            label={tab === "saved" ? "No saved roles yet." : "No roles scouted yet."}
            hint="Scout jobs to find your next step up."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {shown.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onSave={() => act(job.id, api.saveJob)}
                onDismiss={() => act(job.id, api.dismissJob)}
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

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <span className="flex items-center gap-1.5" title={`${label}: ${value}/5`}>
      <span className="font-mono text-[9px] uppercase tracking-wide text-faint">{label}</span>
      <span className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className={`dot ${n <= value ? "bg-amber" : "bg-hairline-strong"}`} />
        ))}
      </span>
    </span>
  );
}

function JobCard({
  job,
  onSave,
  onDismiss,
}: {
  job: Job;
  onSave: () => void;
  onDismiss: () => void;
}) {
  return (
    <article className="card card-hover fade-up flex flex-col p-5">
      <div>
        <h2 className="display text-[1.2rem] leading-snug text-ink">{job.title}</h2>
        <p className="mt-0.5 text-[12.5px] text-muted">
          <span className="text-ink/80">{job.company || "—"}</span>
          {job.location && <span className="text-faint"> · {job.location}</span>}
        </p>
        {job.comp && (
          <span className="mt-2 inline-block rounded-lg border border-green/40 bg-green/[0.08] px-2.5 py-1 font-mono text-[11px] text-green">
            {job.comp}
          </span>
        )}
      </div>

      <div className="mt-3 flex items-center gap-4">
        <Meter label="fit" value={job.fit_score} />
        <Meter label="long-term" value={job.trajectory} />
      </div>

      <div className="mt-3.5 space-y-2 text-[12px] leading-relaxed">
        <Field label="Why you fit" tone="blue">{job.why_fit}</Field>
        <Field label="Long-term" tone="amber">{job.why_step_up}</Field>
        {job.readiness && <Field label="To land it" tone="green">{job.readiness}</Field>}
        {job.watch_outs && <Field label="Watch-outs" tone="red">{job.watch_outs}</Field>}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-hairline pt-3">
        {job.url ? (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 truncate pr-3 font-mono text-[10.5px] text-blue hover:underline"
          >
            view posting <Icon.external size={11} />
          </a>
        ) : (
          <span className="truncate pr-3 font-mono text-[10px] text-faint">{job.source}</span>
        )}
        {job.status === "saved" ? (
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
