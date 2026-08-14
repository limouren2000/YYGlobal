from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class OwnedMixin:
    owner_id: Mapped[str] = mapped_column(String(64), default="local-admin", index=True)


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default="local-admin")
    name: Mapped[str] = mapped_column(String(120), default="P0 单用户测试空间")


class ApplicantProfile(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "applicant_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    current_school: Mapped[str] = mapped_column(String(200), default="")
    current_major: Mapped[str] = mapped_column(String(200), default="")
    degree: Mapped[str] = mapped_column(String(80), default="")
    gpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gpa_scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    language_scores: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    target_countries: Mapped[list] = mapped_column(JSON, default=list)
    target_fields: Mapped[list] = mapped_column(JSON, default=list)
    intake: Mapped[str] = mapped_column(String(80), default="")
    budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Experience(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "experiences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("applicant_profiles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str] = mapped_column(String(200), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")
    end_date: Mapped[str] = mapped_column(String(20), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(50), default="other")
    path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    parse_status: Mapped[str] = mapped_column(String(40), default="pending")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extracted_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class Program(Base, TimestampMixin):
    __tablename__ = "programs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    university: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    degree: Mapped[str] = mapped_column(String(80), default="Master")
    country: Mapped[str] = mapped_column(String(100), index=True)
    city: Mapped[str] = mapped_column(String(100), default="")
    field: Mapped[str] = mapped_column(String(160), index=True)
    duration_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tuition: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    official_url: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProgramSource(Base, TimestampMixin):
    __tablename__ = "program_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(300), default="")
    source_type: Mapped[str] = mapped_column(String(40), default="official")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="verified")


class EvidenceChunk(Base, TimestampMixin):
    __tablename__ = "evidence_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("program_sources.id"), index=True)
    field: Mapped[str] = mapped_column(String(80), index=True)
    quote: Mapped[str] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(String(200), default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


class ProgramRequirement(Base, TimestampMixin):
    __tablename__ = "program_requirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), unique=True, index=True)
    deadline_raw: Mapped[str] = mapped_column(String(200), default="")
    deadline: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    deadlines: Mapped[list] = mapped_column(JSON, default=list)
    min_gpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    language: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)
    materials: Mapped[list] = mapped_column(JSON, default=list)
    fees: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Shortlist(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "shortlists"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), default="我的 P0 选校方案")
    rationale: Mapped[str] = mapped_column(Text, default="")


class ShortlistItem(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "shortlist_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    shortlist_id: Mapped[str] = mapped_column(ForeignKey("shortlists.id"), index=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    tier: Mapped[str] = mapped_column(String(30), default="target")
    score: Mapped[float] = mapped_column(Float, default=0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    risks: Mapped[list] = mapped_column(JSON, default=list)


class MaterialPlan(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "material_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    cv_plan: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    ps_plan: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    gaps: Mapped[list] = mapped_column(JSON, default=list)


class MaterialArtifact(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "material_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    program_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("programs.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), index=True)
    scope: Mapped[str] = mapped_column(String(30), default="general", index=True)
    version_name: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(40), default="English")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class MaterialDraft(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "material_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("programs.id"), nullable=True, index=True
    )
    slot_key: Mapped[str] = mapped_column(String(120), default="", index=True)
    parent_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("material_drafts.id"), nullable=True, index=True
    )
    derived_from_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("material_drafts.id"), nullable=True, index=True
    )
    root_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    revision_type: Mapped[str] = mapped_column(String(30), default="generated")
    change_summary: Mapped[str] = mapped_column(Text, default="首次生成")
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(240))
    language: Mapped[str] = mapped_column(String(40), default="English")
    prompt: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text)
    source_experience_ids: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    model_info: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)


class ApplicationPackage(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "application_packages"
    __table_args__ = (
        UniqueConstraint("owner_id", "program_id", name="uq_application_package_owner_program"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    shortlist_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("shortlists.id"), nullable=True, index=True
    )
    official_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    ready: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    plan_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="needs_official_verification")


class Application(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="planning", index=True)
    round_name: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class Task(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    program_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("programs.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(60), default="application")
    status: Mapped[str] = mapped_column(String(30), default="todo")
    due_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    details: Mapped[str] = mapped_column(Text, default="")


class Conversation(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(240), default="新对话")
    program_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("programs.id"), nullable=True, index=True
    )
    slot_key: Mapped[str] = mapped_column(String(120), default="", index=True)
    material_kind: Mapped[str] = mapped_column(String(40), default="", index=True)
    resource_ids: Mapped[list] = mapped_column(JSON, default=list)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Message(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)


class AgentRun(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    skill_name: Mapped[str] = mapped_column(String(100), default="")
    skill_version: Mapped[str] = mapped_column(String(30), default="")
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="running")
    plan: Mapped[list] = mapped_column(JSON, default=list)
    context_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    final_output: Mapped[str] = mapped_column(Text, default="")
    structured_output: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    stop_reason: Mapped[str] = mapped_column(String(80), default="")
    token_usage: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class AgentStep(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "agent_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    expected_output: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class ToolCall(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "tool_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    step_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(120))
    arguments: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="started")
    error: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class Memory(Base, TimestampMixin, OwnedMixin):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_type: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    source_type: Mapped[str] = mapped_column(String(60), default="user_confirmed")
    source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SkillVersion(Base, TimestampMixin):
    __tablename__ = "skill_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    eval_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class MCPConnection(Base, TimestampMixin):
    __tablename__ = "mcp_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), index=True)
    transport: Mapped[str] = mapped_column(String(40), default="demo")
    endpoint: Mapped[str] = mapped_column(String(500), default="in-process")
    read_only: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="available")
    tools: Mapped[list] = mapped_column(JSON, default=list)
