"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Project, type Thread, type ThreadDetail } from "@/lib/api";
import Sidebar, { type Selection } from "@/components/Sidebar";
import ThreadList, { orderedIds } from "@/components/ThreadList";
import ThreadView from "@/components/ThreadView";
import BriefingPane from "@/components/BriefingPane";
import HomeDashboard from "@/components/HomeDashboard";
import IdeasPane from "@/components/IdeasPane";
import JobsPane from "@/components/JobsPane";
import EventsPane from "@/components/EventsPane";
import ResearchPane from "@/components/ResearchPane";
import JournalPane from "@/components/JournalPane";
import SecondBrainPane from "@/components/SecondBrainPane";
import SettingsPane from "@/components/SettingsPane";
import CommandPalette from "@/components/CommandPalette";
import { Icon } from "@/components/Icons";
import DraftPanel from "@/components/DraftPanel";
import NewProjectModal from "@/components/NewProjectModal";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selection, setSelection] = useState<Selection>({ kind: "home" });
  const [threads, setThreads] = useState<Thread[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [organizing, setOrganizing] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [notice, setNotice] = useState<
    { text: string; kind: "ok" | "err"; action?: { label: string; run: () => void } } | null
  >(null);

  const flash = (
    text: string,
    kind: "ok" | "err" = "ok",
    action?: { label: string; run: () => void },
  ) => {
    setNotice({ text, kind, action });
    setTimeout(() => setNotice(null), kind === "err" ? 8000 : action ? 6500 : 4500);
  };

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await api.projects());
    } catch (e) {
      flash(e instanceof Error ? e.message : "Backend unreachable — is it running on :8000?", "err");
    }
  }, []);

  const refreshThreads = useCallback(async (sel: Selection, quiet = false) => {
    if (!quiet) setListLoading(true);
    try {
      const filter =
        sel.kind === "unclassified"
          ? { unclassified: true }
          : sel.kind === "digest"
            ? { digest: true }
            : sel.kind === "project"
              ? { projectId: sel.id }
              : {}; // "all" and "home" both see everything
      setThreads(await api.threads(filter));
    } catch {
      /* surfaced via projects fetch */
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    refreshThreads(selection);
  }, [selection, refreshThreads]);

  // Quiet background poll — keeps the deck current alongside the backend's
  // scheduled sync, without spinners or scroll jumps.
  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState !== "visible" || syncing || organizing) return;
      refreshProjects();
      refreshThreads(selection, true);
    }, 60_000);
    return () => clearInterval(id);
  }, [selection, syncing, organizing, refreshProjects, refreshThreads]);

  // ⌘K / Ctrl+K toggles the command palette (works even from inputs).
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") {
        ev.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Keyboard triage: j/k walk the visible list, e jumps into the draft editor.
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const el = ev.target as HTMLElement;
      if (
        el.tagName === "INPUT" ||
        el.tagName === "TEXTAREA" ||
        el.isContentEditable ||
        ev.metaKey ||
        ev.ctrlKey
      )
        return;
      // j/k only when a thread list is on screen
      const hasList = !["home", "ideas", "jobs", "events", "research", "journal", "brain", "settings"].includes(selection.kind);
      if (hasList && (ev.key === "j" || ev.key === "k")) {
        const order = orderedIds(threads, projects, selection);
        if (order.length === 0) return;
        const idx = selectedId == null ? -1 : order.indexOf(selectedId);
        const next =
          ev.key === "j"
            ? order[Math.min(idx + 1, order.length - 1)]
            : order[Math.max(idx - 1, 0)];
        if (next != null && next !== selectedId) openThread(next);
      } else if (ev.key === "e" && detail) {
        ev.preventDefault();
        window.dispatchEvent(new Event("ip-focus-draft"));
      } else if (ev.key === "Escape" && detail && !ev.defaultPrevented) {
        // back out of the thread (DraftPanel claims Esc first when confirming)
        setSelectedId(null);
        setDetail(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threads, projects, selection, selectedId, detail]);

  const openThread = async (id: number) => {
    setSelectedId(id);
    setDetailLoading(true);
    setDetail(null);
    try {
      setDetail(await api.threadDetail(id));
    } catch (e) {
      flash(e instanceof Error ? e.message : "Failed to load thread", "err");
    } finally {
      setDetailLoading(false);
    }
  };

  const patchThread = (updated: Thread) => {
    setThreads((ts) => ts.map((t) => (t.id === updated.id ? updated : t)));
    setDetail((d) => (d && d.thread.id === updated.id ? { ...d, thread: updated } : d));
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const s = await api.sync();
      flash(
        `Sync: ${s.seen} seen · ${s.skipped} already processed · ${s.classified} classified · ${s.drafted} drafted` +
          (s.errors.length ? ` · ${s.errors.length} failed (will retry)` : ""),
        s.errors.length ? "err" : "ok",
      );
      await Promise.all([refreshProjects(), refreshThreads(selection)]);
    } catch (e) {
      flash(e instanceof Error ? e.message : "Sync failed", "err");
    } finally {
      setSyncing(false);
    }
  };

  const handleOrganize = async () => {
    setOrganizing(true);
    try {
      const o = await api.organize();
      flash(
        `Organized ${o.considered} threads: ${o.assigned} filed` +
          (o.new_projects.length ? ` (new: ${o.new_projects.join(", ")})` : "") +
          ` · ${o.skipped} junked` +
          (o.unresolved ? ` · ${o.unresolved} left unfiled` : ""),
      );
      await Promise.all([refreshProjects(), refreshThreads(selection)]);
    } catch (e) {
      flash(e instanceof Error ? e.message : "Organize failed", "err");
    } finally {
      setOrganizing(false);
    }
  };

  return (
    <main className="flex h-screen">
      <Sidebar
        projects={projects}
        selection={selection}
        onSelect={(s) => {
          setSelection(s);
          setSelectedId(null);
          setDetail(null);
        }}
        onNewProject={() => setModalOpen(true)}
        onSync={handleSync}
        syncing={syncing}
        onOrganize={handleOrganize}
        organizing={organizing}
      />

      {selection.kind !== "home" &&
        selection.kind !== "ideas" &&
        selection.kind !== "jobs" &&
        selection.kind !== "events" &&
        selection.kind !== "research" &&
        selection.kind !== "journal" &&
        selection.kind !== "brain" &&
        selection.kind !== "settings" && (
        <ThreadList
          threads={threads}
          projects={projects}
          selection={selection}
          selectedId={selectedId}
          onSelect={openThread}
          loading={listLoading}
        />
      )}

      {/* detail pane */}
      <section className="flex h-full min-w-0 flex-1 flex-col">
        {detail ? (
          <>
            <div className="flex-1 overflow-y-auto px-8 py-6">
              <ThreadView subject={detail.thread.subject} messages={detail.messages} />
            </div>
            <DraftPanel
              key={detail.thread.id}
              draft={detail.draft_body ?? ""}
              replyTo={detail.reply_to}
              status={detail.thread.status}
              onSave={async (body) => {
                patchThread(await api.saveDraft(detail.thread.id, body));
              }}
              onSend={async (body, to) => {
                patchThread(await api.send(detail.thread.id, body, to));
                flash("Reply sent ✓");
                refreshProjects();
              }}
              onIgnore={async () => {
                patchThread(await api.ignore(detail.thread.id));
              }}
              onRedraft={async () => {
                patchThread(await api.redraft(detail.thread.id));
                setDetail(await api.threadDetail(detail.thread.id));
                flash("Fresh draft ready ✓");
              }}
            />
          </>
        ) : detailLoading ? (
          <div className="flex flex-1 items-center justify-center text-sm text-faint">
            Loading thread…
          </div>
        ) : selection.kind === "home" ? (
          <HomeDashboard
            threads={threads}
            projects={projects}
            flash={flash}
            onOpenThread={openThread}
            onOpenProject={(id) => {
              setSelection({ kind: "project", id });
              setSelectedId(null);
              setDetail(null);
            }}
            onOpenBriefing={() => {
              setSelection({ kind: "digest" });
              setSelectedId(null);
              setDetail(null);
            }}
            onStateChanged={() => {
              refreshProjects();
              refreshThreads(selection, true);
            }}
          />
        ) : selection.kind === "ideas" ? (
          <IdeasPane />
        ) : selection.kind === "jobs" ? (
          <JobsPane />
        ) : selection.kind === "events" ? (
          <EventsPane />
        ) : selection.kind === "research" ? (
          <ResearchPane />
        ) : selection.kind === "journal" ? (
          <JournalPane />
        ) : selection.kind === "brain" ? (
          <SecondBrainPane />
        ) : selection.kind === "settings" ? (
          <SettingsPane />
        ) : selection.kind === "digest" ? (
          <BriefingPane />
        ) : (
          <EmptyState hasProjects={projects.length > 0} onNewProject={() => setModalOpen(true)} />
        )}
      </section>

      {modalOpen && (
        <NewProjectModal
          onClose={() => setModalOpen(false)}
          onCreate={async (name, description) => {
            await api.createProject(name, description);
            await refreshProjects();
            flash(`Project "${name}" created`);
          }}
        />
      )}

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        projects={projects}
        threads={threads}
        onNavigate={(s) => {
          setSelection(s);
          setSelectedId(null);
          setDetail(null);
        }}
        onOpenThread={openThread}
        onSync={handleSync}
        onOrganize={handleOrganize}
      />

      {notice && (
        <div
          className="fade-up fixed bottom-5 left-1/2 z-50 flex max-w-[560px] -translate-x-1/2 items-center gap-2.5 rounded-xl border border-hairline-strong bg-overlay/95 px-4 py-2.5 font-mono text-[11.5px] backdrop-blur"
          style={{ boxShadow: "var(--shadow-pop)" }}
        >
          <span
            className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
              notice.kind === "err" ? "bg-red/15 text-red" : "bg-green/15 text-green"
            }`}
          >
            <Icon.check size={11} />
          </span>
          <span className={notice.kind === "err" ? "text-red" : "text-muted"}>{notice.text}</span>
          {notice.action && (
            <button
              onClick={() => {
                notice.action!.run();
                setNotice(null);
              }}
              className="ml-1 rounded-md border border-hairline-strong px-2 py-0.5 text-[11px] text-ink transition-colors hover:bg-raised"
            >
              {notice.action.label}
            </button>
          )}
        </div>
      )}
    </main>
  );
}

function EmptyState({
  hasProjects,
  onNewProject,
}: {
  hasProjects: boolean;
  onNewProject: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-10 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-dim/50 bg-amber/[0.12]">
        <Icon.mail size={24} className="text-amber" />
      </div>
      <h2 className="display mt-4 text-[1.35rem] text-ink">
        {hasProjects ? "Pick a thread to review" : "Welcome aboard"}
      </h2>
      <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-muted">
        {hasProjects ? (
          <>
            Threads marked <span className="text-amber">needs reply</span> come with an AI
            draft written in your voice — review, edit, and send without ever opening Gmail.
          </>
        ) : (
          <>
            Start by creating a project — its description teaches the classifier what
            belongs in it. Then hit <span className="text-amber">Sync now</span>.
          </>
        )}
      </p>
      {!hasProjects && (
        <button onClick={onNewProject} className="btn btn-primary mt-5 px-5 py-2 text-[13px]">
          Create first project
        </button>
      )}
    </div>
  );
}
