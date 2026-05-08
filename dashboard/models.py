from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Room(BaseModel):
    room_id: str
    task_ref: str
    status: str
    retries: int
    message_count: int
    last_activity: Optional[str] = None
    task_description: Optional[str] = None
    goal_total: int = 0
    goal_done: int = 0


class Message(BaseModel):
    id: str
    ts: str
    from_: str
    to: str
    type: str
    ref: str
    body: str


class RunRequest(BaseModel):
    plan: str
    plan_id: str


class ReactionRequest(BaseModel):
    entity_id: str
    user_id: str
    reaction_type: str


class CommentRequest(BaseModel):
    entity_id: str
    user_id: str
    body: str
    parent_id: Optional[str] = None


class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str


class CreatePlanRequest(BaseModel):
    path: str
    title: str = "Untitled"
    content: Optional[str] = None
    working_dir: Optional[str] = None


class SavePlanRequest(BaseModel):
    content: str
    # "manual_save", "ai_refine", "expansion"
    change_source: str = "manual_save"


class RefineRequest(BaseModel):
    message: str
    plan_content: str = ""
    plan_id: str = ""
    model: str = ""
    chat_history: list = Field(default_factory=list)
    working_dir: str = ""  # Target project directory for this plan
    asset_context: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)  # [{url: "data:image/...;base64,...", name, contentType}]


class UpdatePlanRoleConfigRequest(BaseModel):
    default_model: str | None = None
    temperature: float | None = None
    timeout_seconds: int | None = None
    cli: str | None = None
    skill_refs: List[str] | None = None
    disabled_skills: List[str] | None = None


class StrategyParameter(BaseModel):
    name: str
    label: str
    value: float | int | str | bool
    type: str  # "int", "float", "bool", "string"


class Strategy(BaseModel):
    id: str
    name: str
    description: str
    status: str  # "active", "inactive"
    parameters: List[StrategyParameter]
    last_run: Optional[str] = None


class Skill(BaseModel):
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    trust_level: str = "experimental"
    source: str = "project"
    version: str = "0.1.0"
    category: Optional[str] = None
    score: Optional[float] = None
    applicable_roles: List[str] = Field(default_factory=list)
    content: str = ""
    path: Optional[str] = None
    relative_path: Optional[str] = None
    params: List[Dict[str, Any]] = Field(default_factory=list)
    changelog: List[Dict[str, Any]] = Field(default_factory=list)
    author: Optional[str] = None
    updated_at: Optional[str] = None
    forked_from: Optional[str] = None
    is_draft: bool = False
    enabled: bool = True
    active_epics_count: int = 0


class Role(BaseModel):
    id: str
    name: str
    description: str = ""
    instructions: str = ""
    provider: str  # 'Claude', 'GPT', 'Gemini', 'Custom'
    version: str
    temperature: float = 0.7
    budget_tokens_max: int = 500000
    max_retries: int = 3
    timeout_seconds: int = 300
    skill_refs: List[str] = Field(default_factory=list)
    mcp_refs: List[str] = Field(default_factory=list)
    system_prompt_override: Optional[str] = None
    instance_type: str = "worker" # 'worker' | 'evaluator'
    created_at: str
    updated_at: str


class CreateRoleRequest(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9 \-_]+$"
    )
    description: str = Field("", max_length=500)
    instructions: str = ""
    provider: str
    version: str
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    budget_tokens_max: int = Field(500000, ge=1000, le=10000000)
    max_retries: int = Field(3, ge=1, le=10)
    timeout_seconds: int = Field(300, ge=60)
    skill_refs: List[str] = Field(default_factory=list)
    mcp_refs: List[str] = Field(default_factory=list)
    instance_type: str = "worker"
    system_prompt_override: Optional[str] = Field(None, max_length=2000)


class SkillSearchResponse(BaseModel):
    skills: List[Skill]
    total: int


class SkillInstallRequest(BaseModel):
    path: str


class SkillSearchRequest(BaseModel):
    query: str
    role: Optional[str] = None
    tags: List[str] = []


class SkillSyncResponse(BaseModel):
    synced_count: int
    added: List[str]
    updated: List[str]
    removed: List[str]


class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=60)
    description: str = Field(..., min_length=10, max_length=500)
    category: str
    applicable_roles: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    content: str = Field(..., min_length=50)
    is_draft: bool = False


class SkillUpdateRequest(BaseModel):
    description: Optional[str] = Field(None, min_length=10, max_length=500)
    category: Optional[str] = None
    applicable_roles: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    content: Optional[str] = None
    is_draft: Optional[bool] = None
    enabled: Optional[bool] = None
    major_bump: bool = False
    change_description: Optional[str] = None


class SkillForkRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=60)


class SkillValidateRequest(BaseModel):
    content: str


class SkillValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    markers: List[Dict[str, Any]] = Field(default_factory=list)


class SkillDuplicateCheckRequest(BaseModel):
    name: str


class SkillDuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    similar_skills: List[str] = Field(default_factory=list)


