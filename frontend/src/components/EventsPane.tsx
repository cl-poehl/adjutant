"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Event } from "@/lib/api";
import { Icon } from "./Icons";
import PageHeader from "./PageHeader";
import { EmptyState, Field, SkeletonGrid } from "./IdeasPane";

const CITY_KEY = "ip.events.city.v2"; // bumped so the stale saved city resets to the new default
const SUGGESTED = ["Munich", "Zürich", "Berlin", "Vienna", "London", "Paris"];

export default function EventsPane() {
  const [city, setCity] = useState("Munich");
  const [draftCity, setDraftCity] = useState("Munich");
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [scouting, setScouting] = useState(false);
  const [tab, setTab] = useState<"fresh" | "saved">("fresh");
  const [error, setError] = useState<string | null>(null);

  // Remember the last city across sessions.
  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem(CITY_KEY) : null;
    if (saved) {
      setCity(saved);
      setDraftCity(saved);
    }
  }, []);

  const load = useCallback(async (c: string) => {
    setLoading(true);
    try {
      setEvents(await api.events(c));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(city);
  }, [city, load]);

  const applyCity = (c: string) => {
    const next = c.trim();
    if (!next || next === city) return;
    setCity(next);
    setDraftCity(next);
    if (typeof window !== "undefined") localStorage.setItem(CITY_KEY, next);
  };

  const scout = async () => {
    applyCity(draftCity);
    const target = draftCity.trim() || city;
    setScouting(true);
    setError(null);
    try {
      const r = await api.scoutEvents(target);
      setEvents((prev) => [...r.events, ...prev]);
      setTab("fresh");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scouting failed");
    } finally {
      setScouting(false);
    }
  };

  const act = async (id: number, fn: (id: number) => Promise<Event>) => {
    const updated = await fn(id);
    setEvents((prev) => prev.map((e) => (e.id === id ? updated : e)));
  };

  const fresh = events.filter((e) => e.status === "new");
  const saved = events.filter((e) => e.status === "saved");
  const shown = tab === "saved" ? saved : fresh;

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7">
      <div className="mx-auto max-w-[1400px]">
        <PageHeader
          eyebrow="City scout"
          title="Events worth your evening"
          subtitle="Live-scouted, real events in your city — matched to your interests and the story your CV tells, and kept deliberately varied across music, art, ideas, nightlife, sport and tech."
          actions={
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-lg border border-hairline-strong bg-raised/40 px-2.5 py-1.5">
                <Icon.pin size={14} className="text-faint" />
                <input
                  value={draftCity}
                  onChange={(e) => setDraftCity(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") scout();
                  }}
                  list="ip-city-suggestions"
                  placeholder="City"
                  className="w-28 bg-transparent text-[13px] text-ink placeholder:text-faint focus:outline-none"
                />
                <datalist id="ip-city-suggestions">
                  {SUGGESTED.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </div>
              <button onClick={scout} disabled={scouting} className="btn btn-primary">
                <Icon.ticket size={14} className={scouting ? "spin" : ""} />
                {scouting ? "Scouting…" : "Scout events"}
              </button>
            </div>
          }
        />

        <div className="mb-5 flex items-center gap-1 border-b border-hairline">
          <Tab active={tab === "fresh"} onClick={() => setTab("fresh")} label="Fresh" n={fresh.length} />
          <Tab active={tab === "saved"} onClick={() => setTab("saved")} label="Saved" n={saved.length} />
          <span className="ml-auto pb-2 font-mono text-[10px] text-faint">in {city}</span>
        </div>

        {error && <p className="mb-4 text-sm text-red">{error}</p>}

        {scouting && (
          <div className="card mb-4 flex items-center gap-2.5 border-amber-dim/40 px-5 py-3.5 text-[13px] text-amber">
            <Icon.ticket size={15} className="spin" />
            Searching venues, listings and ticket sites in {draftCity.trim() || city} for events that fit you…
          </div>
        )}

        {loading && events.length === 0 ? (
          <SkeletonGrid />
        ) : shown.length === 0 ? (
          <EmptyState
            label={tab === "saved" ? "No saved events yet." : `No events scouted for ${city} yet.`}
            hint="Set your city and scout to find things worth going to."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {shown.map((ev) => (
              <EventCard
                key={ev.id}
                ev={ev}
                onSave={() => act(ev.id, api.saveEvent)}
                onDismiss={() => act(ev.id, api.dismissEvent)}
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

function Meter({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-1.5" title={`fit: ${value}/5`}>
      <span className="font-mono text-[9px] uppercase tracking-wide text-faint">fit</span>
      <span className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className={`dot ${n <= value ? "bg-amber" : "bg-hairline-strong"}`} />
        ))}
      </span>
    </span>
  );
}

function EventCard({
  ev,
  onSave,
  onDismiss,
}: {
  ev: Event;
  onSave: () => void;
  onDismiss: () => void;
}) {
  return (
    <article className="card card-hover fade-up flex flex-col p-5">
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {ev.category && (
            <span className="rounded-md border border-blue/40 bg-blue/[0.08] px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-wide text-blue">
              {ev.category}
            </span>
          )}
          {ev.when && (
            <span className="inline-flex items-center gap-1 rounded-md border border-amber-dim bg-amber/10 px-2 py-0.5 text-[12px] font-semibold text-amber">
              <Icon.today size={12} />
              {ev.when}
            </span>
          )}
        </div>
        <h2 className="display text-[1.2rem] leading-snug text-ink">{ev.title}</h2>
        {ev.venue && <p className="mt-0.5 text-[12.5px] text-muted"><span className="text-ink/80">{ev.venue}</span></p>}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {ev.deadline && (
            <span className="inline-flex items-center gap-1 rounded-lg border border-red/40 bg-red/[0.08] px-2.5 py-1 text-[11px] font-medium text-red">
              <Icon.bell size={11} />
              {ev.deadline}
            </span>
          )}
          {ev.price && (
            <span className="inline-block rounded-lg border border-green/40 bg-green/[0.08] px-2.5 py-1 font-mono text-[11px] text-green">
              {ev.price}
            </span>
          )}
        </div>
      </div>

      <div className="mt-3">
        <Meter value={ev.fit_score} />
      </div>

      <div className="mt-3.5 space-y-2 text-[12px] leading-relaxed">
        {ev.description && <Field label="What">{ev.description}</Field>}
        {ev.why_fit && <Field label="Why you" tone="amber">{ev.why_fit}</Field>}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-hairline pt-3">
        {ev.url ? (
          <a
            href={ev.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 truncate pr-3 font-mono text-[10.5px] text-blue hover:underline"
          >
            tickets / info <Icon.external size={11} />
          </a>
        ) : (
          <span className="truncate pr-3 font-mono text-[10px] text-faint">{ev.source}</span>
        )}
        {ev.status === "saved" ? (
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
