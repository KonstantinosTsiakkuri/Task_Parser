from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Selection, Tag


class SelectionRepository:
    """Подборки и справочник тегов. Не коммитит — транзакцией управляет сервис."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_tag(self, tag_id: int) -> Tag | None:
        return await self.session.get(Tag, tag_id)

    async def create(self, rating: int, tag_id: int) -> Selection:
        """Создаёт подборку и сразу получает её id (flush), чтобы проставить его задачам."""
        selection = Selection(rating=rating, tag_id=tag_id)
        self.session.add(selection)
        await self.session.flush()
        return selection
