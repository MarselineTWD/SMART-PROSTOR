from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
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


class TZTemplateORM(Base):
    """Каталог шаблонов ТЗ, между которыми переключается пользователь."""

    __tablename__ = "tz_templates"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stage_presets: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TZDocumentORM(Base):
    """Сохранённое техническое задание, отображается на странице «Мои ТЗ»."""

    __tablename__ = "tz_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    template_key: Mapped[str] = mapped_column(String, nullable=False)
    template_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    object_name: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    executor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    ready_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requisites: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    chat: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --- Справочные данные ПРОСТОР, перенесённые из xlsx (миграция 0003) ----------
# Источник: «Выгрузка из системы» (Компании, Договоры, Договор+РС, Договор+продукты,
# Продукты+расценки, Продукты+Операции). Используются для расчёта сроков по этапам
# и построения роадмапа для каждого подрядчика.


class ProcurementCompanyORM(Base):
    __tablename__ = "pr_companies"

    company_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    info: Mapped[str] = mapped_column(Text, nullable=False, default="")
    services: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class ProcurementContractORM(Base):
    __tablename__ = "pr_contracts"

    contract_id: Mapped[str] = mapped_column(String, primary_key=True)
    number: Mapped[str] = mapped_column(String, nullable=False, default="")
    company_id: Mapped[str] = mapped_column(String, nullable=False)


class ProcurementProductORM(Base):
    __tablename__ = "pr_products"

    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, default="")


class ProcurementContractProductORM(Base):
    __tablename__ = "pr_contract_products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(String, nullable=False)
    contract_id: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)


class ProcurementPriceORM(Base):
    __tablename__ = "pr_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    price_id: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    price_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    measurement_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    measurement_type: Mapped[str] = mapped_column(String, nullable=False, default="")


class ProcurementOperationORM(Base):
    __tablename__ = "pr_operations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    operation_name: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ProcurementCalcORM(Base):
    __tablename__ = "pr_calcs"

    calc_id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String, nullable=False)
    contract_id: Mapped[str | None] = mapped_column(String, nullable=True)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ProcurementStageORM(Base):
    __tablename__ = "pr_stages"

    stage_id: Mapped[str] = mapped_column(String, primary_key=True)
    calc_id: Mapped[str] = mapped_column(String, nullable=False)
    parent_stage_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documentation: Mapped[str] = mapped_column(Text, nullable=False, default="")
