"use client";

import type { Project } from "@/lib/api";
import { Icon, type IconName } from "./Icons";
import ThemeToggle from "./ThemeToggle";

export type Selection =
  | { kind: "home" }
  | { kind: "ideas" }
  | { kind: "jobs" }
  | { kind: "events" }
  | { kind: "research" }
  | { kind: "journal" }
  | { kind: "brain" }
  | { kind: "all" }
  | { kind: "unclassified" }
  | { kind: "digest" }
  | { kind: "settings" }
  | { kind: "project"; id: number };

function selKey(s: Selection): string {
  return s.kind === "project" ? `p${s.id}` : s.kind;
}

export default function Sidebar({
  projects,
  selection,
  onSelect,
  onNewProject,
  onSync,
  syncing,
  onOrganize,
  organizing,
}: {
  projects: Project[];
  selection: Selection;
  onSelect: (s: Selection) => void;
  onNewProject: () => void;
  onSync: () => void;
  syncing: boolean;
  onOrganize: () => void;
  organizing: boolean;
}) {
  const current = selKey(selection);

  const Item = ({
    sel,
    label,
    icon,
    count,
    attention,
    auto,
    dim,
  }: {
    sel: Selection;
    label: string;
    icon?: IconName;
    count?: number;
    attention?: number;
    auto?: boolean;
    dim?: boolean;
  }) => {
    const active = selKey(sel) === current;
    const Glyph = icon ? Icon[icon] : null;
    return (
      <button
        onClick={() => onSelect(sel)}
        className={`group relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-left text-[13px] transition-colors ${
          active
            ? "bg-raised text-ink"
            : `${dim ? "text-faint" : "text-muted"} hover:bg-raised/55 hover:text-ink`
        }`}
      >
        {active && (
          <span className="absolute left-0 top-1/2 h-4 w-[2.5px] -translate-y-1/2 rounded-full bg-amber" />
        )}
        {Glyph && (
          <Glyph
            size={15}
            className={active ? "text-amber" : "text-faint group-hover:text-muted"}
          />
        )}
        <span className="flex min-w-0 flex-1 items-center gap-1.5">
          <span className="truncate">{label}</span>
          {auto && <span className="text-[9px] text-faint">✦</span>}
        </span>
        {attention ? (
          <span className="rounded-full bg-amber/15 px-1.5 font-mono text-[10px] text-amber">
            {attention}
          </span>
        ) : count != null && count > 0 ? (
          <span className="font-mono text-[10px] text-faint">{count}</span>
        ) : null}
      </button>
    );
  };

  const SectionLabel = ({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) => (
    <div className="mb-1 mt-4 flex items-center justify-between px-2.5">
      <span className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-faint">{children}</span>
      {action}
    </div>
  );

  return (
    <aside className="glass flex h-full w-[244px] shrink-0 flex-col border-r border-hairline">
      {/* wordmark */}
      <div className="flex items-center gap-2.5 px-4 pb-4 pt-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-dim/70 bg-amber/15">
          <Icon.send size={15} className="text-amber" />
        </div>
        <div>
          <div className="text-[13.5px] font-semibold tracking-tight text-ink">Adjutant</div>
          <div className="font-mono text-[8.5px] uppercase tracking-[0.2em] text-faint">
            your command deck
          </div>
        </div>
      </div>

      {/* nav */}
      <nav className="flex-1 overflow-y-auto px-2.5 pb-3">
        <div className="space-y-0.5">
          <Item sel={{ kind: "home" }} label="Today" icon="today" />
          <Item sel={{ kind: "ideas" }} label="Ideas" icon="idea" />
          <Item sel={{ kind: "jobs" }} label="Jobs" icon="compass" />
          <Item sel={{ kind: "events" }} label="Events" icon="ticket" />
          <Item sel={{ kind: "research" }} label="Research" icon="search" />
          <Item sel={{ kind: "journal" }} label="Journal" icon="book" />
          <Item sel={{ kind: "brain" }} label="Second brain" icon="brain" />
        </div>

        <SectionLabel>Mail</SectionLabel>
        <div className="space-y-0.5">
          <Item sel={{ kind: "all" }} label="All mail" icon="mail" />
          <Item sel={{ kind: "unclassified" }} label="Unclassified" icon="inbox" />
        </div>

        <SectionLabel
          action={
            <button
              onClick={onNewProject}
              title="New project"
              className="rounded p-0.5 text-faint transition-colors hover:text-amber"
            >
              <Icon.plus size={13} />
            </button>
          }
        >
          Projects
        </SectionLabel>
        <div className="space-y-0.5">
          {projects.filter((p) => !p.digest).map((p) => (
            <Item
              key={p.id}
              sel={{ kind: "project", id: p.id }}
              label={p.name}
              icon="folder"
              count={p.thread_count}
              attention={p.needs_attention}
              auto={p.auto}
            />
          ))}
          {projects.length === 0 && (
            <button
              onClick={onNewProject}
              className="w-full rounded-lg border border-dashed border-hairline-strong px-2.5 py-2 text-left text-xs text-faint transition-colors hover:border-amber-dim hover:text-muted"
            >
              Add your first project — its description powers classification.
            </button>
          )}
        </div>

        {projects.some((p) => p.digest) && (
          <>
            <SectionLabel>Digest</SectionLabel>
            <div className="space-y-0.5">
              <Item sel={{ kind: "digest" }} label="Briefing" icon="sparkle" />
              {projects.filter((p) => p.digest).map((p) => (
                <Item
                  key={p.id}
                  sel={{ kind: "project", id: p.id }}
                  label={p.name}
                  icon="feed"
                  count={p.thread_count}
                  dim
                />
              ))}
            </div>
          </>
        )}
      </nav>

      {/* actions */}
      <div className="space-y-1.5 border-t border-hairline p-3">
        <button
          onClick={onSync}
          disabled={syncing || organizing}
          className="btn btn-outline w-full"
        >
          <Icon.sync size={13} className={syncing ? "spin" : ""} />
          {syncing ? "Syncing…" : "Sync now"}
        </button>
        <button
          onClick={onOrganize}
          disabled={syncing || organizing}
          title="Let AI invent categories from unfiled mail and junk what isn't worth reading"
          className="btn btn-ghost w-full justify-center"
        >
          <Icon.sparkle size={13} className={organizing ? "spin" : ""} />
          {organizing ? "Organizing…" : "Auto-organize"}
        </button>
        <div className="flex items-center justify-between pt-0.5">
          <button
            onClick={() => onSelect({ kind: "settings" })}
            className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11.5px] transition-colors ${
              current === "settings" ? "text-amber" : "text-muted hover:text-ink"
            }`}
          >
            <Icon.gear size={13} /> Settings
          </button>
          <ThemeToggle />
        </div>
        <p className="text-center font-mono text-[9px] text-faint">
          ⌘K palette · j/k nav · ⌘↵ send
        </p>
      </div>
    </aside>
  );
}
