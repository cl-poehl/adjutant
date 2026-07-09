"use client";

import { useState } from "react";

export default function NewProjectModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string, description: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onCreate(name.trim(), description.trim());
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-base/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="fade-up w-[460px] rounded-2xl border border-hairline-strong bg-overlay p-6"
        style={{ boxShadow: "var(--shadow-pop)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="display text-[1.15rem] text-ink">New project</h2>
        <p className="mt-1 text-[12px] leading-relaxed text-muted">
          The description is what the classifier reads — write it like you&apos;re briefing
          an assistant: <em className="text-ink/80">who emails about this, what it covers, what
          doesn&apos;t belong</em>.
        </p>

        <label className="mt-4 block font-mono text-[10px] uppercase tracking-[0.15em] text-faint">
          Name
        </label>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="e.g. Thesis"
          className="mt-1 w-full rounded-md border border-hairline bg-base/60 px-3 py-2 text-[13px] text-ink placeholder:text-faint focus:border-amber-dim focus:outline-none"
        />

        <label className="mt-3 block font-mono text-[10px] uppercase tracking-[0.15em] text-faint">
          Description <span className="text-amber">· powers classification</span>
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          placeholder="e.g. My master's thesis on distributed systems. Emails from my supervisor Prof. Weber, the examination office, co-authors, and anything about deadlines, drafts, or literature."
          className="mt-1 w-full rounded-md border border-hairline bg-base/60 px-3 py-2 text-[13px] leading-relaxed text-ink placeholder:text-faint focus:border-amber-dim focus:outline-none"
        />

        {error && <p className="mt-2 text-xs text-red">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="btn btn-ghost">
            Cancel
          </button>
          <button onClick={submit} disabled={busy || !name.trim()} className="btn btn-primary">
            {busy ? "Creating…" : "Create project"}
          </button>
        </div>
      </div>
    </div>
  );
}
