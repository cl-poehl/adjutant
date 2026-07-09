"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Automations } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";
import ThemeToggle from "./ThemeToggle";

type AutomationKey = keyof Automations;

const AUTOMATIONS: { key: AutomationKey; label: string; cost: string; desc: string }[] = [
  {
    key: "research",
    label: "Daily research brief",
    cost: "~$36/mo",
    desc: "6 web-search topics on Sonnet every morning. Your priciest job by far.",
  },
  {
    key: "jobs",
    label: "Daily job scout",
    cost: "~$9/mo",
    desc: "Scouts + ranks roles matched to your founder profile once a day.",
  },
  {
    key: "ideas",
    label: "Daily startup ideas",
    cost: "~$7/mo",
    desc: "Generates a fresh batch of startup ideas once a day.",
  },
];

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className={`relative h-5 w-9 shrink-0 rounded-full border transition-colors ${
        on ? "border-amber-dim bg-amber/80" : "border-hairline bg-base"
      }`}
    >
      <span
        className={`absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-all ${
          on ? "left-[18px]" : "left-0.5"
        }`}
      />
    </button>
  );
}

export default function SettingsPane() {
  const [profile, setProfile] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [saveState, setSaveState] = useState<"saved" | "dirty" | "saving">("saved");
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [automations, setAutomations] = useState<Automations | null>(null);
  const [autoErr, setAutoErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setProfile((await api.founder()).profile);
      setLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load profile");
    }
    try {
      setAutomations(await api.automations());
    } catch (e) {
      setAutoErr(e instanceof Error ? e.message : "Failed to load automations");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (key: AutomationKey) => {
    if (!automations) return;
    const prev = automations;
    const next = { ...automations, [key]: !automations[key] };
    setAutomations(next); // optimistic
    setAutoErr(null);
    try {
      setAutomations(await api.saveAutomations(next));
    } catch (e) {
      setAutomations(prev); // revert on failure
      setAutoErr(e instanceof Error ? e.message : "Save failed");
    }
  };

  const onChange = (next: string) => {
    setProfile(next);
    setSaveState("dirty");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setSaveState("saving");
      try {
        await api.saveFounder(next);
        setSaveState("saved");
      } catch (e) {
        setSaveState("dirty");
        setError(e instanceof Error ? e.message : "Save failed");
      }
    }, 800);
  };

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-3xl">
        <PageHeader
          eyebrow="Settings"
          title="Tune your engine"
          subtitle="This profile is the 'why you' behind every generated idea and scouted job. The sharper and more honest it is, the better the matches."
          actions={
            <span className="flex items-center gap-2">
              <span className="eyebrow">Theme</span>
              <ThemeToggle />
            </span>
          }
        />

        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-[13px] font-semibold text-ink">
              <Icon.gear size={15} className="text-faint" /> Founder profile
            </h2>
            <span
              className={`font-mono text-[10px] ${
                saveState === "saved" ? "text-faint" : saveState === "saving" ? "text-blue" : "text-amber"
              }`}
            >
              {saveState === "saved" ? "saved" : saveState === "saving" ? "saving…" : "unsaved"}
            </span>
          </div>

          {error && <p className="mb-2 text-xs text-red">{error}</p>}

          {loaded ? (
            <textarea
              value={profile}
              onChange={(e) => onChange(e.target.value)}
              spellCheck={false}
              rows={26}
              className="w-full rounded-lg border border-hairline bg-base/60 px-4 py-3 font-mono text-[12px] leading-relaxed text-ink placeholder:text-faint focus:border-amber-dim focus:outline-none"
              placeholder="Describe your edges, domains, and what you're optimizing for…"
            />
          ) : (
            <div className="skeleton h-72 w-full rounded-lg" />
          )}

          <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
            Edits autosave and take effect on your next <span className="text-amber">Generate ideas</span> or{" "}
            <span className="text-amber">Scout jobs</span>. Markdown is fine — write it like a brief.
          </p>
        </section>

        <section className="card mt-5 p-5">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-[13px] font-semibold text-ink">
              <Icon.gear size={15} className="text-faint" /> Automations &amp; spend
            </h2>
          </div>
          <p className="mb-4 text-[11.5px] leading-relaxed text-faint">
            These are the paid jobs that run automatically each day. Turn one off to stop its
            spend — you can still run it by hand anytime from its own page.
          </p>

          {autoErr && <p className="mb-2 text-xs text-red">{autoErr}</p>}

          {automations ? (
            <ul className="divide-y divide-hairline">
              {AUTOMATIONS.map((a) => (
                <li key={a.key} className="flex items-center gap-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-medium text-ink">{a.label}</span>
                      <span className="chip border-hairline font-mono text-[10px] text-faint">
                        {a.cost}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11.5px] leading-relaxed text-faint">{a.desc}</p>
                  </div>
                  <span className="font-mono text-[10px] text-faint">
                    {automations[a.key] ? "on" : "off"}
                  </span>
                  <Toggle on={automations[a.key]} onClick={() => toggle(a.key)} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="skeleton h-40 w-full rounded-lg" />
          )}
        </section>
      </div>
    </div>
  );
}
