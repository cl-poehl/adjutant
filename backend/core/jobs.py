"""Job scout — finds roles that are a strong PROFILE FIT *and* a genuine career
step-up with high comp, not just keyword matches.

Two-stage, mirroring the idea engine:
  1. SCAN — Claude with live web search hunts current openings + comp benchmarks
     across the founder's target roles/locations.
  2. RANK — Claude scores each on profile-fit AND career-trajectory value, keeps
     only roles that are both a real match and a meaningful step up.
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
from db.models import Job

log = logging.getLogger("adjutant.jobs")

_SCAN_SYSTEM = """You are an executive recruiter using web search. Given a candidate \
profile and their preferences, find SPECIFIC, currently-open roles that maximise their \
LONG-TERM career capital — not just the next paycheck. Optimise for the joint of: durable \
career success, compensation (incl. equity upside), and a path to long-term work-life \
control. Short-term sacrifice is acceptable if the long-term payoff is high.

Weight toward roles with: real equity / upside, elite signal & learning that compounds \
(top labs, frontier companies, strong founding teams), durable skill-building in the \
candidate's moat (drawn from their profile), and compensation and locations that match \
their stated preferences. Judge comp, equity, and long-term optionality on merit.

Search real sources (company career pages, LinkedIn, YC/wellfound, Levels.fyi for comp). \
For each role capture: exact title, company, location/remote, comp estimate (Levels.fyi / \
market if not posted — mark 'est.'), source URL, and what makes it long-term valuable. \
Return 8–15 concrete, nameable openings with sources/dates."""

_RANK_SYSTEM = """You are a sharp long-term career advisor for ONE candidate. You get their \
profile and scouted roles. Keep only roles that are BOTH a strong profile fit AND high \
LONG-TERM value (career capital + comp + optionality over 5–10 years — equity, elite signal, \
moat-building, and a path to eventually setting their own terms). Drop lateral moves and \
weak fits. US/SF roles are first-class for kickstart + salary; rank them on merit.

For every role, give a CONCRETE readiness step: the single most important thing to do to \
become a strong candidate or unblock it (e.g. 'ship a first-author paper to clear the \
publication bar', 'get a warm intro through a shared contact', 'start visa groundwork \
early if the role needs one').

Respond with ONLY this JSON, no prose:
{
  "jobs": [
    {
      "title": "<role title>",
      "company": "<company>",
      "location": "<location / remote>",
      "comp": "<salary/comp estimate; mark 'est.' if inferred>",
      "url": "<application or posting URL if known, else ''>",
      "fit_score": <integer 1–5: how well their profile matches today>,
      "trajectory": <integer 1–5: long-term career value (capital + comp + optionality)>,
      "why_fit": "<the candidate's specific edges that match this role>",
      "why_step_up": "<why this maximises long-term success/comp/optionality>",
      "readiness": "<the single most important concrete step to land or unblock it>",
      "watch_outs": "<honest risks, gaps, or red flags>",
      "source": "<where it was found>"
    }
  ]
}
Order by (fit_score + trajectory) descending. Include roles scoring >=4 on at least one axis \
and >=3 on the other. Be honest in watch_outs — do not oversell."""

# Default search guidance; override with your specifics via the JOB_PREFS env var.
_DEFAULT_PREFS = (
    "Optimise for long-term career success, compensation, and work-life control "
    "(long horizon; short-term sacrifice OK if the payoff is high). Target roles and "
    "seniority that build on the candidate's strongest moat from their profile "
    "(founding/early engineer, research scientist or engineer at strong labs and "
    "frontier companies, or senior/staff applied roles), valuing equity and elite "
    "signal over raw base. Draw the candidate's fields, locations, comp bar, and "
    "constraints from their profile; set anything specific via the JOB_PREFS env var."
)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def scout_jobs(session: Session, n: int = 8, use_web: bool = True) -> dict:
    profile = founder.load_profile()
    prefs = os.getenv("JOB_PREFS", _DEFAULT_PREFS)

    recent = session.execute(
        select(Job.title, Job.company).order_by(Job.created_at.desc()).limit(40)
    ).all()
    avoid = "\n".join(f"- {t} @ {c}" for t, c in recent) or "(none yet)"

    # 1. SCAN — live openings + comp
    scan_user = (
        f"CANDIDATE PROFILE:\n{profile}\n\n"
        f"PREFERENCES:\n{prefs}\n\n"
        "Find specific currently-open roles now, with comp estimates and sources."
    )
    if use_web:
        listing = complete_with_search(DRAFT_MODEL, _SCAN_SYSTEM, scan_user, max_tokens=3000)
    else:
        listing = complete(DRAFT_MODEL, _SCAN_SYSTEM, scan_user, max_tokens=2000)

    # 2. RANK — fit × trajectory
    rank_user = (
        f"CANDIDATE PROFILE:\n{profile}\n\n"
        f"PREFERENCES:\n{prefs}\n\n"
        f"SCOUTED ROLES:\n{listing}\n\n"
        f"ALREADY-SHOWN ROLES (avoid duplicates):\n{avoid}\n\n"
        f"Return the best {n} roles as specified."
    )
    raw = complete(DRAFT_MODEL, _RANK_SYSTEM + "\n\n" + EMPHASIS_GUIDE, rank_user, max_tokens=8000)
    data = extract_json(raw)

    today = _today()
    created: list[Job] = []
    for it in data.get("jobs", [])[:n]:
        title = str(it.get("title", "")).strip()
        if not title:
            continue

        def _score(key: str) -> int:
            try:
                return max(1, min(5, int(it.get(key, 3))))
            except (TypeError, ValueError):
                return 3

        job = Job(
            found_date=today,
            title=title,
            company=str(it.get("company", "")).strip(),
            location=str(it.get("location", "")).strip(),
            comp=str(it.get("comp", "")).strip(),
            url=str(it.get("url", "")).strip(),
            fit_score=_score("fit_score"),
            trajectory=_score("trajectory"),
            why_fit=str(it.get("why_fit", "")).strip(),
            why_step_up=str(it.get("why_step_up", "")).strip(),
            readiness=str(it.get("readiness", "")).strip(),
            watch_outs=str(it.get("watch_outs", "")).strip(),
            source=str(it.get("source", "")).strip(),
        )
        session.add(job)
        created.append(job)
    session.commit()

    return {"found": len(created), "date": today, "used_web": use_web,
            "ids": [j.id for j in created]}
