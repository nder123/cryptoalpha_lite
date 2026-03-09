"""Repository for persisting runtime configuration overrides."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.database import db_session
from app.repositories.models import RuntimeSetting


class RuntimeSettingsRepository:
    """Persistence layer for runtime configuration overrides."""

    def __init__(self, storage_path: str | None = None) -> None:
        settings = get_settings()
        fallback_path = (
            storage_path or settings.runtime_overrides_path or "runtime_overrides.json"
        )
        path = Path(fallback_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path = path
        self._logger = get_logger(__name__)

    async def fetch_overrides(self) -> Dict[str, Any]:
        try:
            async with db_session() as session:
                overrides = await self._fetch_overrides(session)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("runtime_settings_fetch_db_failed", error=str(exc))
            overrides = await self._read_local()
        else:
            if overrides:
                await self._write_local(overrides)
        return overrides

    async def upsert_overrides(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        if not overrides:
            return await self.fetch_overrides()
        try:
            async with db_session() as session:
                await self._upsert(session, overrides)
                stored = await self._fetch_overrides(session)
        except Exception as exc:  # noqa: BLE001
            self._logger.error("runtime_settings_upsert_db_failed", error=str(exc))
            existing = await self._read_local()
            merged = {**existing, **overrides}
            await self._write_local(merged)
            return merged
        await self._write_local(stored)
        return stored

    async def _fetch_overrides(self, session: AsyncSession) -> Dict[str, Any]:
        result = await session.execute(select(RuntimeSetting))
        rows = result.scalars().all()
        return {row.key: row.value for row in rows}

    async def _upsert(self, session: AsyncSession, overrides: Dict[str, Any]) -> None:
        for key, value in overrides.items():
            stmt = select(RuntimeSetting).where(RuntimeSetting.key == key)
            result = await session.execute(stmt)
            try:
                setting = result.scalar_one()
            except NoResultFound:
                setting = RuntimeSetting(
                    key=key, value=value, updated_at=datetime.now(timezone.utc)
                )
                session.add(setting)
            else:
                setting.value = value
                setting.updated_at = datetime.now(timezone.utc)

    async def _read_local(self) -> Dict[str, Any]:
        path = self._storage_path

        def _read() -> Dict[str, Any]:
            if not path.exists():
                return {}
            try:
                with path.open("r", encoding="utf-8") as file:
                    data = json.load(file)
            except json.JSONDecodeError:
                data = {}
            return data

        return await asyncio.to_thread(_read)

    async def _write_local(self, overrides: Dict[str, Any]) -> None:
        path = self._storage_path

        def _write() -> None:
            with path.open("w", encoding="utf-8") as file:
                json.dump(overrides, file, ensure_ascii=False, indent=2, sort_keys=True)

        await asyncio.to_thread(_write)
