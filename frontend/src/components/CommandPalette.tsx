"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Project, Thread } from "@/lib/api";
import { Icon, type IconName } from "./Icons";
import type { Selection } from "./Sidebar";

type Cmd = {
  id: string;
  label: string;
  hint?: string;
  icon: IconName;
  run: () => void;
};

export default function CommandPalette({
  open,
  onClose,
  projects,
  threads,
  onNavigate,
  onOpenThread,
  onSync,
  onOrganize,
}: {
  open: boolean;
  onClose: () => void;
  projects: Project[];
  threads: Thread[];
  onNavigate: (s: Selection) => void;
  onOpenThread: (id: number) => void;
  onSync: () => void;
  onOrganize: () => void;
}) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  const commands = useMemo<Cmd[]>(() => {
    const go = (s: Selection) => () => {
      onNavigate(s);
      onClose();
    };
    const nav: Cmd[] = [
      { id: "today", label: "Today", icon: "today", run: go({ kind: "home" }) },
      { id: "ideas", label: "Ideas", icon: "idea", run: go({ kind: "ideas" }) },
      { id: "jobs", label: "Jobs", icon: "compass", run: go({ kind: "jobs" }) },
      { id: "events", label: "Events", icon: "ticket", run: go({ kind: "events" }) },
      { id: "research", label: "Research", icon: "search", run: go({ kind: "research" }) },
      { id: "journal", label: "Journal", icon: "book", run: go({ kind: "journal" }) },
      { id: "brain", label: "Second brain", icon: "brain", run: go({ kind: "brain" }) },
      { id: "briefing", label: "Briefing", icon: "sparkle", run: go({ kind: "digest" }) },
      { id: "all", label: "All mail", icon: "mail", run: go({ kind: "all" }) },
      { id: "uncl", label: "Unclassified", icon: "inbox", run: go({ kind: "unclassified" }) },
      { id: "settings", label: "Settings", icon: "gear", run: go({ kind: "settings" }) },
    ];
    const projectCmds: Cmd[] = projects.map((p) => ({
      id: `p${p.id}`,
      label: p.name,
      hint: "project",
      icon: p.digest ? "feed" : "folder",
      run: go({ kind: "project", id: p.id }),
    }));
    const actions: Cmd[] = [
      { id: "a-sync", label: "Sync now", hint: "action", icon: "sync", run: () => { onSync(); onClose(); } },
      { id: "a-org", label: "Auto-organize", hint: "action", icon: "sparkle", run: () => { onOrganize(); onClose(); } },
    ];
    return [...nav, ...actions, ...projectCmds];
  }, [projects, onNavigate, onClose, onSync, onOrganize]);

  const ql = q.trim().toLowerCase();
  const matchedCmds = ql
    ? commands.filter((c) => c.label.toLowerCase().includes(ql))
    : commands;
  const matchedThreads = ql
    ? threads
        .filter(
          (t) =>
            t.subject.toLowerCase().includes(ql) ||
            t.last_sender.toLowerCase().includes(ql),
        )
        .slice(0, 6)
    : [];

  type Row = { kind: "cmd"; cmd: Cmd } | { kind: "thread"; thread: Thread };
  const rows: Row[] = [
    ...matchedCmds.map((cmd) => ({ kind: "cmd" as const, cmd })),
    ...matchedThreads.map((thread) => ({ kind: "thread" as const, thread })),
  ];

  useEffect(() => {
    if (active >= rows.length) setActive(Math.max(0, rows.length - 1));
  }, [rows.length, active]);

  const runRow = (r: Row) => {
    if (r.kind === "cmd") r.cmd.run();
    else {
      onOpenThread(r.thread.id);
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-base/70 pt-[12vh] backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="fade-up w-[560px] overflow-hidden rounded-2xl border border-hairline-strong bg-overlay"
        style={{ boxShadow: "var(--shadow-pop)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 border-b border-hairline px-4 py-3">
          <Icon.arrow size={15} className="text-faint" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, rows.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter" && rows[active]) {
                e.preventDefault();
                runRow(rows[active]);
              } else if (e.key === "Escape") {
                onClose();
              }
            }}
            placeholder="Jump to, search mail, or run an action…"
            className="flex-1 bg-transparent text-[14px] text-ink placeholder:text-faint focus:outline-none"
          />
          <span className="chip">esc</span>
        </div>

        <div className="max-h-[52vh] overflow-y-auto p-1.5">
          {rows.length === 0 && (
            <p className="px-3 py-6 text-center text-[12.5px] text-faint">No matches.</p>
          )}
          {matchedThreads.length > 0 && (
            <div className="px-2.5 pb-1 pt-2 font-mono text-[9px] uppercase tracking-[0.15em] text-faint">
              Jump · {matchedCmds.length ? "Navigate & actions above" : ""}
            </div>
          )}
          {rows.map((r, i) => {
            const isActive = i === active;
            const base = `flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] ${
              isActive ? "bg-raised text-ink" : "text-muted"
            }`;
            if (r.kind === "cmd") {
              const Glyph = Icon[r.cmd.icon];
              return (
                <button key={r.cmd.id} className={base} onMouseEnter={() => setActive(i)} onClick={() => runRow(r)}>
                  <Glyph size={14} className={isActive ? "text-amber" : "text-faint"} />
                  <span className="flex-1 truncate">{r.cmd.label}</span>
                  {r.cmd.hint && <span className="font-mono text-[9px] uppercase tracking-wide text-faint">{r.cmd.hint}</span>}
                </button>
              );
            }
            return (
              <button key={`t${r.thread.id}`} className={base} onMouseEnter={() => setActive(i)} onClick={() => runRow(r)}>
                <Icon.mail size={14} className={isActive ? "text-amber" : "text-faint"} />
                <span className="min-w-0 flex-1">
                  <span className="truncate">{r.thread.subject}</span>
                  <span className="ml-2 font-mono text-[10px] text-faint">{r.thread.last_sender}</span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
