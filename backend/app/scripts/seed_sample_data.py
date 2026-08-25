"""Seeds the sample hiring-domain schema (candidates, jobs, applications,
interviews). This is fixture data for the 3 query_templates seeded by
seed_query_templates.py — not part of DESIGN.md §5, see app/models/candidate.py.

Idempotent: skips entirely if any candidates already exist.

Run with:
    ./menv/bin/python -m app.scripts.seed_sample_data
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.models import Application, Candidate, Interview, Job

RNG_SEED = 42

FIRST_NAMES = [
    "Alex", "Bianca", "Carlos", "Dana", "Ethan", "Farah", "Grace", "Hassan",
    "Ivy", "Jamal", "Kira", "Liam", "Maya", "Noah", "Olga",
]
LAST_NAMES = [
    "Bennett", "Cruz", "Dietrich", "Esparza", "Fontaine", "Goldberg", "Huang",
    "Ibarra", "Jansen", "Kowalski", "Lindqvist", "Moreno", "Nakamura", "Osei",
]
SOURCES = ["referral", "job_board", "linkedin", "career_site", "agency"]
SOURCE_WEIGHTS = [0.25, 0.30, 0.25, 0.15, 0.05]

JOBS = [
    {"title": "Senior Backend Engineer", "department": "Engineering", "location": "Remote", "level": "senior", "status": "open"},
    {"title": "Backend Engineer", "department": "Engineering", "location": "Bangalore", "level": "mid", "status": "open"},
    {"title": "Account Executive", "department": "Sales", "location": "New York", "level": "mid", "status": "open"},
    {"title": "Product Designer", "department": "Design", "location": "Remote", "level": "senior", "status": "closed"},
    {"title": "Sales Development Rep", "department": "Sales", "location": "New York", "level": "junior", "status": "open"},
]

# One weighted draw per application across its whole lifecycle.
STAGE_WEIGHTS = {
    "applied": 0.15,
    "screen": 0.15,
    "interview": 0.15,
    "offer": 0.05,
    "hired": 0.25,
    "rejected": 0.25,
}
INTERVIEWED_STAGES = {"interview", "offer", "hired", "rejected"}

INTERVIEWERS = [
    "Dana Cole", "Priya Nair", "Marcus Webb", "Elena Torres",
    "Sam Okafor", "Jin Park", "Ravi Shah", "Nora Klein",
]
ROUNDS = ["phone_screen", "technical", "onsite", "final"]
RECOMMENDATIONS = ["strong_yes", "yes", "no", "strong_no"]

WINDOW_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2025, 12, 1, tzinfo=timezone.utc)


def _random_dt(start: datetime, end: datetime) -> datetime:
    if end <= start:
        return start
    seconds = random.randint(0, int((end - start).total_seconds()))
    return start + timedelta(seconds=seconds)


def _score() -> Decimal:
    return Decimal(f"{round(random.uniform(2.0, 9.5), 1):.1f}")


async def seed_sample_data() -> None:
    random.seed(RNG_SEED)
    sessionmaker = get_sessionmaker()
    now = datetime.now(timezone.utc)

    async with sessionmaker() as session:
        existing = await session.scalar(select(func.count()).select_from(Candidate))
        if existing:
            print(f"candidates already seeded ({existing} rows) — skipping")
            return

        jobs = [
            Job(
                title=spec["title"],
                department=spec["department"],
                location=spec["location"],
                level=spec["level"],
                status=spec["status"],
                opened_at=now - timedelta(days=random.randint(200, 500)),
            )
            for spec in JOBS
        ]
        session.add_all(jobs)
        await session.flush()

        candidates = []
        for i in range(40):
            first, last = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
            candidates.append(
                Candidate(
                    name=f"{first} {last}",
                    email=f"{first.lower()}.{last.lower()}{i}@example.com",
                    source=random.choices(SOURCES, weights=SOURCE_WEIGHTS)[0],
                    created_at=now - timedelta(days=random.randint(30, 700)),
                )
            )
        session.add_all(candidates)
        await session.flush()

        stage_pool, stage_weights = list(STAGE_WEIGHTS), list(STAGE_WEIGHTS.values())
        applications = []
        for _ in range(60):
            candidate, job = random.choice(candidates), random.choice(jobs)
            stage = random.choices(stage_pool, weights=stage_weights)[0]
            applied_at = _random_dt(WINDOW_START, WINDOW_END)

            decided_at, outcome = None, None
            if stage == "hired":
                decided_at = applied_at + timedelta(days=random.randint(14, 60))
                outcome = "hired"
            elif stage == "rejected":
                decided_at = applied_at + timedelta(days=random.randint(5, 45))
                outcome = random.choices(["rejected", "withdrawn"], weights=[0.8, 0.2])[0]

            applications.append(
                Application(
                    candidate_id=candidate.id,
                    job_id=job.id,
                    stage=stage,
                    applied_at=applied_at,
                    decided_at=decided_at,
                    outcome=outcome,
                )
            )
        session.add_all(applications)
        await session.flush()

        interviews = []
        for application in applications:
            if application.stage not in INTERVIEWED_STAGES:
                continue
            window_end_for_app = application.decided_at or now
            for round_name in ROUNDS[: random.randint(1, 3)]:
                scheduled_at = _random_dt(
                    application.applied_at,
                    max(window_end_for_app, application.applied_at + timedelta(days=1)),
                )
                scored = random.random() < 0.9
                if not scored:
                    score, recommendation = None, None
                else:
                    score = _score()
                    if application.outcome == "hired":
                        weights = [0.45, 0.40, 0.10, 0.05]
                    elif application.outcome in ("rejected", "withdrawn"):
                        weights = [0.05, 0.15, 0.40, 0.40]
                    else:
                        weights = [0.20, 0.35, 0.30, 0.15]
                    recommendation = random.choices(RECOMMENDATIONS, weights=weights)[0]

                interviews.append(
                    Interview(
                        application_id=application.id,
                        round=round_name,
                        interviewer=random.choice(INTERVIEWERS),
                        scheduled_at=scheduled_at,
                        score=score,
                        recommendation=recommendation,
                    )
                )
        session.add_all(interviews)

        await session.commit()
        print(
            f"seeded {len(jobs)} jobs, {len(candidates)} candidates, "
            f"{len(applications)} applications, {len(interviews)} interviews"
        )


if __name__ == "__main__":
    asyncio.run(seed_sample_data())
