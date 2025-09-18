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
        self.openai_client = None
        self.anthropic_client = None
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        self.max_local_retries = int(os.getenv("MAX_LOCAL_RETRIES", "3"))
        self.max_escalation_retries = int(os.getenv("MAX_ESCALATION_RETRIES", "2"))
        self.force_escalation = False
        self.current_attempt = 0
        self.local_failures = 0
        
        # Initialize prompt cache manager
        self.prompt_cache = PromptCacheManager()
        
        # Conversation history for context (per run)
        self.conversation_histories: Dict[str, List[Dict[str, str]]] = {}
        
        # Initialize clients if keys are available
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Cost mapping (EUR per 1K tokens)
        self.cost_mapping = {
            "local": {"input": 0.0, "output": 0.0},
            "gpt-5": {"input": 0.005, "output": 0.015},  # Estimated pricing
            "claude-3-5-sonnet": {"input": 0.003, "output": 0.015}
        }
    
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
                    response = await self._generate_with_tier(prompt, attempt_tier)
                    
                    if self._is_valid_response(response.content, task_type):
                        # Reset failure count on success
                        if attempt_tier == ModelTier.LOCAL:
                            self.local_failures = 0
                        return response
                    else:
                        logger.warning(f"Invalid response from {attempt_tier}, escalating...")
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
                response = await self._generate_ollama(prompt)
                
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
        """Get escalation path for model selection"""
        if initial_tier == ModelTier.LOCAL:
            return [ModelTier.LOCAL, ModelTier.MEDIUM, ModelTier.PREMIUM]
        elif initial_tier == ModelTier.MEDIUM:
            return [ModelTier.MEDIUM, ModelTier.PREMIUM, ModelTier.LOCAL]
        else:
            return [ModelTier.PREMIUM, ModelTier.MEDIUM, ModelTier.LOCAL]
    
    async def _generate_with_tier(self, prompt: str, tier: ModelTier) -> LLMResponse:
        """Generate response with specific model tier"""
        if tier == ModelTier.LOCAL:
            return await self._generate_ollama(prompt)
        elif tier == ModelTier.MEDIUM:
            return await self._generate_openai(prompt)
        else:  # PREMIUM
            return await self._generate_anthropic(prompt)
    
    async def _generate_ollama(self, prompt: str) -> LLMResponse:
        """Generate using local Ollama model"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
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
            # Get conversation history for this run
            conversation_history = self.conversation_histories.get(run_id, [])
            
            # Prepare messages with caching optimization
            messages, cache_used = await self.prompt_cache.prepare_openai_messages(
                task_type, prompt, conversation_history
            )
            
            # Use GPT-4o with native caching if available
            model = "gpt-4o"  # Supports better caching
            extra_params = {}
            
            # Try to use OpenAI's native caching if supported
            if cache_used and len(conversation_history) > 0:
                # Use message caching for longer conversations
                extra_params["stream"] = False
                extra_params["max_completion_tokens"] = 2048
            
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
            
            # Update conversation history
            if run_id:
                if run_id not in self.conversation_histories:
                    self.conversation_histories[run_id] = []
                
                self.conversation_histories[run_id].extend([
                    {"role": "user", "content": prompt},
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
    
    async def _generate_anthropic(self, prompt: str) -> LLMResponse:
        """Generate using Anthropic Claude model"""
        if not self.anthropic_client:
            raise Exception("Anthropic API key not configured")
        
        try:
            response = await asyncio.to_thread(
                self.anthropic_client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract token usage from response
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            cost = self._calculate_cost("claude-3-5-sonnet", prompt_tokens, completion_tokens)
            
            return LLMResponse(
                content=response.content[0].text,
                model="claude-3-5-sonnet-20241022",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_eur=cost
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
        """Validate response based on task type"""
        if not content or len(content.strip()) < 10:
            return False
        
        if task_type == "coding":
            # Check for patch format
            return "BEGIN_PATCH" in content and "END_PATCH" in content
        elif task_type == "planning":
            # Check for structured plan
            return any(marker in content.lower() for marker in ["step", "1.", "2.", "plan"])
        
        return True
    
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