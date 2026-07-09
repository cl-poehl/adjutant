"use client";

import { useState } from "react";
import type { Project, Thread } from "@/lib/api";
import { timeAgo } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import { Icon } from "./Icons";
import type { Selection } from "./Sidebar";

const AVATAR_TINTS = [
  "bg-blue/15 text-blue",
  "bg-green/15 text-green",
  "bg-amber/15 text-amber",
  "bg-violet/15 text-violet",
  "bg-red/15 text-red",
];

function avatarFor(name: string): { initials: string; tint: string } {
  const clean = (name || "?").replace(/[<>"]/g, "").trim();
  const parts = clean.split(/[\s@.]+/).filter(Boolean);
  const initials = ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
  let h = 0;
  for (const c of clean) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return { initials, tint: AVATAR_TINTS[h % AVATAR_TINTS.length] };
}

/** Triage order: things waiting on me float to the top. */
const STATUS_ORDER = ["needs_reply", "drafted", "new", "classified", "sent", "ignored"];

export default function ThreadList({
  threads,
  projects,
  selection,
  selectedId,
  onSelect,
  loading,
}: {
  threads: Thread[];
  projects: Project[];
  selection: Selection;
  selectedId: number | null;
  onSelect: (id: number) => void;
  loading: boolean;
}) {
  const [showIgnored, setShowIgnored] = useState(false);

  const projectName = (id: number | null) =>
    id == null ? "Unclassified" : (projects.find((p) => p.id === id)?.name ?? "Unclassified");

  // Junk stays out of sight unless explicitly asked for (digest shows all).
  const ignored = threads.filter((t) => t.status === "ignored");
  const visible =
    showIgnored || selection.kind === "digest"
      ? threads
      : threads.filter((t) => t.status !== "ignored");

  // Group by project on the overview views; otherwise a flat triage list.
  const grouped =
    selection.kind === "all" || selection.kind === "home"
      ? groupBy(visible, (t) => projectName(t.project_id))
      : new Map([["", sortTriage(visible)]]);

  const heading =
    selection.kind === "all" || selection.kind === "home"
      ? "All mail"
      : selection.kind === "unclassified"
        ? "Unclassified"
        : selection.kind === "digest"
          ? "Digest"
          : selection.kind === "project"
            ? projectName(selection.id)
            : "";

  return (
    <section className="glass flex h-full w-[372px] shrink-0 flex-col border-r border-hairline">
      <header className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <h2 className="text-[13px] font-semibold tracking-tight text-ink">{heading}</h2>
        <span className="chip">{visible.length}</span>
      </header>

      <div className="flex-1 overflow-y-auto">
        {loading && threads.length === 0 ? (
          <div className="space-y-2 p-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="flex gap-3 px-1 py-2">
                <div className="skeleton h-8 w-8 shrink-0 rounded-full" />
                <div className="flex-1 space-y-2 py-0.5">
                  <div className="skeleton h-3 w-2/3 rounded" />
                  <div className="skeleton h-2.5 w-full rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : visible.length === 0 && ignored.length === 0 ? (
          <div className="px-5 py-14 text-center">
            <Icon.inbox size={26} className="mx-auto text-faint" />
            <p className="mt-3 text-sm text-muted">Nothing here yet.</p>
            <p className="mt-1 text-xs text-faint">
              Hit <span className="text-amber">Sync now</span> to pull, classify and draft
              your recent mail.
            </p>
          </div>
        ) : (
          [...grouped.entries()].map(([group, items]) => (
            <div key={group || "flat"}>
              {group && (
                <div className="glass sticky top-0 z-10 border-b border-hairline px-4 py-1.5 font-mono text-[9.5px] uppercase tracking-[0.16em] text-faint">
                  {group}
                </div>
              )}
              {sortTriage(items).map((t) => (
                <ThreadRow
                  key={t.id}
                  thread={t}
                  active={t.id === selectedId}
                  onClick={() => onSelect(t.id)}
                />
              ))}
            </div>
          ))
        )}
        {ignored.length > 0 && selection.kind !== "digest" && (
          <button
            onClick={() => setShowIgnored((v) => !v)}
            className="block w-full px-4 py-3 text-center font-mono text-[10.5px] text-faint transition-colors hover:text-muted"
          >
            {showIgnored
              ? "− hide filtered mail"
              : `··· ${ignored.length} filtered as not worth reading — show`}
          </button>
        )}
      </div>
    </section>
  );
}

function ThreadRow({
  thread,
  active,
  onClick,
}: {
  thread: Thread;
  active: boolean;
  onClick: () => void;
}) {
  const urgent =
    thread.urgency === "high" && thread.status !== "sent" && thread.status !== "ignored";
  const { initials, tint } = avatarFor(thread.last_sender);
  const faded = thread.status === "ignored" || thread.status === "sent";

  return (
    <button
      onClick={onClick}
      className={`relative flex w-full gap-3 border-b border-hairline px-4 py-3 text-left transition-colors ${
        active ? "bg-raised" : "hover:bg-raised/50"
      } ${faded ? "opacity-55" : ""}`}
    >
      {active && <span className="absolute left-0 top-0 h-full w-[2.5px] bg-amber" />}
      <span
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${tint}`}
      >
        {initials}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-[12.5px] font-medium text-ink">
            {thread.last_sender || "(unknown sender)"}
          </span>
          <span className="shrink-0 font-mono text-[10px] text-faint">
            {timeAgo(thread.updated_at)}
          </span>
        </span>
        <span className="mt-0.5 flex items-center gap-1.5">
          {urgent && <Icon.zap size={11} className="shrink-0 text-amber" />}
          <span className="truncate text-[12.5px] text-muted">{thread.subject}</span>
        </span>
        <span className="mt-1.5 flex items-center gap-2">
          <StatusBadge status={thread.status} />
          <span className="truncate text-[11px] text-faint">{thread.snippet}</span>
        </span>
      </span>
    </button>
  );
}

export function sortTriage(threads: Thread[]): Thread[] {
  return [...threads].sort((a, b) => {
    const d = STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status);
    if (d !== 0) return d;
    return +new Date(b.updated_at) - +new Date(a.updated_at);
  });
}

/** Visual order of the list — also drives j/k keyboard navigation. */
export function orderedIds(
  threads: Thread[],
  projects: Project[],
  selection: Selection,
): number[] {
  const visible =
    selection.kind === "digest" ? threads : threads.filter((t) => t.status !== "ignored");
  if (selection.kind === "all" || selection.kind === "home") {
    const name = (id: number | null) =>
      id == null ? "Unclassified" : (projects.find((p) => p.id === id)?.name ?? "Unclassified");
    return [...groupBy(visible, (t) => name(t.project_id)).values()]
      .flatMap((g) => sortTriage(g))
      .map((t) => t.id);
  }
  return sortTriage(visible).map((t) => t.id);
}

function groupBy<T>(items: T[], key: (t: T) => string): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const k = key(item);
    if (!map.has(k)) map.set(k, []);
    map.get(k)!.push(item);
  }
  // Unclassified group last
  return new Map(
    [...map.entries()].sort(([a], [b]) =>
      a === "Unclassified" ? 1 : b === "Unclassified" ? -1 : a.localeCompare(b),
    ),
  );
}