class ProviderSettings(BaseModel):
    api_key_ref: Optional[str] = None
    base_url: Optional[str] = None
    org_id: Optional[str] = None
    enabled: bool = True
    default_model: Optional[str] = None
    deployment_mode: Optional[str] = None   # 'gemini' | 'vertex' (Google only)
    project_id: Optional[str] = None        # Vertex AI project ID (Google only)
    vertex_location: Optional[str] = None   # Vertex AI region (Google only, default: global)
    vertex_auth_mode: Optional[str] = None  # 'service_account' | 'oauth' (Vertex only, default: service_account)
    enabled_models: List[str] = Field(
        default_factory=list,
        description=(
            "List of allowed model IDs. "
            "If empty, all models from this provider are allowed."
        ),
    )
    dismissed: Optional[bool] = False


class ProvidersNamespace(BaseModel):
    openai: Optional[ProviderSettings] = None
    anthropic: Optional[ProviderSettings] = None
    google: Optional[ProviderSettings] = None
    byteplus: Optional[ProviderSettings] = None
    openai_compatible: Optional[ProviderSettings] = None
    ollama: Optional[ProviderSettings] = None
    custom: Dict[str, ProviderSettings] = Field(default_factory=dict)


class RoleSettings(BaseModel):
    default_model: Optional[str] = None
    temperature: Optional[float] = None
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    budget_tokens_max: Optional[int] = None
    system_prompt_override: Optional[str] = None
    skill_refs: List[str] = Field(default_factory=list)
    disabled_skills: List[str] = Field(default_factory=list)
    instance_type: Optional[str] = None


class RuntimeSettings(BaseModel):
    poll_interval: int = Field(default=5, ge=1, le=300)
    max_concurrent_rooms: int = Field(default=10, ge=1, le=10000)
    auto_approve_tools: bool = False
    dynamic_pipelines: bool = True
    # Master agent default model — format: "provider/model_id" or plain "model_id".
    # Empty string means "use the hardcoded default from master_agent.py".
    master_agent_model: str = ""


class MemorySettings(BaseModel):
    # -- Processing LLM --
    llm_backend: str = "ollama"           # gemini | openai | ollama | openrouter | sglang | openai-compatible
    llm_model: str = "llama3.2"           # model name (provider-specific)
    # -- Embedding --
    embedding_backend: str = "ollama"     # gemini | ollama | openai-compatible
    embedding_model: str = "leoipulsar/harrier-0.6b"
    # -- Vector store --
    vector_backend: str = "zvec"              # zvec | chroma
    # -- Behaviour --
    context_aware: bool = True                # include similar memories in LLM analysis
    auto_sync: bool = True                    # periodic disk sync
    auto_sync_interval: int = 60              # seconds between syncs
    ttl_days: int = 30                        # auto-delete entries older than N days
    # Legacy alias — readers should prefer vector_backend
    vector_store: str = "zvec"


class ChannelPlatformSettings(BaseModel):
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)


class ChannelsNamespace(BaseModel):
    telegram: Optional[ChannelPlatformSettings] = None
    slack: Optional[ChannelPlatformSettings] = None
    discord: Optional[ChannelPlatformSettings] = None
    custom: Dict[str, ChannelPlatformSettings] = Field(default_factory=dict)


class AutonomySettings(BaseModel):
    idle_explore_enabled: bool = False
    interval: int = 3600


class ObservabilitySettings(BaseModel):
    log_level: str = "INFO"
    broadcast_verbosity: str = "normal"
    otel_enabled: bool = False


class KnowledgeSettings(BaseModel):
    """Knowledge service runtime settings (ADR-15).

    Overrides the env-var defaults baked into ``dashboard/knowledge/config.py``.
    Resolution precedence is ``MasterSettings.knowledge`` > env var >
    hardcoded default — see :class:`KnowledgeService.__init__`.

    All fields are prefixed with ``knowledge_`` to explicitly declare the
    settings namespace and avoid field-name collisions across namespaces.

    Empty strings mean "no override; use the env-var / hardcoded default".
    ``knowledge_embedding_dimension`` is informational and read-only on the
    frontend (the actual dim is determined by the embedding model that gets
    loaded).
    """

    # -- LLM --
    knowledge_llm_backend: str = ""             # empty = use config.LLM_PROVIDER
    knowledge_llm_model: str = ""               # empty = use config.LLM_MODEL
    # -- Embedding --
    knowledge_embedding_backend: str = ""       # empty = use config.EMBEDDING_PROVIDER
    knowledge_embedding_model: str = ""         # empty = use config.EMBEDDING_MODEL
    knowledge_embedding_dimension: int = 768    # read-only / informational — always 768


class MasterSettings(BaseModel):
    providers: ProvidersNamespace = Field(default_factory=ProvidersNamespace)
    roles: Dict[str, RoleSettings] = Field(default_factory=dict)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    channels: ChannelsNamespace = Field(default_factory=ChannelsNamespace)
    autonomy: AutonomySettings = Field(default_factory=AutonomySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    knowledge: KnowledgeSettings = Field(default_factory=KnowledgeSettings)


class EffectiveResolution(BaseModel):
    effective: Dict[str, Any]
    provenance: Dict[str, str]
