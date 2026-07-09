"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type BrainAnswer, type Note } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";
import Emphasize from "./Emphasize";

export default function SecondBrainPane() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<BrainAnswer | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [kind, setKind] = useState<"note" | "bookmark">("note");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [tags, setTags] = useState("");

  const load = useCallback(async () => {
    try {
      setNotes(await api.notes());
    } catch {
      /* surfaced on add */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const ask = async () => {
    const q = question.trim();
    if (q.length < 2 || asking) return;
    setAsking(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await api.brainAsk(q));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ask failed");
    } finally {
      setAsking(false);
    }
  };

  const add = async () => {
    if (!title.trim() && !content.trim() && !url.trim()) return;
    try {
      const n = await api.addNote({ kind, title, content, url, tags });
      setNotes((prev) => [n, ...prev]);
      setTitle(""); setContent(""); setUrl(""); setTags("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
    }
  };

  const remove = async (id: number) => {
    await api.deleteNote(id);
    setNotes((prev) => prev.filter((n) => n.id !== id));
  };

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-[900px]">
        <PageHeader
          eyebrow="Second brain"
          title="Ask your own notes"
          subtitle="Save notes & bookmarks, then ask questions over them. Answers are grounded only in your material, with citations — it won't make things up."
        />

        {/* ask */}
        <div className="card mb-4 flex items-center gap-2 p-4">
          <Icon.brain size={16} className="shrink-0 text-amber" />
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="What did I note about…?"
            className="min-w-0 flex-1 bg-transparent text-[14px] text-ink placeholder:text-faint focus:outline-none"
          />
          <button onClick={ask} disabled={asking || question.trim().length < 2} className="btn btn-primary">
            {asking ? <Icon.sync size={14} className="spin" /> : <Icon.arrow size={14} />}
            {asking ? "Thinking…" : "Ask"}
          </button>
        </div>

        {error && <p className="mb-4 text-sm text-red">{error}</p>}

        {answer && (
          <div className="card mb-6 p-5">
            <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink"><Emphasize>{answer.answer}</Emphasize></p>
            {answer.sources.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2 border-t border-hairline pt-3">
                {answer.sources.map((s) => (
                  <span key={s.id} className="inline-flex items-center gap-1 rounded-md border border-hairline-strong px-2 py-0.5 font-mono text-[10px] text-muted">
                    <span className="text-faint">#{s.id}</span>
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-blue hover:underline">{s.title}</a>
                    ) : (
                      s.title
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* add note / bookmark */}
        <section className="card mb-6 p-5">
          <div className="mb-3 flex rounded-lg border border-hairline-strong p-0.5">
            {(["note", "bookmark"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={`flex-1 rounded-md px-3 py-1 text-[12px] capitalize transition-colors ${
                  kind === k ? "bg-amber text-white" : "text-muted hover:text-ink"
                }`}
              >
                {k}
              </button>
            ))}
          </div>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title (optional)"
            className="mb-2 w-full rounded-lg border border-hairline-strong bg-panel px-3 py-2 text-[13px] text-ink placeholder:text-faint focus:border-amber focus:outline-none"
          />
          {kind === "bookmark" && (
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
              className="mb-2 w-full rounded-lg border border-hairline-strong bg-panel px-3 py-2 font-mono text-[12px] text-ink placeholder:text-faint focus:border-amber focus:outline-none"
            />
          )}
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={kind === "bookmark" ? "Why you saved it / key takeaways…" : "Write your note… (this is what gets searched)"}
            rows={4}
            className="mb-2 w-full resize-none rounded-lg border border-hairline-strong bg-panel px-3 py-2 text-[13px] leading-relaxed text-ink placeholder:text-faint focus:border-amber focus:outline-none"
          />
          <div className="flex items-center gap-2">
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="tags, comma, separated"
              className="min-w-0 flex-1 rounded-lg border border-hairline-strong bg-panel px-3 py-1.5 font-mono text-[11.5px] text-ink placeholder:text-faint focus:border-amber focus:outline-none"
            />
            <button onClick={add} className="btn btn-outline"><Icon.plus size={13} /> save</button>
          </div>
        </section>

        {/* corpus */}
        <h2 className="mb-2 px-1 font-mono text-[10.5px] uppercase tracking-[0.15em] text-faint">
          {notes.length} item{notes.length !== 1 ? "s" : ""} in your brain
        </h2>
        <div className="space-y-2">
          {notes.map((n) => (
            <div key={n.id} className="group card flex items-start gap-3 p-4">
              <Icon.book size={15} className="mt-0.5 shrink-0 text-faint" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[9px] uppercase tracking-wide text-faint">#{n.id} · {n.kind}</span>
                  {n.title && <span className="truncate text-[13px] font-medium text-ink">{n.title}</span>}
                </div>
                {n.content && <p className="mt-0.5 line-clamp-3 whitespace-pre-wrap text-[12.5px] leading-relaxed text-muted">{n.content}</p>}
                {n.url && (
                  <a href={n.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 truncate font-mono text-[10.5px] text-blue hover:underline">
                    {n.url} <Icon.external size={10} />
                  </a>
                )}
                {n.tags && <div className="mt-1 font-mono text-[10px] text-faint">{n.tags}</div>}
              </div>
              <button onClick={() => remove(n.id)} className="rounded p-1 text-faint opacity-0 transition-opacity hover:text-red group-hover:opacity-100">
                <Icon.trash size={13} />
              </button>
            </div>
          ))}
          {notes.length === 0 && (
            <div className="rounded-xl border border-dashed border-hairline-strong px-6 py-12 text-center">
              <p className="text-sm text-muted">Your brain is empty.</p>
              <p className="mt-1.5 text-xs text-faint">Add notes or bookmarks above, then ask questions over them.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
