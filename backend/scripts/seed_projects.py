"""Seed example projects (idempotent). Edit the list, then run from backend/:

    python -m scripts.seed_projects
"""
from __future__ import annotations

from sqlalchemy import select

from db.models import Project
from db.session import SessionLocal, init_db

PROJECTS = [
    {
        "name": "Thesis",
        "description": "Everything about my master's thesis: supervisor emails, "
        "literature, deadlines, drafts, feedback rounds.",
    },
    {
        "name": "Side Project",
        "description": "My software side project: collaborators, users, hosting, "
        "domain/billing notices for it.",
    },
]


def main() -> None:
    init_db()
    with SessionLocal() as session:
        for spec in PROJECTS:
            if session.scalar(select(Project).where(Project.name == spec["name"])):
                print(f"exists: {spec['name']}")
                continue
            session.add(Project(**spec))
            print(f"created: {spec['name']}")
        session.commit()


if __name__ == "__main__":
    main()
