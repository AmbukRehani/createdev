"""The only place ORM queries for query_templates live."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query_template import QueryTemplate


class QueryTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_intent(self, intent: str) -> QueryTemplate | None:
        result = await self._session.execute(
            select(QueryTemplate).where(QueryTemplate.intent == intent)
        )
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[QueryTemplate]:
        result = await self._session.execute(
            select(QueryTemplate)
            .where(QueryTemplate.enabled.is_(True))
            .order_by(QueryTemplate.intent)
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        intent: str,
        description: str,
        sql_text: str,
        params_schema: dict,
        enabled: bool = True,
    ) -> QueryTemplate:
        template = QueryTemplate(
            intent=intent,
            description=description,
            sql_text=sql_text,
            params_schema=params_schema,
            enabled=enabled,
        )
        self._session.add(template)
        await self._session.flush()
        return template
