from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.app.core.config import settings


class Base(DeclarativeBase):
    pass


EMB_DIM = settings.embedding_dim


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    subcontract_policy: Mapped[str] = mapped_column(String, nullable=False, default="allowed")

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contracts: Mapped[list["Contract"]] = relationship(back_populates="company")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    operations: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    template_id: Mapped[str | None] = mapped_column(String, nullable=True)
    has_price_rules: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    has_operations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_legacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    product_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="contracts")


class HistoricalCase(Base):
    __tablename__ = "historical_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[str | None] = mapped_column(String, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    object_name: Mapped[str] = mapped_column(String, nullable=False, default="")

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntentPrompt(Base):
    """Reference sentences for zero-shot intent classification via embeddings."""

    __tablename__ = "intent_prompts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    intent: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)
