from typing import Optional, Dict, Any
from databases import Database
from sqlalchemy import Table, MetaData, Column, String, Integer, Numeric, Text, DateTime
from ..config import settings
from sqlalchemy import and_, or_

class JongsoRepository:
    def __init__(self):
        self.database = Database(settings.DATABASE_URL)
        self.metadata = MetaData()
        self.jongso_shops = Table(
            "jongso_shops",
            self.metadata,
            Column("id", String, primary_key=True),
            Column("name", Text, nullable=False),
            Column("address", Text),
            Column("lat", Numeric(10, 6)),
            Column("lng", Numeric(10, 6)),
            Column("rating", Numeric(2, 1)),
            Column("user_ratings_total", Integer),
            Column("smoking_status", Text),
            Column("positive_score", Integer),
            Column("negative_score", Integer),
            Column("summary", Text),
            Column("last_fetched_at", DateTime(timezone=True)),
        )

    async def connect(self):
        await self.database.connect()

    async def disconnect(self):
        await self.database.disconnect()

    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        query = self.jongso_shops.select().where(self.jongso_shops.c.name == name)
        return await self.database.fetch_one(query)

    async def get_by_name_and_address(self, name: str, address: str):
        query = self.jongso_shops.select().where(
            and_(
                self.jongso_shops.c.name == name,
                self.jongso_shops.c.address == address,
            )
        )
        return await self.database.fetch_one(query)

    async def search_by_keyword(self, keyword: str):
        query = self.jongso_shops.select().where(
            or_(
                self.jongso_shops.c.name.ilike(f"%{keyword}%"),
                self.jongso_shops.c.address.ilike(f"%{keyword}%"),
            )
        )
        return await self.database.fetch_all(query)

    async def create(self, shop_data: Dict[str, Any]) -> None:
        query = self.jongso_shops.insert().values(**shop_data)
        await self.database.execute(query)