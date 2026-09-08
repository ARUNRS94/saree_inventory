"""Generic repository helpers."""
from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    """Small repository wrapper to keep persistence out of services and UI."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def get(self, entity_id: int) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def list(self) -> list[ModelT]:
        return list(self.session.scalars(select(self.model)))

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)
