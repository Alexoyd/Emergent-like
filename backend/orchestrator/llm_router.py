import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import openai
import anthropic
import httpx
import json
import time
import collections
import re
import tempfile
from datetime import datetime
from .prompt_cache import PromptCacheManager

logger = logging.getLogger(__name__)

class ModelTier(Enum):
    LOCAL = "local"
    MEDIUM = "medium" 
    PREMIUM = "premium"

@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_eur: float

class LLMRouter:
    def __init__(self):
        self.max_requests_per_minute = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "20"))
        self.request_timestamps = collections.deque()
        self.openai_client = None
        self.anthropic_client = None
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        self.max_local_retries = int(os.getenv("MAX_LOCAL_RETRIES", "3"))
        self.max_escalation_retries = int(os.getenv("MAX_ESCALATION_RETRIES", "2"))
        self.force_escalation = False
        self.current_attempt = 0
        self.local_failures = 0
        
        # ✅ Check if Anthropic is enabled
        self.anthropic_enabled = os.getenv("ENABLE_ANTHROPIC", "true").lower() == "true"
        
         # Initialize prompt cache manager
        self.prompt_cache = PromptCacheManager()
        
        # Conversation history for context (per run)
        self.conversation_histories: Dict[str, List[Dict[str, str]]] = {}
        
        # Initialize clients if keys are available
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # ✅ Only initialize Anthropic if enabled AND key is available
        if self.anthropic_enabled and os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif not self.anthropic_enabled:
            logger.info("Anthropic integration disabled via ENABLE_ANTHROPIC=false")
        elif not os.getenv("ANTHROPIC_API_KEY"):
            logger.warning("Anthropic API key not provided, Anthropic integration disabled")
        
        # Cost mapping (EUR per 1K tokens)
        self.cost_mapping = {
            "local": {"input": 0.0, "output": 0.0},
            "gpt-5": {"input": 0.005, "output": 0.015},  # Estimated pricing
            "claude-3-5-sonnet": {"input": 0.003, "output": 0.015}
        }
    
    async def _wait_if_rate_limited(self):
        now = time.time()
        # Nettoyer les timestamps vieux de plus de 60s
        while self.request_timestamps and now - self.request_timestamps[0] > 60:
            self.request_timestamps.popleft()

        if len(self.request_timestamps) >= self.max_requests_per_minute:
            sleep_time = 60 - (now - self.request_timestamps[0])
            logger.warning(f"Rate limit atteint ({self.max_requests_per_minute}/min). "
                        f"Pause de {sleep_time:.2f} secondes...")
            await asyncio.sleep(sleep_time)
            # Après la pause, nettoyer à nouveau
            await self._wait_if_rate_limited()

        # Enregistrer l’horodatage de la requête actuelle
        self.request_timestamps.append(time.time())

    async def generate(self, prompt: str, task_type: str, current_cost: float, budget_limit: float, run_id: str = None) -> LLMResponse:
        """Generate response with improved automatic model selection and escalation"""
        try:
            # Reset attempt counter for new generation
            self.current_attempt = 0
            
            # Determine initial model tier
            tier = self._determine_tier(task_type, current_cost, budget_limit, len(prompt))
            
            # Try local model first with configured retries
            if tier == ModelTier.LOCAL and not self.force_escalation:
                local_response = await self._try_local_with_retries(prompt, task_type, run_id)
                if local_response:
                    return local_response
                    
                # Local failed, escalate
                logger.warning(f"Local model failed after {self.max_local_retries} attempts, escalating...")
                self.local_failures += 1
            
            # Try escalation path
            for attempt_tier in self._get_escalation_path(tier):
                if attempt_tier == ModelTier.LOCAL and self.local_failures >= self.max_local_retries:
                    continue  # Skip local if already failed
                    
                try:
                    self.current_attempt += 1
                    response = await self._generate_with_tier(prompt, attempt_tier, task_type, run_id)
                    
                    if self._is_valid_response(response.content, task_type):
                        # Reset failure count on success
                        if attempt_tier == ModelTier.LOCAL:
                            self.local_failures = 0
                        return response
                    else:
                        logger.warning(f"Invalid response from {attempt_tier}, escalating...")
                        
                        # ✅ RETRY UNE FOIS pour task_type="coding" seulement
                        if task_type == "coding":
                            retry_response = await self._retry_for_valid_diff(attempt_tier, task_type, run_id)
                            if retry_response:
                                return retry_response
                                
                        continue
                        
                except Exception as e:
                    logger.error(f"Error with {attempt_tier} (attempt {self.current_attempt}): {e}")
                    if self.current_attempt >= self.max_escalation_retries:
                        break
                    continue
            
            # Fallback to basic response if all fail
            return LLMResponse(
                content="Error: Unable to generate response with any available model after escalation",
                model="error",
                prompt_tokens=0,
                completion_tokens=0,
                cost_eur=0.0
            )
            
        except Exception as e:
            logger.error(f"Error in LLM routing: {e}")
            return LLMResponse(
                content=f"Error: {str(e)}",
                model="error", 
                prompt_tokens=0,
                completion_tokens=0,
                cost_eur=0.0
            )
    
    async def _try_local_with_retries(self, prompt: str, task_type: str, run_id: str = None) -> Optional[LLMResponse]:
        """Try local model with configured retries"""
        for attempt in range(1, self.max_local_retries + 1):
            try:
                logger.info(f"Local attempt {attempt}/{self.max_local_retries} for {task_type}")
                response = await self._generate_ollama(prompt, task_type)
                
                if self._is_valid_response(response.content, task_type):
                    logger.info(f"Local model succeeded on attempt {attempt}")
                    return response
                else:
                    logger.warning(f"Local model invalid response on attempt {attempt}")
                    
            except Exception as e:
                logger.error(f"Local model error on attempt {attempt}: {e}")
                
            # Wait between retries (exponential backoff)
            if attempt < self.max_local_retries:
                await asyncio.sleep(2 ** attempt)
        
        return None
    
    def _determine_tier(self, task_type: str, current_cost: float, budget_limit: float, prompt_length: int) -> ModelTier:
        """Determine appropriate model tier based on task and constraints"""
        remaining_budget = budget_limit - current_cost
        
        # Force escalation if requested
        if self.force_escalation:
            return ModelTier.PREMIUM
        
        # Use premium for complex tasks or when local failed
        if task_type == "debugging" or prompt_length > 8000:
            return ModelTier.PREMIUM if remaining_budget > 0.5 else ModelTier.LOCAL
        
        # Use medium for coding tasks
        if task_type == "coding" and remaining_budget > 0.1:
            return ModelTier.MEDIUM
        
        # Default to local
        return ModelTier.LOCAL
    
    def _get_escalation_path(self, initial_tier: ModelTier) -> list:
        """Get escalation path for model selection, excluding disabled providers"""
        available_tiers = []
        
        # Always include LOCAL if available
        available_tiers.append(ModelTier.LOCAL)
        
        # Include MEDIUM (OpenAI) if client is available  
        if self.openai_client:
            available_tiers.append(ModelTier.MEDIUM)
            
        # ✅ Only include PREMIUM (Anthropic) if enabled and client available
        if self.anthropic_enabled and self.anthropic_client:
            available_tiers.append(ModelTier.PREMIUM)
        
        # Build escalation path based on initial tier preference
        if initial_tier == ModelTier.LOCAL:
            path = [ModelTier.LOCAL, ModelTier.MEDIUM, ModelTier.PREMIUM]
        elif initial_tier == ModelTier.MEDIUM:
            path = [ModelTier.MEDIUM, ModelTier.PREMIUM, ModelTier.LOCAL]
        else:
            path = [ModelTier.PREMIUM, ModelTier.MEDIUM, ModelTier.LOCAL]
                    
        # Filter path to only include available tiers
        return [tier for tier in path if tier in available_tiers]
    
    async def _generate_with_tier(self, prompt: str, tier: ModelTier, task_type: str = "coding", run_id: str = None) -> LLMResponse:
        """Generate response with specific model tier"""
        if tier == ModelTier.LOCAL:
            return await self._generate_ollama(prompt, task_type)
        elif tier == ModelTier.MEDIUM:
            return await self._generate_openai(prompt, task_type, run_id)
        else:  # PREMIUM
            if not self.anthropic_enabled:
                raise Exception("Anthropic is disabled via ENABLE_ANTHROPIC=false")
            if not self.anthropic_client:
                raise Exception("Anthropic client not available (API key missing or disabled)")
            return await self._generate_anthropic(prompt, task_type, run_id)
    
    async def _generate_ollama(self, prompt: str, task_type: str = "coding") -> LLMResponse:
        """Generate using local Ollama model"""
        try:
            # ✅ FORCER LE CONTRAT STRICT pour task_type="coding"  
            final_prompt = prompt
            if task_type == "coding":
                from .prompt_cache import STRICT_PATCH_SUFFIX
                final_prompt = f"{prompt.rstrip()}\
\
{STRICT_PATCH_SUFFIX.strip()}"
                
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": final_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                            "num_predict": 2048
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return LLMResponse(
                        content=data.get("response", ""),
                        model=self.ollama_model,
                        prompt_tokens=data.get("prompt_eval_count", 0),
                        completion_tokens=data.get("eval_count", 0),
                        cost_eur=0.0  # Local model is free
                    )
                else:
                    raise Exception(f"Ollama API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise
    
    async def _generate_openai(self, prompt: str, task_type: str = "coding", run_id: str = None) -> LLMResponse:
        """Generate using OpenAI GPT model with prompt caching"""
        if not self.openai_client:
            raise Exception("OpenAI API key not configured")
        
        try:
             # ✅ Throttle avant de lancer la requête
            await self._wait_if_rate_limited()

            # Get conversation history for this run
            conversation_history = self.conversation_histories.get(run_id, [])
            
            # ✅ FORCER LE CONTRAT STRICT pour task_type="coding"
            final_user_prompt = prompt
            if task_type == "coding":
                from .prompt_cache import STRICT_PATCH_SUFFIX
                final_user_prompt = f"{prompt.rstrip()}\
\
{STRICT_PATCH_SUFFIX.strip()}"
            
            # Prepare messages with caching optimization
            messages, cache_used = await self.prompt_cache.prepare_openai_messages(
                task_type, final_user_prompt, conversation_history
            )
            
            # Use GPT-4o with native caching if available
            model = "gpt-4o"  # Supports better caching
            extra_params = {}
            
            # Try to use OpenAI's native caching if supported
            if cache_used and len(conversation_history) > 0:
                # Use message caching for longer conversations
                extra_params["stream"] = False
                #extra_params["max_completion_tokens"] = 2048
                
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
                **extra_params
            )
            
            usage = response.usage
            
            # Calculate cost with caching savings
            base_cost = self._calculate_cost("gpt-4o", usage.prompt_tokens, usage.completion_tokens)
            cache_savings_pct = 0.3 if cache_used else 0.0  # 30% savings with cache
            final_cost = base_cost * (1 - cache_savings_pct)
            
            # Update conversation history (avec le prompt original, pas le STRICT_PATCH_SUFFIX)
            if run_id:
                if run_id not in self.conversation_histories:
                    self.conversation_histories[run_id] = []
                
                self.conversation_histories[run_id].extend([
                    {"role": "user", "content": prompt},  # Original prompt, pas final_user_prompt
                    {"role": "assistant", "content": response.choices[0].message.content}
                ])
                
                # Limit history size to prevent context overflow
                if len(self.conversation_histories[run_id]) > 10:
                    self.conversation_histories[run_id] = self.conversation_histories[run_id][-8:]
            
            logger.info(f"OpenAI request: {usage.prompt_tokens} prompt + {usage.completion_tokens} completion tokens, cache_used: {cache_used}, cost: €{final_cost:.4f}")
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_eur=final_cost
            )
            
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise
    
    async def _generate_anthropic(self, prompt: str, task_type: str = "coding", run_id: str = None) -> LLMResponse:
        """Generate using Anthropic Claude model with prompt caching"""
        if not self.anthropic_client:
            raise Exception("Anthropic API key not configured")
        
        try:
            # ✅ Throttle avant d’envoyer la requête
            await self._wait_if_rate_limited()

            # Get conversation history for this run
            conversation_history = self.conversation_histories.get(run_id, [])
            
            # ✅ FORCER LE CONTRAT STRICT pour task_type="coding"
            final_user_prompt = prompt
            if task_type == "coding":
                from .prompt_cache import STRICT_PATCH_SUFFIX
                final_user_prompt = f"{prompt.rstrip()}\
\
{STRICT_PATCH_SUFFIX.strip()}"
            
            # Prepare messages with caching optimization
            system_prompt, messages, cache_used = await self.prompt_cache.prepare_anthropic_messages(
                task_type, final_user_prompt, conversation_history
            )
            
            # Use Claude 3.5 Sonnet with prompt caching
            model = "claude-3-5-sonnet-20241022"
            extra_params = {}
            
            # Try to use Anthropic's native prompt caching if supported
            if cache_used and len(conversation_history) > 0:
                # Add cache control for system prompt (Anthropic beta feature)
                extra_params["extra_headers"] = {
                    "anthropic-beta": "prompt-caching-2024-07-31"
                }
                
                # Mark system prompt for caching
                system_prompt = {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            
            response = await asyncio.to_thread(
                self.anthropic_client.messages.create,
                model=model,
                max_tokens=2048,
                temperature=0.1,
                system=system_prompt,
                messages=messages,
                **extra_params
            )
            
            # Extract token usage from response
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            
            # Calculate cost with caching savings
            base_cost = self._calculate_cost("claude-3-5-sonnet", prompt_tokens, completion_tokens)
            
            # Anthropic's prompt caching offers 75% savings on cached portions
            cache_savings_pct = 0.5 if cache_used else 0.0  # Conservative 50% savings estimate
            final_cost = base_cost * (1 - cache_savings_pct)
            
            # Update conversation history (avec le prompt original, pas le STRICT_PATCH_SUFFIX)
            if run_id:
                if run_id not in self.conversation_histories:
                    self.conversation_histories[run_id] = []
                
                self.conversation_histories[run_id].extend([
                    {"role": "user", "content": prompt},  # Original prompt, pas final_user_prompt
                    {"role": "assistant", "content": response.content[0].text}
                ])
                
                # Limit history size to prevent context overflow
                if len(self.conversation_histories[run_id]) > 10:
                    self.conversation_histories[run_id] = self.conversation_histories[run_id][-8:]
            
            logger.info(f"Anthropic request: {prompt_tokens} prompt + {completion_tokens} completion tokens, cache_used: {cache_used}, cost: €{final_cost:.4f}")
            
            return LLMResponse(
                content=response.content[0].text,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_eur=final_cost
            )
            
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            raise
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in EUR for API usage"""
        # Simplified cost calculation - adjust based on actual pricing
        if "gpt" in model:
            return (prompt_tokens * 0.000005 + completion_tokens * 0.000015) * 0.85  # Convert USD to EUR
        elif "claude" in model:
            return (prompt_tokens * 0.000003 + completion_tokens * 0.000015) * 0.85  # Convert USD to EUR
        else:
            return 0.0

    
    def _is_valid_response(self, content: str, task_type: str) -> bool:
        """Validate response based on task type."""
        if not content or len(content.strip()) < 10:
            return False

        if task_type == "coding":
            # ✅ VALIDATION STRICTE : seuls les unified diffs valides sont acceptés
            stripped = content.lstrip()
            
            # 1) Doit commencer par diff --git
            if not stripped.startswith("diff --git"):
                logger.warning(f"Invalid coding response: doesn't start with 'diff --git', starts with: '{stripped[:50]}...'")
                self._save_invalid_response(content, "missing_diff_git_header")
                return False
            
            # 2) Vérification basique de structure unified diff
            lines = content.split('\\')
            
            has_file_headers = False
            has_hunk_header = False
            
            for line in lines:
                if line.startswith('--- ') or line.startswith('+++ '):
                    has_file_headers = True
                elif line.startswith('@@') and '@@' in line[2:]:
                    has_hunk_header = True
                    
            if not has_file_headers:
                logger.warning("Invalid coding response: missing file headers (--- or +++)")
                self._save_invalid_response(content, "missing_file_headers")
                return False
                
            if not has_hunk_header:
                logger.warning("Invalid coding response: missing hunk headers (@@)")
                self._save_invalid_response(content, "missing_hunk_headers") 
                return False
                
            return True

        elif task_type == "planning":
            # Accepter les plans qui mentionnent des étapes ou des listes numérotées
            lower = content.lower()
            if any(k in lower for k in ["step", "plan", "1.", "2.", "- "]):
                return True
            return False

        # Pour les autres types, on valide par défaut si non vide
        return True
 
    def _save_invalid_response(self, content: str, reason: str) -> None:
        """Save invalid response to debug file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_path = f"/tmp/emergent_patches/invalid_{timestamp}_{reason}.txt"
            
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(f"=== Invalid Response Debug ===")
                f.write(f"Reason: {reason}")
                f.write(f"Timestamp: {datetime.now().isoformat()}")
                f.write(f"Length: {len(content)} characters")
                f.write("=== Content ===")
                f.write(content)
                
            logger.info(f"Saved invalid response to {debug_path}")
        except Exception as e:
            logger.error(f"Failed to save invalid response: {e}")

    async def _retry_for_valid_diff(self, tier: ModelTier, task_type: str, run_id: str = None) -> Optional[LLMResponse]:
        """Retry with strict message for invalid coding responses"""
        retry_prompt = """Invalid output. Re-emit ONLY a valid unified diff suitable for 'git apply'. Start with 'diff --git …'. No prose/HTML/Markdown fences."""
        
        try:
            logger.info(f"Retrying {tier} for valid unified diff...")
            response = await self._generate_with_tier(retry_prompt, tier, task_type, run_id)
            
            if self._is_valid_response(response.content, task_type):
                logger.info(f"Retry successful with {tier}")
                return response
            else:
                logger.warning(f"Retry failed with {tier}: still invalid response")
                # Sauvegarder le retry échoué aussi
                self._save_invalid_response(response.content, f"retry_failed_{tier.value}")
                return None
                
        except Exception as e:
            logger.error(f"Error during retry with {tier}: {e}")
            return None
    
    async def check_ollama_availability(self) -> bool:
        """Check if Ollama is available and has the required model"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Check if Ollama is running
                response = await client.get(f"{self.ollama_base_url}/api/tags")
                if response.status_code != 200:
                    return False
                
                # Check if required model is available
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]
                
                return any(self.ollama_model in name for name in model_names)
                
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
