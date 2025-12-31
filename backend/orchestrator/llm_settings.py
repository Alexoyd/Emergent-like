"""
LLM Settings Management - Multi-Provider Architecture

Settings hiérarchiques: global defaults → project defaults → run override
Support providers: Ollama, OpenAI, Anthropic, Google Gemini

Architecture provider-agnostic avec modèles normalisés.
"""

import os
import logging
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ProviderType(str, Enum):
    """Supported LLM providers"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class AgentRole(str, Enum):
    """Agent roles for model assignment"""
    PLANNER = "planner"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    DEFAULT = "default"  # Fallback for any role


class ModelCapability(str, Enum):
    """Model capabilities for filtering"""
    CODING = "coding"
    PLANNING = "planning"
    REVIEW = "review"
    CHAT = "chat"
    JSON_OUTPUT = "json_output"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    LONG_CONTEXT = "long_context"


# =============================================================================
# MODELS - Normalized Provider & Model Definitions
# =============================================================================

class LLMModel(BaseModel):
    """Normalized LLM model definition"""
    id: str = Field(..., description="Unique model identifier (e.g., 'gpt-4o')")
    provider: ProviderType = Field(..., description="Provider type")
    model_id: str = Field(..., description="Provider-specific model ID")
    label: str = Field(..., description="Human-readable label")
    capabilities: List[ModelCapability] = Field(default_factory=list, description="Model capabilities")
    enabled: bool = Field(True, description="Whether model is enabled")
    max_tokens: int = Field(4096, description="Max output tokens")
    context_window: int = Field(8192, description="Context window size")
    input_cost_per_1k: float = Field(0.0, description="Cost per 1K input tokens (EUR)")
    output_cost_per_1k: float = Field(0.0, description="Cost per 1K output tokens (EUR)")
    description: Optional[str] = Field(None, description="Model description")
    
    class Config:
        use_enum_values = True


class LLMProvider(BaseModel):
    """Provider configuration with available models"""
    id: ProviderType = Field(..., description="Provider identifier")
    name: str = Field(..., description="Human-readable name")
    enabled: bool = Field(True, description="Whether provider is enabled globally")
    api_key_configured: bool = Field(False, description="Whether API key is configured")
    base_url: Optional[str] = Field(None, description="Custom base URL (for Ollama)")
    models: List[LLMModel] = Field(default_factory=list, description="Available models")
    status: Literal["connected", "disconnected", "error", "unconfigured"] = Field("unconfigured")
    last_check: Optional[datetime] = Field(None, description="Last health check timestamp")
    error_message: Optional[str] = Field(None, description="Last error message if any")
    
    class Config:
        use_enum_values = True


class RoleModelAssignment(BaseModel):
    """Model assignment for a specific agent role"""
    role: AgentRole = Field(..., description="Agent role")
    provider: ProviderType = Field(..., description="Selected provider")
    model_id: str = Field(..., description="Selected model ID")
    fallback_provider: Optional[ProviderType] = Field(None, description="Fallback provider if primary fails")
    fallback_model_id: Optional[str] = Field(None, description="Fallback model ID")
    
    class Config:
        use_enum_values = True


# =============================================================================
# SETTINGS - Hierarchical Configuration
# =============================================================================

class LLMSettingsBase(BaseModel):
    """Base LLM settings (shared between global/project/run)"""
    
    # Role-based model assignments
    role_assignments: Dict[str, RoleModelAssignment] = Field(
        default_factory=dict,
        description="Model assignments per role (planner/developer/reviewer)"
    )
    
    # Default fallback behavior
    enable_fallback: bool = Field(True, description="Enable automatic fallback to next provider")
    fallback_order: List[ProviderType] = Field(
        default_factory=lambda: [ProviderType.OLLAMA, ProviderType.OPENAI, ProviderType.ANTHROPIC, ProviderType.GOOGLE],
        description="Provider fallback order"
    )
    
    # Budget and limits
    max_retries_per_provider: int = Field(3, ge=1, le=10, description="Max retries before fallback")
    request_timeout_seconds: int = Field(120, ge=30, le=600, description="Request timeout")
    
    # Tracking
    track_usage: bool = Field(True, description="Track token usage and costs")
    track_latency: bool = Field(True, description="Track response latency")
    
    class Config:
        use_enum_values = True


class GlobalLLMSettings(LLMSettingsBase):
    """Global LLM settings (system-wide defaults)"""
    id: str = Field(default="global", description="Settings ID")
    
    # Provider configurations (global level)
    providers: Dict[str, LLMProvider] = Field(
        default_factory=dict,
        description="Provider configurations"
    )
    
    # API keys source preference
    api_keys_source: Literal["env", "db", "both"] = Field(
        "both",
        description="Where to look for API keys: env (.env), db (MongoDB), both (db priority)"
    )
    
    # Global overrides
    force_provider: Optional[ProviderType] = Field(None, description="Force specific provider for all requests")
    force_model: Optional[str] = Field(None, description="Force specific model for all requests")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        use_enum_values = True


class ProjectLLMSettings(LLMSettingsBase):
    """Project-level LLM settings (overrides global)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = Field(..., description="Associated project ID")
    
    # Project-specific API keys (optional, overrides global)
    custom_api_keys: Dict[str, str] = Field(
        default_factory=dict,
        description="Project-specific API keys (encrypted in DB)"
    )
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        use_enum_values = True


