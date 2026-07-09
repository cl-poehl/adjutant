"""Event scout — finds real, upcoming events in a chosen city that fit the
user's personal AND professional interests (the CV tells a clear story, and
they like to spend professional time privately too).

Two-stage, mirroring the job scout:
  1. SCAN — Claude with live web search hunts SPECIFIC, currently-scheduled
     events in the city over the coming weeks across the user's interests.
  2. RANK — Claude scores each on personal fit, keeps a diverse, high-fit set
     (not ten of the same kind), grounded in the profile + interests.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import founder
from core.llm import (
    DRAFT_MODEL,
    EMPHASIS_GUIDE,
    complete,
    complete_with_search,
    extract_json,
)
from db.models import Event

log = logging.getLogger("adjutant.events")

# Generic default interests so the scout works out of the box. Put your real
# interests in the EVENT_INTERESTS env var (and the founder profile) rather than
# here, so nothing personal lives in the code.
_DEFAULT_INTERESTS = (
    "music and live concerts, art and exhibitions, film, food and restaurants, "
    "sport and the outdoors, tech and startup meetups, talks and conferences. "
    "Also weight the professional themes from the founder profile: relevant talks, "
    "conferences, hackathons, demo nights, and lectures are strong fits."
)

_SCAN_SYSTEM = """You are a sharp local culture & events concierge using web search. \
Given a city, a person's profile and their interests, find SPECIFIC, REAL, currently-\
scheduled upcoming events (roughly the next 6 weeks) that they would genuinely love.

Hard rules:
- Events must be REAL and verifiable via search — name the venue and an actual date. \
Do NOT invent events. Prefer official venue pages, ticketing sites (Eventbrite, \
Ticketmaster, RA/Resident Advisor for techno, Meetup/Luma for startup & tech), city \
listings, concert halls, museums, university lecture series, club/sports calendars.
- Cover BREADTH across their interests — don't return ten concerts. Aim for a varied \
slate (music, art, ideas/talks, nightlife, outdoor/sport, startup/tech, etc.).
- EVERY event MUST have a concrete date (a specific day, or a clear range). \
Discard anything whose date you cannot pin down — no "ongoing", no vague "this summer".
- For each event capture: title, category, venue, the exact date/time (or range), any \
registration / ticket / RSVP deadline if one exists (e.g. 'register by Jun 20', \
'tickets sell out'), an approximate price (mark 'est.' or 'free'), a ticket/info URL, \
a one-line description, and the source.

Return 12–20 concrete, nameable events — each with a real, specific date and venue."""

_RANK_SYSTEM = """You are curating an events shortlist for ONE person. You get their \
profile, interests, city and a list of scouted events. Keep only events that are a \
genuine fit and worth their evening — and keep the slate DIVERSE across their \
interests (don't return near-duplicates or all one category).

For each kept event, score personal fit 1–5 and explain, in one sharp clause, why it \
fits THIS person specifically (tie to their interests or profile).

Respond with ONLY this JSON, no prose:
{
  "events": [
    {
      "title": "<event name>",
      "category": "<one of: Classical, Music, Techno, Art, Literature, Talk, Startup, Tech, Outdoor, Sport, Chess, Dance, Film, Food, Other>",
      "venue": "<venue / place>",
      "when": "<REQUIRED specific date & time, or range, as text — never empty/vague>",
      "deadline": "<registration / RSVP / ticket deadline if one exists, else ''>",
      "price": "<approx price, 'free', or 'est. ...'>",
      "url": "<ticket/info URL if known, else ''>",
      "fit_score": <integer 1-5: how well it fits this person>,
      "why_fit": "<one clause: why THIS person specifically would love it>",
      "description": "<one-line description of the event>",
      "source": "<where it was found>"
    }
  ]
}
Order by fit_score descending. Keep events scoring >=3. DROP any event without a \
concrete date in "when". Favour a varied, exciting slate over redundancy. Do not invent \
events — only include ones from the scouted list."""


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def scout_events(
    session: Session, city: str = "", n: int = 10, use_web: bool = True
) -> dict:
    city = (city or "").strip()
    profile = founder.load_profile()
    interests = os.getenv("EVENT_INTERESTS", _DEFAULT_INTERESTS)

    # Avoid re-surfacing the same events we recently showed for this city.
    recent = session.execute(
        select(Event.title, Event.venue)
        .where(Event.city == city)
        .order_by(Event.created_at.desc())
        .limit(60)
    ).all()
    avoid = "\n".join(f"- {t} @ {v}" for t, v in recent) or "(none yet)"

    today = _today()

    # 1. SCAN — live, real upcoming events
    scan_user = (
        f"CITY: {city}\n"
        f"TODAY: {today}\n\n"
        f"PERSON PROFILE:\n{profile}\n\n"
        f"THEIR INTERESTS:\n{interests}\n\n"
        f"Find specific, real, upcoming events in {city} over the next ~6 weeks now, "
        "with venues, exact dates, approximate prices and source URLs."
    )
    if use_web:
        listing = complete_with_search(
            DRAFT_MODEL, _SCAN_SYSTEM, scan_user, max_tokens=3500, max_searches=6
        )
    else:
        listing = complete(DRAFT_MODEL, _SCAN_SYSTEM, scan_user, max_tokens=2500)

    # 2. RANK — fit + diversity
    rank_user = (
        f"CITY: {city}\n\n"
        f"PERSON PROFILE:\n{profile}\n\n"
        f"THEIR INTERESTS:\n{interests}\n\n"
        f"SCOUTED EVENTS:\n{listing}\n\n"
        f"ALREADY-SHOWN EVENTS (avoid duplicates):\n{avoid}\n\n"
        f"Return the best {n} events as specified — diverse across their interests."
    )
    raw = complete(DRAFT_MODEL, _RANK_SYSTEM + "\n\n" + EMPHASIS_GUIDE, rank_user, max_tokens=8000)
    data = extract_json(raw)

    created: list[Event] = []
    for it in data.get("events", [])[:n]:
        title = str(it.get("title", "")).strip()
        when = str(it.get("when", "")).strip()
        # Require a concrete date — skip events the model couldn't pin to a day.
        if not title or not when:
            continue
        try:
            fit = max(1, min(5, int(it.get("fit_score", 3))))
        except (TypeError, ValueError):
            fit = 3
        ev = Event(
            found_date=today,
            city=city,
            title=title,
            category=str(it.get("category", "")).strip(),
            venue=str(it.get("venue", "")).strip(),
            when=when,
            deadline=str(it.get("deadline", "")).strip(),
            price=str(it.get("price", "")).strip(),
            url=str(it.get("url", "")).strip(),
            fit_score=fit,
            why_fit=str(it.get("why_fit", "")).strip(),
            description=str(it.get("description", "")).strip(),
            source=str(it.get("source", "")).strip(),
        )
        session.add(ev)
        created.append(ev)
    session.commit()

    return {"found": len(created), "city": city, "date": today,
            "used_web": use_web, "ids": [e.id for e in created]}
