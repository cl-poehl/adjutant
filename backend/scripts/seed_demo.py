"""Seed a database with realistic, entirely fictional demo data.

Lets anyone preview the whole UI without connecting a real mailbox — and is what
the repo's screenshots are captured from, so no real mail or PII is ever shown.

Point it at a throwaway database and run it:

    DATABASE_URL=sqlite:///./adjutant_demo.db python -m scripts.seed_demo

It wipes and repopulates every table, so re-running is safe. Never run it
against your real database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.models import (
    Email, Event, Habit, HabitLog, Idea, Job, JournalEntry, Note, Project,
    ResearchBrief, ResearchFinding, ResearchTopic, Setting,
)
from db.session import SessionLocal, init_db

NOW = datetime.now(timezone.utc)


def _day(offset: int = 0) -> str:
    return (NOW + timedelta(days=offset)).strftime("%Y-%m-%d")


def _dt(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)


def seed() -> None:
    init_db()
    s = SessionLocal()

    # Fresh slate.
    for model in (HabitLog, Habit, Note, JournalEntry, ResearchFinding,
                  ResearchTopic, ResearchBrief, Event, Job, Idea, Email,
                  Project, Setting):
        s.query(model).delete()
    s.commit()

    # ── Projects (a couple are muted "digest" feed buckets) ──────────────────
    projects = {
        "Fieldwork Robotics": Project(name="Fieldwork Robotics",
            description="The core product: autonomous inspection drones. Threads with the "
            "hardware team, pilot customers, and the safety-cert consultant."),
        "Fundraising": Project(name="Fundraising",
            description="Seed round — investor intros, updates, data-room requests, term sheets."),
        "Hiring": Project(name="Hiring",
            description="Candidate pipeline, referrals, and scheduling for the founding-engineer role."),
        "Personal & Admin": Project(name="Personal & Admin",
            description="Invoices, travel, appointments, and anything logistical."),
        "Industry Reading": Project(name="Industry Reading", digest=True,
            description="Newsletters and digests about robotics, AI, and startups."),
        "Product Updates": Project(name="Product Updates", digest=True,
            description="Transactional and changelog mail from the SaaS tools we use."),
    }
    for p in projects.values():
        s.add(p)
    s.commit()

    def pid(name: str) -> int:
        return projects[name].id

    # ── Threads ──────────────────────────────────────────────────────────────
    # snippet doubles as the reconstructed message body in the demo detail view.
    emails = [
        Email(provider="demo", provider_thread_id="demo-1", project_id=pid("Fundraising"),
              subject="Re: Seed round — following up after the demo",
              last_sender="Priya Anand (Northwind Ventures)", urgency="high",
              status="drafted", processed=True, last_seen_message_id="demo-1-m2",
              snippet="Hi — great meeting you Tuesday, the flight demo was genuinely impressive. "
              "We'd like to move forward. Could you send the data room and your current cap table by "
              "Thursday so we can start diligence before our partner meeting next week?",
              draft_body="Hi Priya,\n\nThank you — it was a pleasure, and I'm glad the demo landed. "
              "I'll send over the data room and cap table today so you have everything ahead of the "
              "partner meeting. Happy to walk your team through the unit economics live if that helps.\n\n"
              "Best,\nAlex"),
        Email(provider="demo", provider_thread_id="demo-2", project_id=pid("Hiring"),
              subject="Founding engineer — Wednesday or Thursday?",
              last_sender="Daniel Okafor", urgency="normal",
              status="drafted", processed=True, last_seen_message_id="demo-2-m1",
              snippet="Thanks for the quick turnaround on the take-home — I really enjoyed the "
              "path-planning problem. I'm free Wednesday afternoon or Thursday morning for the final "
              "conversation. Would either work on your side?",
              draft_body="Hi Daniel,\n\nGreat to hear — the team liked your write-up a lot. "
              "Thursday morning works well; shall we say 10:00? I'll send a calendar invite with a "
              "video link and loop in two of the engineers.\n\nBest,\nAlex"),
        Email(provider="demo", provider_thread_id="demo-3", project_id=pid("Fieldwork Robotics"),
              subject="Safety certification — missing documents",
              last_sender="Bureau Veritas", urgency="high",
              status="needs_reply", processed=True, last_seen_message_id="demo-3-m1",
              snippet="To proceed with the EN 4709-2 assessment we still need the updated failsafe "
              "test logs and the geofencing configuration. The audit slot is reserved for the 28th; "
              "we'd need the documents at least five working days beforehand.",
              draft_body=None),
        Email(provider="demo", provider_thread_id="demo-4", project_id=pid("Fieldwork Robotics"),
              subject="Pilot feedback from the wind-farm inspection",
              last_sender="Sofia Lindqvist (Vindkraft AB)", urgency="normal",
              status="needs_reply", processed=True, last_seen_message_id="demo-4-m2",
              snippet="The crew was impressed with the turbine-blade coverage — 40% faster than the "
              "rope team. Two asks: can the report export to our maintenance system, and could we add "
              "a second site next month?",
              draft_body=None),
        Email(provider="demo", provider_thread_id="demo-5", project_id=pid("Personal & Admin"),
              subject="Invoice INV-2043 — due in 3 days", last_sender="Cloud GPU Co.",
              urgency="normal", status="classified", processed=True,
              snippet="Your monthly invoice for GPU compute is attached. Amount due: €1,180. "
              "Payment is due within 3 days of receipt."),
        Email(provider="demo", provider_thread_id="demo-6", project_id=pid("Fundraising"),
              subject="Intro: you <> Mara at Kestrel Capital", last_sender="Tom Becker",
              urgency="normal", status="sent", processed=True, awaiting_since=_dt(30),
              snippet="Happy to make the intro — Mara leads their hardware investments and is "
              "exactly who you should talk to. Mara, meet Alex, founder of the drone-inspection "
              "startup I mentioned. I'll let you two take it from here."),
        Email(provider="demo", provider_thread_id="demo-7", project_id=pid("Industry Reading"),
              subject="The Robotics Report — Issue #212", last_sender="The Robotics Report",
              status="ignored", processed=True,
              snippet="This week: humanoid funding cools, a breakthrough in tactile sensing, and why "
              "warehouse automation is quietly eating logistics."),
        Email(provider="demo", provider_thread_id="demo-8", project_id=pid("Industry Reading"),
              subject="Deep Learning Weekly", last_sender="DL Weekly", status="ignored",
              processed=True, snippet="Papers, releases, and jobs in ML — curated every Friday."),
        Email(provider="demo", provider_thread_id="demo-9", project_id=pid("Product Updates"),
              subject="Your deployment succeeded", last_sender="Vercel", status="ignored",
              processed=True, snippet="Production deployment for adjutant-web completed in 41s."),
        Email(provider="demo", provider_thread_id="demo-10", project_id=pid("Hiring"),
              subject="Referral — strong controls engineer", last_sender="Nadia Rahman",
              urgency="normal", status="classified", processed=True,
              snippet="I worked with Jonas at my last company — best controls engineer I know, and "
              "he's exploring early-stage robotics. Want me to introduce you?"),
        Email(provider="demo", provider_thread_id="demo-11", project_id=pid("Personal & Admin"),
              subject="Appointment confirmed — Thu 14:30", last_sender="Dental Practice Mitte",
              status="classified", processed=True,
              snippet="This confirms your appointment on Thursday at 14:30. Please arrive 10 minutes early."),
        Email(provider="demo", provider_thread_id="demo-12", project_id=pid("Fieldwork Robotics"),
              subject="Re: Battery supplier — revised lead times", last_sender="Kenji Watanabe",
              urgency="normal", status="drafted", processed=True, last_seen_message_id="demo-12-m3",
              snippet="Lead times moved from 6 to 10 weeks for the high-density cells. If you can "
              "commit to a Q3 volume now, we can hold the original price. Otherwise a 4% increase applies.",
              draft_body="Hi Kenji,\n\nThanks for the heads-up. We can commit to the Q3 volume to hold "
              "pricing — let me confirm the exact quantity with our production plan and come back to you "
              "by Friday. Could you send the updated spec sheet in the meantime?\n\nBest,\nAlex"),
    ]
    for e in emails:
        e.updated_at = _dt(hash(e.provider_thread_id) % 72)
        s.add(e)

    # ── Ideas ────────────────────────────────────────────────────────────────
    def idea(title, pitch, domain, score, why_now, why_you, first_step, market, signal):
        return Idea(created_date=_day(), title=title, pitch=pitch, domain=domain, score=score,
                    why_now=why_now, why_you=why_you, first_step=first_step, market=market,
                    signal=signal, status="new")
    s.add_all([
        idea("Drone-in-a-box for solar farms",
             "Permanently-stationed autonomous drones that inspect utility-scale solar sites on a "
             "schedule and flag defective panels before yield drops.",
             "Robotics · Energy", 5,
             "==Solar capacity is being added faster than crews can inspect it==, and thermal-defect "
             "detection is now reliable.",
             "You already have the autonomy stack and cert relationships from the wind-inspection work.",
             "Cold-email 10 solar O&M providers offering a paid pilot on one site.",
             "$2.1B inspection-services market growing 14%/yr.",
             "Two wind customers have **already asked** whether you cover solar."),
        idea("Failsafe-log compliance copilot",
             "A tool that turns raw drone flight logs into the exact documents safety auditors "
             "require, mapped to EN 4709-2 clauses.",
             "RegTech · Robotics", 4,
             "Every commercial drone operator hits the same certification paperwork wall you just did.",
             "You're living the pain right now and know precisely what auditors want.",
             "Template the documents you're preparing for your own audit; sell them as a product.",
             "Niche but sticky; expands to every regulated autonomy vertical.",
             "Your own certifier volunteered that operators ask them for this constantly."),
        idea("Marketplace for idle inspection crews",
             "Match certified rope-access and drone crews with operators who need one-off inspections.",
             "Marketplace", 3,
             "Inspection demand is spiky and crews sit idle between jobs.",
             "You know both sides of this market from the pilot work.",
             "Interview five crews about utilization and willingness to list.",
             "Fragmented; marketplace liquidity is the hard part.",
             "Anecdotal only so far — validate before building."),
        idea("Turbine-blade defect dataset",
             "License the labelled defect imagery you're accumulating as a benchmark + training set.",
             "Data · ML", 3,
             "High-quality labelled inspection data is scarce and valuable for model builders.",
             "You're generating this data as a byproduct of every pilot.",
             "Check customer contracts for data-rights language before anything else.",
             "Small but high-margin; strategic more than standalone.",
             "Inbound interest from one ML team already."),
    ])

    # ── Jobs ─────────────────────────────────────────────────────────────────
    def job(title, company, location, comp, fit, traj, why_fit, why_step_up, watch, ready, source):
        return Job(found_date=_day(), title=title, company=company, location=location, comp=comp,
                   fit_score=fit, trajectory=traj, why_fit=why_fit, why_step_up=why_step_up,
                   watch_outs=watch, readiness=ready, source=source, url="https://example.com/job",
                   status="new")
    s.add_all([
        job("Head of Autonomy", "Skyward Robotics", "Remote (EU)", "€160–190k + equity", 5, 5,
            "Exactly your stack: perception, path-planning, and field autonomy at scale.",
            "Team lead scope over a 12-person org — a real step up from founder-IC work.",
            "Series-B pace; make sure the safety culture matches yours.",
            "Strong fit today — lead with the wind-farm results.", "Wellfound"),
        job("Founding Engineer, Perception", "Orchard AI", "Berlin", "€130–150k + 1.0%", 4, 4,
            "Agri-robotics perception; overlaps heavily with your inspection work.",
            "Ground-floor equity and technical ownership.",
            "Pre-seed — diligence the runway.",
            "Ready; highlight your labelled-dataset experience.", "Referral"),
        job("Robotics Safety Lead", "Bureau Veritas", "Paris / Hybrid", "€110–135k", 3, 4,
            "Your fresh EN 4709-2 experience is directly relevant.",
            "Moves you from operator to standard-setter.",
            "Large org; slower pace than you're used to.",
            "Would need to frame cert work as a strength.", "LinkedIn"),
        job("Applied ML Engineer", "Vantage Grid", "Remote", "€120–145k", 3, 3,
            "Defect-detection models on imagery — adjacent to your pipeline.",
            "Deepens ML depth if you want to specialize.",
            "Less autonomy/hardware than your core.",
            "Solid but lateral.", "Company site"),
    ])

    # ── Events ───────────────────────────────────────────────────────────────
    def event(title, category, venue, when, price, fit, why, desc):
        return Event(found_date=_day(), city="Berlin", title=title, category=category, venue=venue,
                     when=when, deadline="", price=price, fit_score=fit, why_fit=why,
                     description=desc, url="https://example.com/event", source="Meetup", status="new")
    s.add_all([
        event("Berlin Robotics Meetup", "Tech", "AI Campus", _day(3), "Free", 5,
              "Exactly your crowd — perception and autonomy engineers, several hiring.",
              "Monthly talks + demos; strong for hiring and partnerships."),
        event("Hardware Founders Dinner", "Networking", "Kreuzberg", _day(6), "€25", 4,
              "Small-group dinner with other hardware founders — rare and high-signal.",
              "Curated table of 12; peer support and intros."),
        event("Forest Trail Run — 15km", "Sport", "Grunewald", _day(9), "€30", 3,
              "Matches your interest in trail running; good reset before the raise.",
              "Scenic route with 700m elevation."),
        event("Jazz at Moods", "Music", "Kulturbrauerei", _day(4), "€38", 2,
              "A relaxed evening out if you want a break.",
              "Resident quartet, late set."),
    ])

    # ── Research brief + topics ──────────────────────────────────────────────
    s.add(ResearchBrief(day=_day(),
        for_you="• BVLOS rules are loosening in the EU — [EASA update](https://example.com) — expands "
        "your addressable inspection market\n"
        "• New thermal-defect model beats prior SOTA on PV panels — [arXiv](https://example.com)\n"
        "• Grant call: EU robotics-for-energy, €2M, deadline in 6 weeks — [portal](https://example.com)",
        ventures="• Competitor Skydio raised a Series E; pushing into infrastructure inspection — "
        "[TechCrunch](https://example.com)\n"
        "• Wind O&M spend forecast up 11% next year — [report](https://example.com)\n"
        "• Insurer now offers premium discounts for drone-inspected sites — [brief](https://example.com)"))
    t1 = ResearchTopic(query="Autonomous inspection & BVLOS regulation in the EU", track="you",
                       cadence="daily", status="done", last_run_at=NOW,
                       last_summary="Regulatory tailwinds; two competitor moves worth watching.")
    t2 = ResearchTopic(query="Wind & solar O&M market and competitor funding", track="venture",
                       cadence="daily", status="done", last_run_at=NOW,
                       last_summary="Market growing double digits; insurers starting to incentivize.")
    s.add_all([t1, t2])
    s.flush()
    s.add_all([
        ResearchFinding(topic_id=t1.id, run_date=_day(), title="EASA proposes lighter BVLOS approvals",
            detail="Standard scenarios expanded, cutting approval time for routine inspection flights.",
            why_matters="Directly widens your serviceable market.", importance=5,
            url="https://example.com", source="EASA", status="new"),
        ResearchFinding(topic_id=t2.id, run_date=_day(), title="Skydio Series E targets infrastructure",
            detail="Raise earmarked for utilities and infrastructure inspection.",
            why_matters="Validates the space; sharpens competitive positioning.", importance=4,
            url="https://example.com", source="TechCrunch", status="new"),
    ])

    # ── Habits + journal + notes ─────────────────────────────────────────────
    habits = [Habit(name="Deep work block", emoji="🎯", sort=0),
              Habit(name="Move / run", emoji="🏃", sort=1),
              Habit(name="Read 20 min", emoji="📚", sort=2),
              Habit(name="No phone before 9", emoji="🌅", sort=3)]
    s.add_all(habits)
    s.flush()
    for i, h in enumerate(habits):
        for d in range(0, 21):
            if (d + i) % 3 != 0:  # a realistic, imperfect streak
                s.add(HabitLog(habit_id=h.id, day=_day(-d)))

    s.add(JournalEntry(day=_day(), mood="🙂",
        text="Wind-farm pilot went better than hoped — 40% faster than the rope team, and Sofia "
        "wants a second site. Northwind is ready to start diligence. Need to get the data room "
        "tight and the failsafe logs to the certifier before the 28th. Feeling the pull between "
        "shipping and fundraising; keep the mornings for deep work."))
    s.add_all([
        Note(kind="note", title="Fundraise narrative",
             content="Lead with the wind-farm result (40% faster, safer). Framing: 'inspection is a "
             "recurring, regulated, data-generating wedge into infrastructure autonomy.'",
             tags="fundraising,strategy"),
        Note(kind="bookmark", title="EN 4709-2 standard — overview", url="https://example.com/en4709",
             content="Reference for the safety-certification requirements.", tags="compliance,safety"),
        Note(kind="note", title="Pilot pricing thoughts",
             content="Per-site subscription + per-report fee. Anchor on cost of a rope team per day.",
             tags="pricing,product"),
    ])

    s.commit()
    counts = {m.__name__: s.query(m).count() for m in
              (Project, Email, Idea, Job, Event, ResearchFinding, Habit, Note)}
    print("seeded demo data:", counts)


if __name__ == "__main__":
    seed()
