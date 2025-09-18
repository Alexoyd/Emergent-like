import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class CachedPrompt:
    hash_key: str
    system_prompt: str
    created_at: datetime
    last_used: datetime
    usage_count: int
    provider: str  # 'openai' or 'anthropic'
    
@dataclass 
class PromptDelta:
    conversation_history: List[Dict[str, str]]
    current_user_message: str

class PromptCacheManager:
    def __init__(self):
        self.cache: Dict[str, CachedPrompt] = {}
        self.max_cache_size = 100  # Maximum cached prompts
        self.cache_ttl_hours = 24  # Cache time-to-live in hours
        
        # Standard system prompts with their hashes
        self.system_prompts = {
            "coding": """You are an expert AI coding agent. Generate precise, minimal code changes.
Your task is to create focused patches that solve specific problems without introducing unnecessary complexity.

Guidelines:
- Generate unified diff patches in the format: BEGIN_PATCH...END_PATCH
- Focus on minimal, testable changes
- Include appropriate error handling
- Follow best practices for the given technology stack
- Add comments for complex logic
- Ensure backward compatibility where possible

Response format:
BEGIN_PATCH
<unified diff or file content changes>
END_PATCH

CHECKLIST
- Tests: OK/KO with brief explanation
- Linting: OK/KO 
- Security: OK/KO
- Performance: OK/KO
- Comments: <brief summary of changes and reasoning>""",

            "planning": """You are an AI project planning agent. Create detailed, actionable execution plans.
Your task is to break down complex goals into specific, measurable steps.

Guidelines:
- Create numbered, sequential steps
- Each step should be independently testable
- Include specific files to modify or create
- Define clear success criteria
- Estimate complexity and dependencies
- Consider potential risks and mitigation strategies

Format as numbered list with brief descriptions and specific deliverables.""",

            "debugging": """You are an expert debugging agent. Analyze errors and provide systematic solutions.
Your task is to identify root causes and implement comprehensive fixes.

Guidelines:
- Analyze stack traces and error messages thoroughly
- Consider multiple potential causes
- Provide step-by-step diagnostic approach
- Include logging and monitoring improvements
- Test fixes against edge cases
- Document the resolution process

Focus on robust solutions that prevent similar issues in the future.""",

            "analysis": """You are an expert code analysis agent. Provide comprehensive insights into codebases.
Your task is to understand structure, patterns, and provide actionable recommendations.

Guidelines:
- Analyze architecture and design patterns
- Identify technical debt and improvement opportunities
- Assess security and performance implications
- Provide specific, actionable recommendations
- Consider maintainability and scalability
- Highlight best practices and anti-patterns

Deliver structured analysis with clear priorities and implementation suggestions."""
        }
        
        # Pre-compute hashes for system prompts
        self.system_prompt_hashes = {
            task_type: self._compute_hash(prompt) 
            for task_type, prompt in self.system_prompts.items()
        }
        
    def _compute_hash(self, text: str) -> str:
        """Compute SHA256 hash of text"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _cleanup_cache(self):
        """Remove expired cache entries"""
        now = datetime.now(timezone.utc)
        expired_keys = []
        
        for key, cached_prompt in self.cache.items():
            if now - cached_prompt.created_at > timedelta(hours=self.cache_ttl_hours):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
            
        # If cache is still too large, remove least recently used
        if len(self.cache) > self.max_cache_size:
            sorted_cache = sorted(
                self.cache.items(),
                key=lambda x: x[1].last_used
            )
            
            # Remove oldest 20% of entries
            to_remove = len(sorted_cache) - int(self.max_cache_size * 0.8)
            for i in range(to_remove):
                del self.cache[sorted_cache[i][0]]
                
        logger.info(f"Cache cleanup: {len(expired_keys)} expired, {len(self.cache)} remaining")
    
    async def prepare_openai_messages(self, task_type: str, user_prompt: str, 
                                    conversation_history: List[Dict[str, str]] = None) -> Tuple[List[Dict[str, str]], bool]:
        """Prepare OpenAI messages with caching optimization"""
        try:
            system_prompt = self.system_prompts.get(task_type, self.system_prompts["coding"])
            system_hash = self.system_prompt_hashes.get(task_type, self._compute_hash(system_prompt))
            
            # Check if we can use cached system prompt
            cached_prompt = self.cache.get(system_hash)
            use_cache = False
            
            if cached_prompt:
                # Update usage stats
                cached_prompt.last_used = datetime.now(timezone.utc)
                cached_prompt.usage_count += 1
                use_cache = True
                logger.info(f"Using cached system prompt for {task_type} (used {cached_prompt.usage_count} times)")
            else:
                # Create new cache entry
                self.cache[system_hash] = CachedPrompt(
                    hash_key=system_hash,
                    system_prompt=system_prompt,
                    created_at=datetime.now(timezone.utc),
                    last_used=datetime.now(timezone.utc),
                    usage_count=1,
                    provider="openai"
                )
                self._cleanup_cache()
                logger.info(f"Created new cached system prompt for {task_type}")
            
            # Build message array
            messages = []
            
            # Add system message (always included for OpenAI)
            messages.append({
                "role": "system", 
                "content": system_prompt
            })
            
            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_prompt
            })
            
            return messages, use_cache
            
        except Exception as e:
            logger.error(f"Error preparing OpenAI messages: {e}")
            # Fallback to basic messages
            return [
                {"role": "system", "content": self.system_prompts.get(task_type, self.system_prompts["coding"])},
                {"role": "user", "content": user_prompt}
            ], False
    
    async def prepare_anthropic_messages(self, task_type: str, user_prompt: str,
                                       conversation_history: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]], bool]:
        """Prepare Anthropic messages with caching optimization"""
        try:
            system_prompt = self.system_prompts.get(task_type, self.system_prompts["coding"])
            system_hash = self.system_prompt_hashes.get(task_type, self._compute_hash(system_prompt))
            
            # Check if we can use cached system prompt
            cached_prompt = self.cache.get(system_hash)
            use_cache = False
            
            if cached_prompt:
                # Update usage stats
                cached_prompt.last_used = datetime.now(timezone.utc)
                cached_prompt.usage_count += 1 
                use_cache = True
                logger.info(f"Using cached system prompt for {task_type} (used {cached_prompt.usage_count} times)")
            else:
                # Create new cache entry
                self.cache[system_hash] = CachedPrompt(
                    hash_key=system_hash,
                    system_prompt=system_prompt,
                    created_at=datetime.now(timezone.utc),
                    last_used=datetime.now(timezone.utc),
                    usage_count=1,
                    provider="anthropic"
                )
                self._cleanup_cache()
                logger.info(f"Created new cached system prompt for {task_type}")
            
            # Build messages array (Anthropic separates system from messages)
            messages = []
            
            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_prompt
            })
            
            return system_prompt, messages, use_cache
            
        except Exception as e:
            logger.error(f"Error preparing Anthropic messages: {e}")
            # Fallback to basic messages
            return (
                self.system_prompts.get(task_type, self.system_prompts["coding"]),
                [{"role": "user", "content": user_prompt}],
                False
            )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.cache:
            return {
                "total_entries": 0,
                "total_usage": 0,
                "hit_rate": 0.0,
                "most_used": None
            }
            
        total_usage = sum(prompt.usage_count for prompt in self.cache.values())
        most_used = max(self.cache.values(), key=lambda x: x.usage_count)
        
        # Calculate hit rate (usage > 1 means cache hit)
        cache_hits = sum(1 for prompt in self.cache.values() if prompt.usage_count > 1)
        hit_rate = cache_hits / len(self.cache) if self.cache else 0.0
        
        return {
            "total_entries": len(self.cache),
            "total_usage": total_usage,
            "hit_rate": hit_rate,
            "most_used": {
                "hash": most_used.hash_key[:8],
                "usage_count": most_used.usage_count,
                "provider": most_used.provider,
                "created_at": most_used.created_at.isoformat()
            } if most_used else None,
            "cache_size_limit": self.max_cache_size,
            "ttl_hours": self.cache_ttl_hours
        }
    
    def estimate_cost_savings(self, avg_system_prompt_tokens: int = 500, 
                            cost_per_1k_tokens: float = 0.005) -> Dict[str, float]:
        """Estimate cost savings from prompt caching"""
        if not self.cache:
            return {
                "tokens_saved": 0,
                "cost_saved_eur": 0.0,
                "savings_percentage": 0.0
            }
            
        # Calculate tokens saved from cache hits
        cache_hits = sum(max(0, prompt.usage_count - 1) for prompt in self.cache.values())
        tokens_saved = cache_hits * avg_system_prompt_tokens
        cost_saved = (tokens_saved / 1000) * cost_per_1k_tokens * 0.85  # Convert USD to EUR
        
        # Estimate total tokens that would have been used without caching
        total_usage = sum(prompt.usage_count for prompt in self.cache.values())
        total_tokens_without_cache = total_usage * avg_system_prompt_tokens
        
        savings_percentage = (tokens_saved / total_tokens_without_cache * 100) if total_tokens_without_cache > 0 else 0.0
        
        return {
            "tokens_saved": tokens_saved,
            "cost_saved_eur": cost_saved,
            "savings_percentage": savings_percentage,
            "cache_hits": cache_hits,
            "total_requests": total_usage
        }
    
    async def clear_cache(self):
        """Clear all cached prompts"""
        cleared_count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared {cleared_count} cached prompts")
        return cleared_count