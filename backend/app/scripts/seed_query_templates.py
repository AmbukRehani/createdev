"""Seeds the 3 curated query_templates (DESIGN.md §5) against the sample
hiring-domain schema seeded by seed_sample_data.py.

Idempotent: existing intents are left untouched (create-if-missing).

Run with:
    ./menv/bin/python -m app.scripts.seed_query_templates
"""
import asyncio

from app.db.session import get_sessionmaker
from app.repositories import QueryTemplateRepository

TEMPLATES = [
    {
        "intent": "top_sources_by_hires",
        "description": (
            "Ranks candidate acquisition sources by number of hired "
            "applications in a given year, most hires first."
        ),
        # Bind names (:year, :limit) must exactly match params_schema below
        # (DESIGN §8 invariant). `limit` here is a curated, schema-capped
        # "top N" parameter — not the executor's row-safety cap, which is
        # applied separately and unconditionally.
        "sql_text": """
            SELECT c.source AS source, COUNT(*) AS hires
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            WHERE a.outcome = 'hired'
              AND EXTRACT(YEAR FROM a.decided_at) = :year
            GROUP BY c.source
            ORDER BY hires DESC
            LIMIT :limit
        """.strip(),
        "params_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "minimum": 2000,
                    "maximum": 2100,
                    "description": "Calendar year applications were decided in",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                    "description": "Number of top sources to return",
                },
            },
            "required": ["year", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "intent": "avg_time_to_hire_by_dept",
        "description": (
            "Average days from application to hire decision for a "
            "department in a given year."
        ),
        "sql_text": """
            SELECT j.department AS department,
                   AVG(EXTRACT(EPOCH FROM (a.decided_at - a.applied_at)) / 86400.0)
                       AS avg_days_to_hire,
                   COUNT(*) AS hires
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            WHERE a.outcome = 'hired'
              AND j.department = :department
              AND EXTRACT(YEAR FROM a.decided_at) = :year
            GROUP BY j.department
        """.strip(),
        "params_schema": {
            "type": "object",
            "properties": {
                "department": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Department name, e.g. Engineering",
                },
                "year": {
                    "type": "integer",
                    "minimum": 2000,
                    "maximum": 2100,
                    "description": "Calendar year hire decisions were made in",
                },
            },
            "required": ["department", "year"],
            "additionalProperties": False,
        },
    },
    {
        "intent": "interview_pass_rate_by_round",
        "description": (
            "Pass rate per interview round for a given job title, based "
            "on interviewer recommendations."
        ),
        "sql_text": """
            SELECT i.round AS round,
                   COUNT(*) FILTER (WHERE i.recommendation IN ('yes', 'strong_yes'))
                       AS passed,
                   COUNT(*) FILTER (WHERE i.recommendation IS NOT NULL) AS scored,
                   ROUND(
                       COUNT(*) FILTER (WHERE i.recommendation IN ('yes', 'strong_yes'))::numeric
                       / NULLIF(COUNT(*) FILTER (WHERE i.recommendation IS NOT NULL), 0),
                       3
                   ) AS pass_rate
            FROM interviews i
            JOIN applications a ON a.id = i.application_id
            JOIN jobs j ON j.id = a.job_id
            WHERE j.title = :job_title
            GROUP BY i.round
            ORDER BY i.round
        """.strip(),
        "params_schema": {
            "type": "object",
            "properties": {
                "job_title": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Exact job title, e.g. Senior Backend Engineer",
                },
            },
            "required": ["job_title"],
            "additionalProperties": False,
        },
    },
]


async def seed_query_templates() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = QueryTemplateRepository(session)
        created, skipped = 0, 0
        for spec in TEMPLATES:
            if await repo.get_by_intent(spec["intent"]) is not None:
                skipped += 1
                continue
            await repo.create(**spec)
            created += 1
        await session.commit()
        print(f"query_templates: created {created}, already present {skipped}")


if __name__ == "__main__":
    asyncio.run(seed_query_templates())
