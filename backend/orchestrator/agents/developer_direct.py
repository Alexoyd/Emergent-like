"""
Developer Agent - Direct Write Mode (JSON Operations)

Retourne des opérations JSON au lieu de diffs Git.
Mode par défaut à partir de la Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Dict
import logging
import json
from pydantic import ValidationError

from ..plan_parser import Step
from .planner import ProjectContext
from ..schemas import DeveloperOutput


@dataclass
class OperationsResult:
    """Résultat de génération d'opérations de fichiers"""
    step_id: int
    stack: str
    operations: List[Dict[str, Any]]  # Liste d'opérations validées
    attempts: int
    validated: bool


class OperationsGenerationError(Exception):
    """Erreur lors de la génération d'opérations"""
    pass


class DeveloperAgentDirect:
    """
    Generate file operations (JSON) instead of Git patches
    
    Le LLM retourne du JSON structuré que nous validons et exécutons directement.
    Plus fiable que les patches Git.
    """
    
    def __init__(
        self,
        llm_router: Any,
        rag_system: Any,
        tool_manager: Any,
        max_attempts: int = 3,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.llm_router = llm_router
        self.rag_system = rag_system
        self.tool_manager = tool_manager
        self.max_attempts = max_attempts
        self.log = logger or logging.getLogger(__name__)
    
    async def generate_operations(
        self,
        step: Step,
        project_context: ProjectContext,
        run: Any,
        rag_context: Optional[List[str]] = None,
    ) -> OperationsResult:
        """
        Génère des opérations de fichiers validées pour un step
        
        Returns:
            OperationsResult avec liste d'opérations JSON
        """
        stack = (project_context.metadata or {}).get("stack", "generic").lower()
        project_path = (project_context.metadata or {}).get("project_path")
        file_tree_snippet = (project_context.metadata or {}).get("file_tree", "")
        
        # 1) RAG context
        if rag_context is None and self.rag_system is not None:
            try:
                if hasattr(self.rag_system, "get_context"):
                    rag_context = await self.rag_system.get_context(project_context.code_path)
                elif hasattr(self.rag_system, "get_relevant_chunks"):
                    rag_context = await self.rag_system.get_relevant_chunks(project_context.code_path)
                else:
                    rag_context = []
            except Exception as e:
                self.log.warning(f"RAG context fetching failed: {e}")
                rag_context = []
        
        rag_context = rag_context or []
        
        last_error: Optional[str] = None
        for attempt in range(1, self.max_attempts + 1):
            # 2) Build JSON prompt
            prompt = self._build_json_prompt(
                step=step,
                stack=stack,
                rag_context=rag_context,
                file_tree=file_tree_snippet,
                attempt=attempt,
                last_error=last_error,
            )
            
            # 3) LLM call
            try:
                response = await self.llm_router.generate(
                    prompt=prompt,
                    task_type="coding",
                    current_cost=run.cost_used_eur,
                    budget_limit=run.daily_budget_eur,
                    run_id=run.id,
                )
                llm_text: str = response.content
            except Exception as e:
                last_error = f"LLM error: {e}"
                self.log.warning(last_error)
                continue
            
            # 4) Extract and validate JSON
            try:
                operations = self._extract_and_validate_json(llm_text)
                if not operations:
                    last_error = "No valid JSON operations found in LLM response"
                    self.log.info(f"Attempt {attempt}: {last_error}")
                    continue
                
                # Success!
                self.log.info(f"✅ Generated {len(operations)} valid file operations")
                return OperationsResult(
                    step_id=step.id,
                    stack=stack,
                    operations=operations,
                    attempts=attempt,
                    validated=True,
                )
                
            except Exception as e:
                last_error = f"JSON validation error: {e}"
                self.log.warning(f"Attempt {attempt}: {last_error}")
                continue
        
        # All attempts exhausted
        raise OperationsGenerationError(
            f"Could not generate valid operations for step {step.id} after {self.max_attempts} attempts. "
            f"Last error: {last_error}"
        )
    
    def _build_json_prompt(
        self,
        *,
        step: Step,
        stack: str,
        rag_context: List[str],
        file_tree: str,
        attempt: int,
        last_error: Optional[str],
    ) -> str:
        """
        Construit un prompt pour générer des opérations JSON
        """
        guidelines = self._stack_guidelines(stack)
        rag_block = "\n".join(rag_context[:8]) if rag_context else "(no additional context)"
        error_hint = f"\n⚠️ Previous attempt failed: {last_error}\nPlease fix the issue and try again.\n" if last_error else ""
        
        file_tree_block = (
            f"Existing project structure (partial):\n{file_tree.strip()}\n\n" if file_tree else ""
        )
        
        return (
            "You are a senior software developer. Implement the following step by generating file operations.\n\n"
            f"Step #{step.id}: {step.description}\n\n"
            f"Target stack: {stack}\n\n"
            f"Context from RAG (may include code excerpts, constraints):\n{rag_block}\n\n"
            f"{file_tree_block}"
            f"Coding standards and constraints for this stack:\n{guidelines}\n\n"
            f"{error_hint}"
            "🔥🔥🔥 CRITICAL INSTRUCTIONS - READ CAREFULLY 🔥🔥🔥\n\n"
            "YOU MUST RETURN **ONLY** PURE JSON. NO TEXT BEFORE OR AFTER.\n"
            "DO NOT write explanations, comments, or markdown.\n"
            "DO NOT use ```json code fences.\n"
            "YOUR ENTIRE RESPONSE MUST BE VALID JSON starting with { and ending with }\n\n"
            "REQUIRED JSON STRUCTURE:\n\n"
            "{\n"
            '  "operations": [\n'
            "    {\n"
            '      "type": "create",\n'
            '      "path": "relative/path/to/file.ext",\n'
            '      "content": "full file content here"\n'
            "    },\n"
            "    {\n"
            '      "type": "update",\n'
            '      "path": "relative/path/to/existing.ext",\n'
            '      "content": "complete new content"\n'
            "    },\n"
            "    {\n"
            '      "type": "insert",\n'
            '      "path": "relative/path/to/file.ext",\n'
            '      "after_line": 10,  // 0-indexed: 0=start, -1=EOF\n'
            '      "content": "text to insert"\n'
            "    },\n"
            "    {\n"
            '      "type": "search_replace",\n'
            '      "path": "relative/path/to/file.ext",\n'
            '      "search": "exact text to find",\n'
            '      "replace": "replacement text"\n'
            "    },\n"
            "    {\n"
            '      "type": "rename",\n'
            '      "old_path": "old/path.ext",\n'
            '      "new_path": "new/path.ext"\n'
            "    },\n"
            "    {\n"
            '      "type": "delete",\n'
            '      "path": "relative/path/to/file.ext"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "📋 OPERATION TYPES:\n"
            "• create: New file (must not exist)\n"
            "• update: Replace entire file content (must exist)\n"
            "• insert: Insert text after specific line number (0-indexed: 0=start, N=after line N, -1=EOF)\n"
            "  ⚠️ Line numbers are 0-INDEXED! First line is 0, not 1.\n"
            "  ⚠️ after_line=0 means insert at the very beginning (before all lines)\n"
            "  ⚠️ after_line=-1 means insert at the end of file (EOF anchor)\n"
            "• search_replace: Find and replace exact text\n"
            "• rename: Move or rename file\n"
            "• delete: Remove file\n\n"
            "⚠️ MANDATORY RULES:\n"
            "1. ⛔ NO explanatory text - ONLY JSON\n"
            "2. ⛔ NO markdown code fences (```json)\n"
            "3. ⛔ NO comments inside or outside JSON\n"
            "4. ✅ START your response with {  (opening brace)\n"
            "5. ✅ END your response with }  (closing brace)\n"
            "6. ✅ All paths must be relative (no leading /, no ..)\n"
            "7. ✅ Escape special characters in JSON strings (\\n, \\t, \\\", etc.)\n"
            "8. ✅ Maximum 5 operations per step\n"
            "9. ✅ Operations execute in order - plan dependencies\n\n"
            "🎯 YOUR RESPONSE MUST START EXACTLY LIKE THIS:\n"
            '{"operations": [\n'
        )
    
    def _stack_guidelines(self, stack: str) -> str:
        """Guidelines par stack (réutilise la logique existante)"""
        stack = (stack or "").lower()
        if stack == "laravel":
            return (
                "- PHP 8+, PSR-12, Laravel conventions.\n"
                "- Prefer dependency injection, FormRequests, Eloquent models.\n"
                "- Update routes, controllers, tests (Pest).\n"
                "- Provide migrations/factories when schema changes."
            )
        if stack == "react":
            return (
                "- React 18, functional components, hooks.\n"
                "- TypeScript preferred, Vite or CRA layout respected.\n"
                "- Unit tests with Jest/RTL when altering logic."
            )
        if stack == "vue":
            return (
                "- Vue 3 + Vite, single-file components (.vue).\n"
                "- Composition API.\n"
                "- Unit tests with Vitest where applicable."
            )
        if stack == "python":
            return (
                "- Python 3.10+, PEP8/Flake8, type hints where useful.\n"
                "- Pytest tests for new behavior; keep functions small and pure."
            )
        if stack == "node":
            return (
                "- Node 18+, ESM or CommonJS consistently.\n"
                "- Add Jest tests for business logic."
            )
        return (
            "- Follow idiomatic patterns for the language.\n"
            "- Include minimal tests or usage examples when changing logic."
        )
    
    def _extract_and_validate_json(self, text: str) -> List[Dict[str, Any]]:
        """
        🔥 ENHANCED: Extrait et valide le JSON depuis la réponse du LLM
        Gère divers formats de réponse (markdown, texte explicatif, etc.)
        """
        if not text:
            return []
        
        original_text = text
        text = text.strip()
        
        # 1. Remove markdown code fences (multiple variants)
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```JSON"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # 2. Remove common text prefixes
        common_prefixes = [
            "Here is the JSON:",
            "Here's the JSON:",
            "The JSON output is:",
            "JSON:",
            "Response:",
            "Output:",
        ]
        for prefix in common_prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        # 3. Try to parse JSON directly first
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            # 4. Try to extract JSON from text by finding first { and last }
            start = text.find("{")
            end = text.rfind("}")
            
            if start != -1 and end != -1 and start < end:
                json_candidate = text[start:end+1]
                try:
                    data = json.loads(json_candidate)
                    self.log.info(f"✅ Extracted JSON from position {start} to {end}")
                except json.JSONDecodeError as e2:
                    # 5. Last resort: try to find {"operations": pattern
                    ops_start = text.find('{"operations":')
                    if ops_start == -1:
                        ops_start = text.find("{'operations':")
                    
                    if ops_start != -1:
                        # Find matching closing brace
                        bracket_count = 0
                        for i in range(ops_start, len(text)):
                            if text[i] == '{':
                                bracket_count += 1
                            elif text[i] == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    json_candidate = text[ops_start:i+1]
                                    try:
                                        data = json.loads(json_candidate)
                                        self.log.info(f"✅ Extracted JSON using bracket counting")
                                        break
                                    except:
                                        pass
                        else:
                            self.log.error(f"❌ JSON extraction failed. Original text length: {len(original_text)}")
                            self.log.error(f"First 200 chars: {original_text[:200]}")
                            raise ValueError(f"Could not parse JSON: {e}")
                    else:
                        self.log.error(f"❌ No JSON structure found in response")
                        self.log.error(f"First 200 chars: {original_text[:200]}")
                        raise ValueError(f"No valid JSON found in response: {e}")
            else:
                self.log.error(f"❌ No JSON braces found in response")
                raise ValueError(f"No valid JSON found in response: {e}")
        
        # 6. Validate with Pydantic
        try:
            validated = DeveloperOutput(**data)
            # Convert Pydantic models to dicts
            operations = [op.dict() for op in validated.operations]
            self.log.info(f"✅ Validated {len(operations)} operations")
            return operations
        except ValidationError as e:
            self.log.error(f"❌ JSON validation failed: {e}")
            self.log.error(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            raise ValueError(f"JSON validation failed: {e}")
