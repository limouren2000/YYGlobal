from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str
    llm_mode: str
    version: str


class ExperienceInput(BaseModel):
    id: Optional[str] = None
    kind: str
    title: str
    organization: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    confirmed: bool = True


class ExperienceResponse(ExperienceInput):
    id: str


class ProfileUpdate(BaseModel):
    full_name: str = ""
    current_school: str = ""
    current_major: str = ""
    degree: str = ""
    gpa: Optional[float] = None
    gpa_scale: Optional[float] = None
    language_scores: Dict[str, Any] = Field(default_factory=dict)
    target_countries: List[str] = Field(default_factory=list)
    target_fields: List[str] = Field(default_factory=list)
    intake: str = ""
    budget: Optional[float] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    experiences: List[ExperienceInput] = Field(default_factory=list)


class ProfileResponse(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    updated_at: datetime
    experiences: List[ExperienceResponse] = Field(default_factory=list)


class DocumentResponse(ORMModel):
    id: str
    filename: str
    mime_type: str
    kind: str
    parse_status: str
    extracted_data: Dict[str, Any]
    created_at: datetime


class DocumentConfirmRequest(BaseModel):
    accepted_fields: List[str] = Field(default_factory=list)


class RequirementResponse(ORMModel):
    deadline_raw: str = ""
    deadline: Optional[str] = None
    deadlines: List[Dict[str, Any]] = Field(default_factory=list)
    min_gpa: Optional[float] = None
    language: Dict[str, Any] = Field(default_factory=dict)
    prerequisites: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    fees: Dict[str, Any] = Field(default_factory=dict)
    source_ids: List[str] = Field(default_factory=list)
    verified: bool = False


class SourceResponse(ORMModel):
    id: str
    url: str
    title: str
    source_type: str
    fetched_at: datetime
    status: str


class EvidenceResponse(ORMModel):
    id: str
    source_id: str
    field: str
    quote: str
    locator: str
    confidence: float


class ProgramResponse(ORMModel):
    id: str
    university: str
    name: str
    degree: str
    country: str
    city: str
    field: str
    duration_months: Optional[int]
    tuition: Optional[float]
    currency: str
    official_url: str
    summary: str
    requirement: Optional[RequirementResponse] = None
    sources: List[SourceResponse] = Field(default_factory=list)
    evidence: List[EvidenceResponse] = Field(default_factory=list)


class ProgramVerifyResponse(BaseModel):
    program_id: str
    source_id: str
    status: str
    fetched_at: datetime
    content_hash: str
    extracted: Dict[str, Any]


class BatchVerifyResponse(BaseModel):
    matched_count: int
    attempted_count: int
    verified_count: int
    needs_review_count: int
    failed_count: int
    results: List[Dict[str, Any]] = Field(default_factory=list)


class ProgramRecommendationResponse(BaseModel):
    program: ProgramResponse
    score: float
    reasons: List[str] = Field(default_factory=list)


class ShortlistCreate(BaseModel):
    name: str = "我的 P0 选校方案"
    program_ids: List[str]


class ShortlistItemsUpdate(BaseModel):
    program_ids: List[str]


class ShortlistItemResponse(BaseModel):
    id: str
    program: ProgramResponse
    tier: str
    score: float
    rationale: str
    risks: List[str]


class ShortlistResponse(BaseModel):
    id: str
    name: str
    rationale: str
    items: List[ShortlistItemResponse]
    created_at: datetime


class MaterialPlanCreate(BaseModel):
    program_id: str


class MaterialPlanResponse(ORMModel):
    id: str
    program_id: str
    checklist: List[Dict[str, Any]]
    cv_plan: Dict[str, Any]
    ps_plan: Dict[str, Any]
    gaps: List[str]
    created_at: datetime


class MaterialArtifactCreate(BaseModel):
    document_id: str
    program_id: Optional[str] = None
    kind: str
    scope: str = "general"
    version_name: str = Field(min_length=1, max_length=200)
    language: str = "English"
    status: str = "draft"
    notes: str = ""


class MaterialArtifactUpdate(BaseModel):
    program_id: Optional[str] = None
    scope: Optional[str] = None
    version_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    language: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class MaterialArtifactResponse(BaseModel):
    id: str
    document_id: str
    program_id: Optional[str]
    kind: str
    scope: str
    version_name: str
    language: str
    status: str
    notes: str
    filename: str
    parse_status: str
    created_at: datetime
    updated_at: datetime


class MaterialPreflightRequest(BaseModel):
    artifact_id: str
    program_id: str


class MaterialPreflightResponse(BaseModel):
    ready_to_upload: bool
    artifact_id: str
    program_id: str
    checks: List[Dict[str, Any]]
    warnings: List[str]


class MaterialDraftGenerate(BaseModel):
    kind: str
    program_id: Optional[str] = None
    slot_key: str = ""
    language: str = "English"
    prompt: str = Field(default="", max_length=10000)


class MaterialDraftUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    content: Optional[str] = Field(default=None, min_length=1)
    status: Optional[str] = None


class MaterialDraftResponse(ORMModel):
    id: str
    program_id: Optional[str]
    slot_key: str
    parent_id: Optional[str]
    derived_from_id: Optional[str]
    root_id: Optional[str]
    version_number: int
    revision_type: str
    change_summary: str
    kind: str
    title: str
    language: str
    prompt: str
    content: str
    source_experience_ids: List[str]
    warnings: List[str]
    model_info: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class PackageMaterialUpdate(BaseModel):
    material_key: str
    status: str
    selected_asset_type: str = ""
    selected_asset_id: str = ""
    note: str = ""


class ApplicationPackageResponse(BaseModel):
    id: str
    program: ProgramResponse
    shortlist_id: Optional[str]
    official_verified: bool
    checklist: List[Dict[str, Any]]
    gaps: List[str]
    ready: bool
    plan_confirmed: bool = False
    status: str
    created_at: datetime
    updated_at: datetime


class MaterialAssetPreviewResponse(BaseModel):
    title: str
    kind: str
    mime_type: str
    content: str
    raw_url: str = ""


class ApplicationCreate(BaseModel):
    program_id: str
    status: str = "planning"
    round_name: str = ""
    notes: str = ""


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    round_name: Optional[str] = None
    notes: Optional[str] = None


class ApplicationResponse(ORMModel):
    id: str
    program_id: str
    status: str
    round_name: str
    notes: str
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str
    program_id: Optional[str] = None
    category: str = "application"
    status: str = "todo"
    due_date: Optional[str] = None
    priority: str = "medium"
    details: str = ""


class TimelineCreate(BaseModel):
    program_id: str


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    details: Optional[str] = None


class TaskResponse(ORMModel):
    id: str
    program_id: Optional[str]
    title: str
    category: str
    status: str
    due_date: Optional[str]
    priority: str
    details: str
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: Optional[str] = None


class WritingConversationCreate(BaseModel):
    program_id: str
    slot_key: str = Field(min_length=1, max_length=120)
    material_kind: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=240)
    resource_ids: List[str] = Field(default_factory=list)


class WritingConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    resource_ids: Optional[List[str]] = None


class AssistantConversationCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=240)
    resource_ids: List[str] = Field(default_factory=list)


class AssistantConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    pinned: Optional[bool] = None
    resource_ids: Optional[List[str]] = None


class WritingMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=10000)


class WritingMessageResponse(ORMModel):
    id: str
    role: str
    content: str
    sources: List[Dict[str, Any]]
    created_at: datetime


class WritingConversationResponse(ORMModel):
    id: str
    title: str
    program_id: str
    slot_key: str
    material_kind: str
    resource_ids: List[str]
    messages: List[WritingMessageResponse] = Field(default_factory=list)
    latest_draft: Optional[MaterialDraftResponse] = None
    created_at: datetime
    updated_at: datetime


class AssistantConversationResponse(BaseModel):
    id: str
    title: str
    scene: str
    program_id: Optional[str] = None
    program_label: str = ""
    slot_key: str = ""
    material_kind: str = ""
    pinned: bool = False
    resource_ids: List[str] = Field(default_factory=list)
    messages: List[WritingMessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MemoryResponse(ORMModel):
    id: str
    memory_type: str
    key: str
    value: Dict[str, Any]
    source_type: str
    source_id: Optional[str]
    confidence: float
    active: bool
    updated_at: datetime


class SkillResponse(BaseModel):
    name: str
    version: str
    description: str
    tools: List[str]
    output_schema: Dict[str, Any]
    enabled: bool


class MCPServerResponse(BaseModel):
    name: str
    transport: str
    endpoint: str
    read_only: bool
    status: str
    tools: List[str]


class AgentRunResponse(ORMModel):
    id: str
    skill_name: str
    skill_version: str
    goal: str
    status: str
    plan: List[Dict[str, Any]]
    final_output: str
    structured_output: Dict[str, Any]
    stop_reason: str
    token_usage: Dict[str, Any]
    duration_ms: int
    created_at: datetime


class TraceResponse(BaseModel):
    run: AgentRunResponse
    steps: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