class RunLLMSettings(LLMSettingsBase):
    """Run-level LLM settings (overrides project and global)"""
    run_id: str = Field(..., description="Associated run ID")
    
    # Run-specific overrides (highest priority)
    override_provider: Optional[ProviderType] = Field(None, description="Override provider for this run")
    override_model: Optional[str] = Field(None, description="Override model for this run")
    
    class Config:
        use_enum_values = True


# =============================================================================
# TRACKING - Usage & Performance Metrics
# =============================================================================

class LLMUsageRecord(BaseModel):
    """Record of a single LLM request"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Request details
    provider: ProviderType
    model_id: str
    role: AgentRole
    
    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Cost (EUR)
    cost_eur: float = 0.0
    
    # Performance
    latency_ms: int = 0
    success: bool = True
    error_message: Optional[str] = None
    
    # Fallback tracking
    was_fallback: bool = False
    original_provider: Optional[ProviderType] = None
    fallback_reason: Optional[str] = None
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        use_enum_values = True


class LLMUsageStats(BaseModel):
    """Aggregated usage statistics"""
    period: Literal["hour", "day", "week", "month", "all"]
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    fallback_requests: int = 0
    
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    
    total_cost_eur: float = 0.0
    
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    
    by_provider: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_model: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_role: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


# =============================================================================
# DEFAULT CONFIGURATIONS
# =============================================================================

def get_default_models() -> Dict[str, List[LLMModel]]:
    """Return default model configurations for all providers"""
    return {
        "ollama": [
            LLMModel(
                id="ollama-qwen2.5-coder",
                provider=ProviderType.OLLAMA,
                model_id="qwen2.5-coder:7b",
                label="Qwen 2.5 Coder 7B",
                capabilities=[ModelCapability.CODING, ModelCapability.CHAT],
                enabled=True,
                max_tokens=4096,
                context_window=32768,
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                description="Local model, free, good for coding tasks"
            ),
            LLMModel(
                id="ollama-codellama",
                provider=ProviderType.OLLAMA,
                model_id="codellama:13b",
                label="Code Llama 13B",
                capabilities=[ModelCapability.CODING],
                enabled=True,
                max_tokens=4096,
                context_window=16384,
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                description="Meta's code-specialized model"
            ),
            LLMModel(
                id="ollama-deepseek-coder",
                provider=ProviderType.OLLAMA,
                model_id="deepseek-coder:6.7b",
                label="DeepSeek Coder 6.7B",
                capabilities=[ModelCapability.CODING, ModelCapability.JSON_OUTPUT],
                enabled=True,
                max_tokens=4096,
                context_window=16384,
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                description="DeepSeek's coding model"
            ),
        ],
        "openai": [
            LLMModel(
                id="openai-gpt-4o",
                provider=ProviderType.OPENAI,
                model_id="gpt-4o",
                label="GPT-4o",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.REVIEW, 
                             ModelCapability.JSON_OUTPUT, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION],
                enabled=True,
                max_tokens=4096,
                context_window=128000,
                input_cost_per_1k=0.005,
                output_cost_per_1k=0.015,
                description="OpenAI's flagship multimodal model"
            ),
            LLMModel(
                id="openai-gpt-4o-mini",
                provider=ProviderType.OPENAI,
                model_id="gpt-4o-mini",
                label="GPT-4o Mini",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.CHAT,
                             ModelCapability.JSON_OUTPUT, ModelCapability.FUNCTION_CALLING],
                enabled=True,
                max_tokens=4096,
                context_window=128000,
                input_cost_per_1k=0.00015,
                output_cost_per_1k=0.0006,
                description="Fast and affordable, good for most tasks"
            ),
            LLMModel(
                id="openai-gpt-4-turbo",
                provider=ProviderType.OPENAI,
                model_id="gpt-4-turbo",
                label="GPT-4 Turbo",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.REVIEW,
                             ModelCapability.JSON_OUTPUT, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION],
                enabled=True,
                max_tokens=4096,
                context_window=128000,
                input_cost_per_1k=0.01,
                output_cost_per_1k=0.03,
                description="Previous flagship, still powerful"
            ),
        ],
        "anthropic": [
            LLMModel(
                id="anthropic-claude-sonnet-4",
                provider=ProviderType.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                label="Claude Sonnet 4",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.REVIEW,
                             ModelCapability.LONG_CONTEXT, ModelCapability.VISION],
                enabled=True,
                max_tokens=8192,
                context_window=200000,
                input_cost_per_1k=0.003,
                output_cost_per_1k=0.015,
                description="Anthropic's latest balanced model"
            ),
            LLMModel(
                id="anthropic-claude-3.5-sonnet",
                provider=ProviderType.ANTHROPIC,
                model_id="claude-3-5-sonnet-20241022",
                label="Claude 3.5 Sonnet",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.REVIEW,
                             ModelCapability.LONG_CONTEXT, ModelCapability.VISION],
                enabled=True,
                max_tokens=8192,
                context_window=200000,
                input_cost_per_1k=0.003,
                output_cost_per_1k=0.015,
                description="Excellent for coding and analysis"
            ),
            LLMModel(
                id="anthropic-claude-3-opus",
                provider=ProviderType.ANTHROPIC,
                model_id="claude-3-opus-20240229",
                label="Claude 3 Opus",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.REVIEW,
                             ModelCapability.LONG_CONTEXT],
                enabled=True,
                max_tokens=4096,
                context_window=200000,
                input_cost_per_1k=0.015,
                output_cost_per_1k=0.075,
                description="Most capable Claude model"
            ),
        ],
        "google": [
            LLMModel(
                id="google-gemini-1.5-pro",
                provider=ProviderType.GOOGLE,
                model_id="gemini-1.5-pro",
                label="Gemini 1.5 Pro",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.REVIEW,
                             ModelCapability.LONG_CONTEXT, ModelCapability.VISION],
                enabled=False,  # Disabled by default
                max_tokens=8192,
                context_window=1000000,
                input_cost_per_1k=0.00125,
                output_cost_per_1k=0.005,
                description="Google's flagship model with huge context"
            ),
            LLMModel(
                id="google-gemini-1.5-flash",
                provider=ProviderType.GOOGLE,
                model_id="gemini-1.5-flash",
                label="Gemini 1.5 Flash",
                capabilities=[ModelCapability.CODING, ModelCapability.CHAT, ModelCapability.LONG_CONTEXT],
                enabled=False,  # Disabled by default
                max_tokens=8192,
                context_window=1000000,
                input_cost_per_1k=0.000075,
                output_cost_per_1k=0.0003,
                description="Fast and cheap, good for quick tasks"
            ),
            LLMModel(
                id="google-gemini-2.0-flash",
                provider=ProviderType.GOOGLE,
                model_id="gemini-2.0-flash-exp",
                label="Gemini 2.0 Flash (Experimental)",
                capabilities=[ModelCapability.CODING, ModelCapability.PLANNING, ModelCapability.JSON_OUTPUT],
                enabled=False,  # Disabled by default
                max_tokens=8192,
                context_window=1000000,
                input_cost_per_1k=0.0001,
                output_cost_per_1k=0.0004,
                description="Latest experimental model"
            ),
        ],
    }


def get_default_providers() -> Dict[str, LLMProvider]:
    """Return default provider configurations"""
    default_models = get_default_models()
    
    return {
        "ollama": LLMProvider(
            id=ProviderType.OLLAMA,
            name="Ollama (Local)",
            enabled=True,
            api_key_configured=True,  # No API key needed
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            models=default_models["ollama"],
            status="unconfigured"
        ),
        "openai": LLMProvider(
            id=ProviderType.OPENAI,
            name="OpenAI",
            enabled=True,
            api_key_configured=bool(os.getenv("OPENAI_API_KEY")),
            models=default_models["openai"],
            status="unconfigured" if not os.getenv("OPENAI_API_KEY") else "disconnected"
        ),
        "anthropic": LLMProvider(
            id=ProviderType.ANTHROPIC,
            name="Anthropic",
            enabled=os.getenv("ENABLE_ANTHROPIC", "true").lower() == "true",
            api_key_configured=bool(os.getenv("ANTHROPIC_API_KEY")),
            models=default_models["anthropic"],
            status="unconfigured" if not os.getenv("ANTHROPIC_API_KEY") else "disconnected"
        ),
        "google": LLMProvider(
            id=ProviderType.GOOGLE,
            name="Google (Gemini)",
            enabled=False,  # Disabled by default
            api_key_configured=bool(os.getenv("GOOGLE_API_KEY")),
            models=default_models["google"],
            status="unconfigured"
        ),
    }


def get_default_role_assignments() -> Dict[str, RoleModelAssignment]:
    """Return default role-to-model assignments"""
    return {
        "planner": RoleModelAssignment(
            role=AgentRole.PLANNER,
            provider=ProviderType.OPENAI,
            model_id="gpt-4o-mini",
            fallback_provider=ProviderType.OLLAMA,
            fallback_model_id="qwen2.5-coder:7b"
        ),
        "developer": RoleModelAssignment(
            role=AgentRole.DEVELOPER,
            provider=ProviderType.OPENAI,
            model_id="gpt-4o-mini",
            fallback_provider=ProviderType.ANTHROPIC,
            fallback_model_id="claude-3-5-sonnet-20241022"
        ),
        "reviewer": RoleModelAssignment(
            role=AgentRole.REVIEWER,
            provider=ProviderType.OPENAI,
            model_id="gpt-4o",
            fallback_provider=ProviderType.ANTHROPIC,
            fallback_model_id="claude-sonnet-4-20250514"
        ),
        "default": RoleModelAssignment(
            role=AgentRole.DEFAULT,
            provider=ProviderType.OLLAMA,
            model_id="qwen2.5-coder:7b",
            fallback_provider=ProviderType.OPENAI,
            fallback_model_id="gpt-4o-mini"
        ),
    }


def get_default_global_settings() -> GlobalLLMSettings:
    """Return default global LLM settings"""
    return GlobalLLMSettings(
        id="global",
        providers=get_default_providers(),
        role_assignments=get_default_role_assignments(),
        enable_fallback=True,
        fallback_order=[ProviderType.OLLAMA, ProviderType.OPENAI, ProviderType.ANTHROPIC, ProviderType.GOOGLE],
        max_retries_per_provider=3,
        request_timeout_seconds=120,
        track_usage=True,
        track_latency=True,
        api_keys_source="both"
    )


# =============================================================================
# SETTINGS MANAGER - Hierarchical Resolution
# =============================================================================

class LLMSettingsManager:
    """
    Manages LLM settings with hierarchical resolution:
    run settings > project settings > global settings > env defaults
    """
    
    def __init__(self, db):
        self.db = db
        self._global_cache: Optional[GlobalLLMSettings] = None
        self._project_cache: Dict[str, ProjectLLMSettings] = {}
        
    async def get_global_settings(self, use_cache: bool = True) -> GlobalLLMSettings:
        """Get global settings from DB or defaults"""
        if use_cache and self._global_cache:
            return self._global_cache
            
        settings_data = await self.db.llm_settings.find_one({"id": "global"})
        
        if settings_data:
            # Convert to model, handling potential missing fields
            try:
                settings = GlobalLLMSettings(**settings_data)
            except Exception as e:
                logger.warning(f"Error parsing global settings, using defaults: {e}")
                settings = get_default_global_settings()
        else:
            # No settings in DB, use defaults
            settings = get_default_global_settings()
            
        # Update status based on current env
        settings = self._update_provider_status(settings)
        
        self._global_cache = settings
        return settings
    
    async def save_global_settings(self, settings: GlobalLLMSettings) -> GlobalLLMSettings:
        """Save global settings to DB"""
        settings.updated_at = datetime.now(timezone.utc)
        
        await self.db.llm_settings.update_one(
            {"id": "global"},
            {"$set": settings.dict()},
            upsert=True
        )
        
        self._global_cache = settings
        return settings
    
    async def get_project_settings(self, project_id: str) -> Optional[ProjectLLMSettings]:
        """Get project-specific settings"""
        if project_id in self._project_cache:
            return self._project_cache[project_id]
            
        settings_data = await self.db.llm_settings.find_one({
            "project_id": project_id,
            "id": {"$ne": "global"}
        })
        
        if settings_data:
            try:
                settings = ProjectLLMSettings(**settings_data)
                self._project_cache[project_id] = settings
                return settings
            except Exception as e:
                logger.warning(f"Error parsing project settings: {e}")
                
        return None
    
    async def save_project_settings(self, settings: ProjectLLMSettings) -> ProjectLLMSettings:
        """Save project-specific settings"""
        settings.updated_at = datetime.now(timezone.utc)
        
        await self.db.llm_settings.update_one(
            {"project_id": settings.project_id, "id": {"$ne": "global"}},
            {"$set": settings.dict()},
            upsert=True
        )
        
        self._project_cache[settings.project_id] = settings
        return settings
    
    async def get_effective_settings(
        self,
        project_id: Optional[str] = None,
        run_settings: Optional[RunLLMSettings] = None
    ) -> Dict[str, Any]:
        """
        Get effective settings with hierarchical resolution:
        run > project > global > env defaults
        """
        # Start with global settings
        global_settings = await self.get_global_settings()
        effective = global_settings.dict()
        
        # Apply project overrides if available
        if project_id:
            project_settings = await self.get_project_settings(project_id)
            if project_settings:
                effective = self._merge_settings(effective, project_settings.dict())
        
        # Apply run overrides if available
        if run_settings:
            effective = self._merge_settings(effective, run_settings.dict())
            
            # Handle explicit run-level overrides
            if run_settings.override_provider:
                effective["force_provider"] = run_settings.override_provider
            if run_settings.override_model:
                effective["force_model"] = run_settings.override_model
        
        return effective
    
    async def get_model_for_role(
        self,
        role: AgentRole,
        project_id: Optional[str] = None,
        run_settings: Optional[RunLLMSettings] = None
    ) -> tuple[ProviderType, str]:
        """Get the configured provider and model for a specific role"""
        effective = await self.get_effective_settings(project_id, run_settings)
        
        # Check for forced provider/model
        if effective.get("force_provider") and effective.get("force_model"):
            return (effective["force_provider"], effective["force_model"])
        
        # Get role assignment
        role_key = role.value if isinstance(role, AgentRole) else role
        assignments = effective.get("role_assignments", {})
        
        if role_key in assignments:
            assignment = assignments[role_key]
            if isinstance(assignment, dict):
                return (assignment["provider"], assignment["model_id"])
            else:
                return (assignment.provider, assignment.model_id)
        
        # Fallback to default role
        if "default" in assignments:
            assignment = assignments["default"]
            if isinstance(assignment, dict):
                return (assignment["provider"], assignment["model_id"])
            else:
                return (assignment.provider, assignment.model_id)
        
        # Ultimate fallback
        return (ProviderType.OLLAMA, "qwen2.5-coder:7b")
    
    def _merge_settings(self, base: Dict, override: Dict) -> Dict:
        """Deep merge settings dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_settings(result[key], value)
            elif value is not None:  # Only override if value is not None
                result[key] = value
                
        return result
    
    def _update_provider_status(self, settings: GlobalLLMSettings) -> GlobalLLMSettings:
        """Update provider status based on current environment"""
        for provider_id, provider in settings.providers.items():
            if provider_id == "ollama":
                provider.base_url = os.getenv("OLLAMA_BASE_URL", provider.base_url)
                provider.api_key_configured = True
            elif provider_id == "openai":
                provider.api_key_configured = bool(os.getenv("OPENAI_API_KEY"))
                provider.status = "disconnected" if provider.api_key_configured else "unconfigured"
            elif provider_id == "anthropic":
                provider.api_key_configured = bool(os.getenv("ANTHROPIC_API_KEY"))
                provider.enabled = os.getenv("ENABLE_ANTHROPIC", "true").lower() == "true"
                provider.status = "disconnected" if provider.api_key_configured else "unconfigured"
            elif provider_id == "google":
                provider.api_key_configured = bool(os.getenv("GOOGLE_API_KEY"))
                provider.status = "disconnected" if provider.api_key_configured else "unconfigured"
                
        return settings
    
    async def record_usage(self, usage: LLMUsageRecord) -> None:
        """Record LLM usage for tracking"""
        await self.db.llm_usage.insert_one(usage.dict())
    
    async def get_usage_stats(
        self,
        period: str = "day",
        project_id: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> LLMUsageStats:
        """Get aggregated usage statistics"""
        # Build query based on filters
        query = {}
        if project_id:
            query["project_id"] = project_id
        if run_id:
            query["run_id"] = run_id
            
        # Add time filter based on period
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        
        if period == "hour":
            query["timestamp"] = {"$gte": now - timedelta(hours=1)}
        elif period == "day":
            query["timestamp"] = {"$gte": now - timedelta(days=1)}
        elif period == "week":
            query["timestamp"] = {"$gte": now - timedelta(weeks=1)}
        elif period == "month":
            query["timestamp"] = {"$gte": now - timedelta(days=30)}
        
        # Aggregate stats
        cursor = self.db.llm_usage.find(query)
        records = await cursor.to_list(length=10000)
        
        stats = LLMUsageStats(period=period)
        
        latencies = []
        by_provider = {}
        by_model = {}
        by_role = {}
        
        for record in records:
            stats.total_requests += 1
            if record.get("success"):
                stats.successful_requests += 1
            else:
                stats.failed_requests += 1
            if record.get("was_fallback"):
                stats.fallback_requests += 1
                
            stats.total_tokens += record.get("total_tokens", 0)
            stats.total_prompt_tokens += record.get("prompt_tokens", 0)
            stats.total_completion_tokens += record.get("completion_tokens", 0)
            stats.total_cost_eur += record.get("cost_eur", 0)
            
            if record.get("latency_ms"):
                latencies.append(record["latency_ms"])
                
            # Group by provider
            provider = record.get("provider", "unknown")
            if provider not in by_provider:
                by_provider[provider] = {"requests": 0, "tokens": 0, "cost": 0}
            by_provider[provider]["requests"] += 1
            by_provider[provider]["tokens"] += record.get("total_tokens", 0)
            by_provider[provider]["cost"] += record.get("cost_eur", 0)
            
            # Group by model
            model = record.get("model_id", "unknown")
            if model not in by_model:
                by_model[model] = {"requests": 0, "tokens": 0, "cost": 0}
            by_model[model]["requests"] += 1
            by_model[model]["tokens"] += record.get("total_tokens", 0)
            by_model[model]["cost"] += record.get("cost_eur", 0)
            
            # Group by role
            role = record.get("role", "unknown")
            if role not in by_role:
                by_role[role] = {"requests": 0, "tokens": 0, "cost": 0}
            by_role[role]["requests"] += 1
            by_role[role]["tokens"] += record.get("total_tokens", 0)
            by_role[role]["cost"] += record.get("cost_eur", 0)
        
        if latencies:
            stats.avg_latency_ms = sum(latencies) / len(latencies)
            latencies.sort()
            p95_idx = int(len(latencies) * 0.95)
            stats.p95_latency_ms = latencies[p95_idx] if p95_idx < len(latencies) else latencies[-1]
        
        stats.by_provider = by_provider
        stats.by_model = by_model
        stats.by_role = by_role
        
        return stats
    
    def invalidate_cache(self, project_id: Optional[str] = None):
        """Invalidate settings cache"""
        if project_id:
            self._project_cache.pop(project_id, None)
        else:
            self._global_cache = None
            self._project_cache.clear()
