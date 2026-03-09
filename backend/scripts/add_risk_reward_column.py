from __future__ import annotations

"""Ensure trade_sessions has risk_reward_ratio column."""

import asyncio

from sqlalchemy import text

from app.infrastructure.database import get_engine


async def ensure_column() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'trade_sessions'
                  AND column_name = 'risk_reward_ratio'
                """
            )
        )
        exists = result.fetchone() is not None
        if exists:
            print("Column risk_reward_ratio already exists")
            return
        await conn.execute(
            text(
                """
                ALTER TABLE trade_sessions
                ADD COLUMN risk_reward_ratio NUMERIC(18, 6)
                """
            )
        )
        print("Column risk_reward_ratio added to trade_sessions")


def main() -> None:
    asyncio.run(ensure_column())


if __name__ == "__main__":
    main()
