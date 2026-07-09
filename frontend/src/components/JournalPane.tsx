"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Habit, type JournalEntry } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";

const todayISO = () => new Date().toISOString().slice(0, 10);
// last 7 calendar days (UTC), oldest -> newest
function last7(): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setUTCDate(now.getUTCDate() - i);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

export default function JournalPane() {
  const [habits, setHabits] = useState<Habit[]>([]);
  const [newHabit, setNewHabit] = useState("");
  const [newEmoji, setNewEmoji] = useState("");
  const [entry, setEntry] = useState<JournalEntry>({ day: todayISO(), text: "", mood: "" });
  const [recent, setRecent] = useState<JournalEntry[]>([]);
  const [saved, setSaved] = useState(true);
  const days = last7();
  const today = todayISO();
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    const [h, e, r] = await Promise.all([
      api.habits(30),
      api.getJournal(today),
      api.journalRecent(14),
    ]);
    setHabits(h);
    setEntry(e);
    setRecent(r.filter((x) => x.day !== today));
  }, [today]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (id: number) => {
    const updated = await api.toggleHabit(id); // defaults to today
    setHabits((prev) => prev.map((h) => (h.id === id ? updated : h)));
  };

  const addHabit = async () => {
    const name = newHabit.trim();
    if (!name) return;
    const h = await api.createHabit(name, newEmoji.trim());
    setHabits((prev) => [...prev, h]);
    setNewHabit("");
    setNewEmoji("");
  };

  const removeHabit = async (id: number) => {
    await api.deleteHabit(id);
    setHabits((prev) => prev.filter((h) => h.id !== id));
  };

  const onEntryChange = (patch: Partial<JournalEntry>) => {
    setEntry((e) => ({ ...e, ...patch }));
    setSaved(false);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      const cur = { ...entry, ...patch };
      await api.putJournal(today, cur.text, cur.mood);
      setSaved(true);
    }, 700);
  };

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-[900px]">
        <PageHeader
          eyebrow="Personal"
          title="Journal & habits"
          subtitle="Keep your streaks and capture the day. Private, on your machine."
        />

        {/* habits */}
        <section className="card mb-6 p-5">
          <h2 className="mb-3 font-mono text-[10.5px] uppercase tracking-[0.15em] text-muted">Habits</h2>
          <div className="space-y-1.5">
            {habits.map((h) => (
              <div key={h.id} className="group flex items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-raised/50">
                <span className="w-6 text-center text-[15px]">{h.emoji || "•"}</span>
                <span className="w-40 shrink-0 truncate text-[13px] text-ink">{h.name}</span>
                <span className="flex items-center gap-1">
                  {days.map((d) => {
                    const done = h.days.includes(d);
                    const isToday = d === today;
                    return (
                      <button
                        key={d}
                        onClick={() => isToday && toggle(h.id)}
                        disabled={!isToday}
                        title={d + (isToday ? " (today)" : "")}
                        className={`h-5 w-5 rounded-md border transition-colors ${
                          done
                            ? "border-amber bg-amber/80"
                            : isToday
                              ? "border-amber-dim hover:bg-amber/15"
                              : "border-hairline-strong"
                        }`}
                      />
                    );
                  })}
                </span>
                <span className="ml-2 font-mono text-[11px] text-amber">{h.streak}🔥</span>
                <button
                  onClick={() => removeHabit(h.id)}
                  className="ml-auto rounded p-1 text-faint opacity-0 transition-opacity hover:text-red group-hover:opacity-100"
                >
                  <Icon.trash size={13} />
                </button>
              </div>
            ))}
            {habits.length === 0 && <p className="px-2 py-3 text-[12.5px] text-faint">No habits yet — add one below.</p>}
          </div>
          <div className="mt-3 flex items-center gap-2 border-t border-hairline pt-3">
            <input
              value={newEmoji}
              onChange={(e) => setNewEmoji(e.target.value)}
              placeholder="🏃"
              maxLength={2}
              className="w-12 rounded-lg border border-hairline-strong bg-panel px-2 py-1.5 text-center text-[14px] focus:border-amber focus:outline-none"
            />
            <input
              value={newHabit}
              onChange={(e) => setNewHabit(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addHabit()}
              placeholder="New habit (e.g. gym, read, ship)"
              className="min-w-0 flex-1 rounded-lg border border-hairline-strong bg-panel px-3 py-1.5 text-[13px] text-ink placeholder:text-faint focus:border-amber focus:outline-none"
            />
            <button onClick={addHabit} disabled={!newHabit.trim()} className="btn btn-outline">
              <Icon.plus size={13} /> add
            </button>
          </div>
        </section>

        {/* today's journal */}
        <section className="card mb-6 p-5">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-mono text-[10.5px] uppercase tracking-[0.15em] text-muted">
              {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
            </h2>
            <span className="flex items-center gap-2">
              <input
                value={entry.mood}
                onChange={(e) => onEntryChange({ mood: e.target.value })}
                placeholder="mood"
                maxLength={16}
                className="w-20 rounded-md border border-hairline-strong bg-panel px-2 py-0.5 text-center text-[12px] focus:border-amber focus:outline-none"
              />
              <span className="font-mono text-[10px] text-faint">{saved ? "saved" : "saving…"}</span>
            </span>
          </div>
          <textarea
            value={entry.text}
            onChange={(e) => onEntryChange({ text: e.target.value })}
            placeholder="What happened today? What's on your mind?"
            rows={8}
            className="draft-editor w-full bg-transparent text-[14px] text-ink placeholder:text-faint"
          />
        </section>

        {/* recent entries */}
        {recent.length > 0 && (
          <section>
            <h2 className="mb-2 px-1 font-mono text-[10.5px] uppercase tracking-[0.15em] text-faint">Earlier</h2>
            <div className="space-y-2">
              {recent.filter((r) => r.text.trim()).map((r) => (
                <div key={r.day} className="card p-4">
                  <div className="mb-1 flex items-center gap-2 font-mono text-[10.5px] text-faint">
                    {new Date(r.day + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                    {r.mood && <span className="text-amber">· {r.mood}</span>}
                  </div>
                  <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-muted">{r.text}</p>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
