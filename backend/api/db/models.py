"""
Modelos SQLAlchemy da API AncoPlat.

Reflete o schema definido na Seção 2 do docs/plano_F2_api.md. Uso
declarativo (Base = declarative_base). Todos os modelos moram aqui para
simplicidade: 4 tabelas, sem ganho real em separar por arquivo.

Tabelas:
  - line_types    (já existe — populada por backend/data/seed_catalog.py)
  - cases         (nova — um caso = input do solver + metadados)
  - executions    (nova — histórico de execuções, retenção 10 últimas por caso)
  - app_config    (nova — chave/valor de configurações globais)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.api.db.session import Base


class LineTypeRecord(Base):
    """
    Catálogo de tipos de linha (F1a). Schema já populado por
    backend/data/seed_catalog.py com 522 entradas (legacy_qmoor) em SI.

    Este modelo apenas descreve a tabela para uso via ORM. Criação e
    seed inicial continuam responsabilidade do script de seed.
    """

    __tablename__ = "line_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_type: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    base_unit_system: Mapped[str] = mapped_column(Text, nullable=False)
    diameter: Mapped[float] = mapped_column(Float, nullable=False)
    dry_weight: Mapped[float] = mapped_column(Float, nullable=False)
    wet_weight: Mapped[float] = mapped_column(Float, nullable=False)
    break_strength: Mapped[float] = mapped_column(Float, nullable=False)
    modulus: Mapped[float | None] = mapped_column(Float, nullable=True)
    qmoor_ea: Mapped[float | None] = mapped_column(Float, nullable=True)
    gmoor_ea: Mapped[float | None] = mapped_column(Float, nullable=True)
    seabed_friction_cf: Mapped[float] = mapped_column(Float, nullable=False)
    data_source: Mapped[str] = mapped_column(Text, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(Text, nullable=True)
    serial_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class CaseRecord(Base):
    """Caso de ancoragem salvo: input do solver + metadados para listagem."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Input canônico do solver (LineSegment + BoundaryConditions + SeabedConfig
    # + SolverConfig + criteria_profile + user_limits) serializado.
    input_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Desnormalizações para filtros rápidos (não são source of truth).
    line_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    water_depth: Mapped[float] = mapped_column(Float, nullable=False)
    line_length: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_profile: Mapped[str] = mapped_column(
        String(40), nullable=False, default="MVP_Preliminary"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    executions: Mapped[list["ExecutionRecord"]] = relationship(
        "ExecutionRecord",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExecutionRecord.executed_at.desc()",
    )

    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_cases_name_nonempty"),
        CheckConstraint("water_depth > 0", name="ck_cases_depth_positive"),
        CheckConstraint("line_length > 0", name="ck_cases_length_positive"),
        Index("idx_cases_name", "name"),
        Index("idx_cases_updated", "updated_at"),
    )


class ExecutionRecord(Base):
    """
    Histórico de execuções do solver para um caso.

    Política de retenção: apenas as 10 execuções mais recentes por caso
    são mantidas. Truncagem ocorre no service após cada solve bem-sucedido.
    """

    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    # SolverResult completo serializado em JSON
    result_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Desnormalizações
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    alert_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fairlead_tension: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_horz_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    utilization: Mapped[float | None] = mapped_column(Float, nullable=True)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    case: Mapped[CaseRecord] = relationship("CaseRecord", back_populates="executions")

    __table_args__ = (
        Index("idx_exec_case", "case_id", "executed_at"),
    )


class AppConfigRecord(Base):
    """Configurações globais da app (chave/valor)."""

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )


class MooringSystemRecord(Base):
    """
    Sistema de ancoragem multi-linha (F5.4).

    Armazena a configuração completa em `config_json` (mesma estratégia
    de `cases.input_json`) e desnormaliza só `line_count` + nome da
    plataforma para queries de listagem. Execuções vivem na tabela
    `mooring_system_executions` (F5.4.2).
    """

    __tablename__ = "mooring_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_radius: Mapped[float] = mapped_column(Float, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # JSON serializado de MooringSystemInput.
    config_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    executions: Mapped[list["MooringSystemExecutionRecord"]] = relationship(
        "MooringSystemExecutionRecord",
        back_populates="mooring_system",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MooringSystemExecutionRecord.executed_at.desc()",
    )

    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_msys_name_nonempty"),
        CheckConstraint("platform_radius > 0", name="ck_msys_platform_radius_positive"),
        CheckConstraint("line_count >= 1", name="ck_msys_line_count_positive"),
        Index("idx_msys_name", "name"),
        Index("idx_msys_updated", "updated_at"),
    )


class MooringSystemExecutionRecord(Base):
    """
    Histórico de execuções do solver multi-linha (F5.4.2).

    Mesma política de retenção de `executions`: apenas as 10 mais
    recentes por sistema são mantidas. Truncagem ocorre no service após
    cada solve bem-sucedido.
    """

    __tablename__ = "mooring_system_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mooring_system_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mooring_systems.id", ondelete="CASCADE"),
        nullable=False,
    )

    # MooringSystemResult completo serializado em JSON.
    result_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Desnormalizações para listagem e badge na UI.
    aggregate_force_magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    aggregate_force_azimuth_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    worst_alert_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    n_converged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_invalid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    mooring_system: Mapped[MooringSystemRecord] = relationship(
        "MooringSystemRecord", back_populates="executions"
    )

    __table_args__ = (
        Index("idx_msys_exec_msys", "mooring_system_id", "executed_at"),
    )


class BuoyRecord(Base):
    """
    Catálogo de boias (F6).

    Espelha o padrão de `LineTypeRecord`: legacy_id rastreável, data_source
    documentado por entrada, base_unit_system reflete unidade DE ORIGEM
    (armazenamento sempre em SI: m, N, kg). `submerged_force` é a magnitude
    em N do empuxo líquido (positivo) — pode ser pré-computada na seed
    pela função `backend.api.services.buoyancy.compute_submerged_force`
    a partir de dimensões + peso, OU informada manualmente quando a fonte
    cita o valor diretamente.

    Convenção de imutabilidade idêntica a `line_types`: entradas com
    `data_source` que comece com prefixo de seed canônico (`excel_buoy_calc_v1`,
    `generic_offshore`, ou `manufacturer_*`) são imutáveis; apenas
    `user_input` aceita PUT/DELETE.
    """

    __tablename__ = "buoys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    buoy_type: Mapped[str] = mapped_column(String(40), nullable=False)
    end_type: Mapped[str] = mapped_column(String(40), nullable=False)
    base_unit_system: Mapped[str] = mapped_column(Text, nullable=False)
    outer_diameter: Mapped[float] = mapped_column(Float, nullable=False)
    length: Mapped[float] = mapped_column(Float, nullable=False)
    weight_in_air: Mapped[float] = mapped_column(Float, nullable=False)
    submerged_force: Mapped[float] = mapped_column(Float, nullable=False)
    data_source: Mapped[str] = mapped_column(Text, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(Text, nullable=True)
    serial_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_buoys_name_nonempty"),
        CheckConstraint("outer_diameter > 0", name="ck_buoys_diameter_positive"),
        CheckConstraint("length > 0", name="ck_buoys_length_positive"),
        CheckConstraint("weight_in_air >= 0", name="ck_buoys_weight_nonneg"),
        Index("idx_buoys_name", "name"),
        Index("idx_buoys_type", "buoy_type"),
    )


__all__ = [
    "AppConfigRecord",
    "BuoyRecord",
    "CaseRecord",
    "ExecutionRecord",
    "LineTypeRecord",
    "MooringSystemExecutionRecord",
    "MooringSystemRecord",
]
