"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Highlight, type HighlightTag } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";
import Emphasize from "./Emphasize";

const TAG_STYLES: Record<HighlightTag, string> = {
  research: "text-blue border-blue/40",
  tools: "text-muted border-hairline-strong",
  money: "text-amber border-amber-dim",
  security: "text-red border-red/40",
  event: "text-green border-green/40",
  admin: "text-faint border-hairline",
};

export default function BriefingPane() {
  const [highlights, setHighlights] = useState<Highlight[] | null>(null);
  const [threads, setThreads] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(async (refresh: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.digest(refresh);
      setHighlights(d.highlights);
      setThreads(d.threads);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Briefing failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    generate(false);
  }, [generate]);

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-2xl">
        <PageHeader
          eyebrow="Digest"
          title="Your briefing"
          subtitle="The week's newsletters and feeds, read for you — only what's actually interesting survives."
          actions={
            <button onClick={() => generate(true)} disabled={loading} className="btn btn-outline">
              <Icon.sync size={13} className={loading ? "spin" : ""} />
              {loading ? "reading…" : "regenerate"}
            </button>
          }
        />

        {loading && !highlights && (
          <div className="card flex items-center justify-center gap-2.5 px-6 py-10 text-[13px] text-muted">
            <Icon.sparkle size={16} className="spin text-amber" />
            Skimming your feed mail — distilling what matters…
          </div>
        )}

        {error && <p className="text-sm text-red">{error}</p>}

        {highlights && (
          <div className="space-y-2.5">
            {highlights.length === 0 && !loading && (
              <p className="card px-6 py-10 text-center text-[13px] text-muted">
                Nothing in the feeds is worth your time right now.
              </p>
            )}
            {highlights.map((h, i) => (
              <article key={i} className="card card-hover fade-up px-5 py-4">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`shrink-0 rounded border px-1.5 py-px font-mono text-[9px] uppercase tracking-wide ${TAG_STYLES[h.tag] ?? TAG_STYLES.admin}`}
                  >
                    {h.tag}
                  </span>
                  <h2 className="text-[14px] font-medium text-ink">{h.title}</h2>
                </div>
                <p className="mt-1.5 pl-[2px] text-[13px] leading-relaxed text-muted"><Emphasize>{h.detail}</Emphasize></p>
              </article>
            ))}
            {threads > 0 && (
              <p className="pt-2 text-center font-mono text-[10.5px] text-faint">
                distilled from {threads} threads · the rest was promotional noise
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
