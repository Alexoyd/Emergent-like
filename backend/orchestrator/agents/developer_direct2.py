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
import re
from pathlib import Path
from pydantic import ValidationError

from ..plan_parser import Step
from .planner import ProjectContext
from ..schemas import DeveloperOutput


@dataclass
class OperationsResult:
    """Résultat de génération d'opérations de fichiers"""
    step_id: int
    stack: str
    operations: List[Dict[str, Any]]
    attempts: int
    validated: bool
    warnings: List[str] = None  # 🔧 FIX: Ajouter warnings dans le résultat


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
    
    def _read_important_files(
        self, 
        project_path: str, 
        stack: str,
        max_files: int = 8,  # 🔧 FIX: Limiter le nombre de fichiers
        max_bytes_per_file: int = 10000  # 🔧 FIX: Réduire la taille max
    ) -> Dict[str, str]:
        """
        Lit un sous-ensemble de fichiers critiques pour fournir un contexte fiable
        aux opérations 'search_replace' (contenu exact attendu).
        
        🔧 FIX: Ajout de limites strictes pour éviter les dépassements de contexte
        """
        root = Path(project_path)
        files: Dict[str, str] = {}
        file_count = 0

        def safe_read(relpath: str, max_bytes: int = None) -> bool:
            """Returns True if file was read successfully"""
            nonlocal file_count
            if file_count >= max_files:
                return False
                
            p = root / relpath
            try:
                if p.exists() and p.is_file():
                    limit = max_bytes or max_bytes_per_file
                    content = p.read_text(encoding="utf-8", errors="replace")
                    if len(content) > limit:
                        content = content[:limit] + "\n... (truncated)"
                    files[relpath] = content
                    file_count += 1
                    return True
            except Exception as e:
                self.log.debug(f"Skip read {relpath}: {e}")
            return False

        # Priorité 1: Fichiers critiques (toujours lire)
        critical_files = [
            "routes/web.php",
            "routes/api.php",
            "database/seeders/DatabaseSeeder.php",
        ]
        
        for cf in critical_files:
            safe_read(cf, max_bytes=15000)  # Plus de contexte pour les fichiers critiques
        
        # Priorité 2: Configuration
        if file_count < max_files:
            for cf in ["composer.json", "package.json", "config/app.php"]:
                if not safe_read(cf):
                    break
        
        # Priorité 3: Controllers (Laravel only, limité)
        if stack == "laravel" and file_count < max_files:
            controllers_dir = root / "app" / "Http" / "Controllers"
            if controllers_dir.exists():
                for p in sorted(controllers_dir.rglob("*.php"))[:5]:  # Max 5 controllers
                    rel = str(p.relative_to(root))
                    if not safe_read(rel, max_bytes=8000):
                        break

        self.log.info(f"📚 Loaded {len(files)} files for context (limit: {max_files})")
        return files
    
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
            OperationsResult avec liste d'opérations JSON et warnings éventuels
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
        
        # 📚 Read important files for search_replace context
        file_contents: Dict[str, str] = {}
        if project_path:
            try:
                file_contents = self._read_important_files(str(project_path), stack)
            except Exception as e:
                self.log.warning(f"Could not read important files: {e}")
                file_contents = {}
        
        for attempt in range(1, self.max_attempts + 1):
            # 2) Build JSON prompt
            prompt = self._build_json_prompt(
                step=step,
                stack=stack,
                rag_context=rag_context,
                file_tree=file_tree_snippet,
                attempt=attempt,
                last_error=last_error,
                file_contents=file_contents,
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

                # 5) Stack-specific coherence validation
                warnings: List[str] = []
                if stack == "laravel":
                    warnings = self._validate_laravel_coherence(operations, stack)
                    if warnings:
                        self.log.warning(f"🔍 Laravel coherence checks found {len(warnings)} potential issues:")
                        for warning in warnings:
                            self.log.warning(f"  {warning}")
                
                # Success!
                self.log.info(f"✅ Generated {len(operations)} valid file operations")
                return OperationsResult(
                    step_id=step.id,
                    stack=stack,
                    operations=operations,
                    attempts=attempt,
                    validated=True,
                    warnings=warnings or [],  # 🔧 FIX: Inclure warnings
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
        file_contents: Optional[Dict[str, str]] = None,
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

        # 📄 File contents block
        file_contents_block = ""
        if file_contents:
            file_contents_block = (
                "\n📄 CURRENT FILE CONTENTS (CRITICAL - READ BEFORE search_replace!):\n"
                "🚨 These are the ACTUAL current contents of important files.\n"
                "🚨 When using 'search_replace', copy the EXACT text from below!\n"
                "🚨 DO NOT guess - use these exact strings!\n\n"
            )
            for file_path, content in file_contents.items():
                max_chars = 2000 if file_path in ["routes/web.php", "routes/api.php"] else 800
                truncated = content if len(content) <= max_chars else content[:max_chars] + "\n... (truncated)"
                file_contents_block += f"### {file_path}\n```\n{truncated}\n```\n\n"
        
        return (
            "You are a senior software developer. Implement the following step by generating file operations.\n\n"
            f"Step #{step.id}: {step.description}\n\n"
            f"Target stack: {stack}\n\n"
            f"Context from RAG (may include code excerpts, constraints):\n{rag_block}\n\n"
            f"{file_tree_block}"
            f"{file_contents_block}"
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
            '      "after_line": 10,\n'
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
            "• insert: Insert text AFTER specific line number (0-indexed)\n"
            "  ⚠️ Line numbers are 0-INDEXED! Line 0 is the first line.\n"
            "  🚨 For PHP files: NEVER use after_line=0! Use search_replace instead.\n"
            "• search_replace: Find and replace exact text (RECOMMENDED for routes/web.php)\n"
            "  🚨 CRITICAL: Match whitespace and indentation EXACTLY\n"
            "• rename: Move or rename file\n"
            "• delete: Remove file\n\n"
            "⚠️ MANDATORY RULES:\n"
            "1. ⛔ NO explanatory text - ONLY JSON\n"
            "2. ⛔ NO markdown code fences (```json)\n"
            "3. ⛔ NO comments inside or outside JSON\n"
            "4. ✅ START with {  END with }\n"
            "5. ✅ All paths must be relative (no leading /, no ..)\n"
            "6. ✅ Use proper JSON escaping: \\n \\t \\\"\n"
            "7. ✅ Maximum 5 operations per step\n"
            "8. ✅ Use 0-indexed line numbers for insert\n"
            "🎯 YOUR RESPONSE MUST START EXACTLY LIKE THIS:\n"
            '{"operations": [\n'
        )
    
    def _stack_guidelines(self, stack: str) -> str:
        """Guidelines par stack"""
        stack = (stack or "").lower()
        if stack == "laravel":
            return """🎯 TARGET: Laravel 12+ (PHP 8.3+, Vite assets)

📋 CORE PRINCIPLES:
- PHP 8.3+, PSR-12, Laravel 12 conventions
- Dependency injection, FormRequests, Eloquent models
- Update routes, controllers, tests (Pest/PHPUnit)

🎨 ASSETS & VITE:
  ✅ ALWAYS use @vite() directive in Blade:
     @vite(['resources/css/app.css', 'resources/js/app.js'])
  ❌ NEVER use {{ asset('css/app.css') }} for main stylesheets

🎯 CONTROLLERS & ROUTES (CRITICAL ORDER):
  1️⃣ FIRST: Create controller in app/Http/Controllers/
  2️⃣ THEN: Add route referencing controller
  3️⃣ FINALLY: Create Blade views

🚨 ROUTES FILE (routes/web.php) - CRITICAL:
  ⛔ NEVER insert at line 0 or 1
  ✅ ALWAYS use "search_replace" for routes/web.php
  ✅ Read file content from context before modifying

🏠 DEFAULT ROUTE (MANDATORY):
  🚨 ALWAYS modify '/' route - users should see YOUR app
  ✅ Replace: Route::get('/', [YourController::class, 'index']);
  ✅ Or redirect: Route::redirect('/', '/main-feature');

🗄️ DATABASE & SEEDERS:
  ✅ Use search_replace to call custom seeders
  ⚠️ Match EXACT indentation (4 spaces in Laravel 12)

✅ VALIDATION & SECURITY:
  - FormRequest classes for complex validation
  - @csrf token in all forms
  - Route model binding when appropriate

🧪 TESTING:
  - Pest tests for new features (Laravel 12 default)
  - Location: tests/Feature/ and tests/Unit/
"""
        
        if stack == "react":
            return "- React 18, functional components, hooks\n- TypeScript preferred, Vite/CRA layout\n- Unit tests with Jest/RTL"
        
        if stack == "vue":
            return "- Vue 3 + Vite, single-file components\n- Composition API\n- Vitest tests"
        
        if stack == "python":
            return "- Python 3.10+, PEP8, type hints\n- Pytest tests"
        
        if stack == "node":
            return "- Node 18+, ESM/CommonJS consistently\n- Jest tests"
        
        return "- Follow idiomatic patterns\n- Include tests for new logic"
    
    def _extract_and_validate_json(self, text: str) -> List[Dict[str, Any]]:
        """
        🔧 ENHANCED: Extrait et valide le JSON depuis la réponse du LLM
        """
        if not text:
            return []
        
        original_text = text
        text = text.strip()
        
        # 1. Remove markdown code fences
        if text.startswith("```json") or text.startswith("```JSON"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # 2. Remove common text prefixes
        for prefix in ["Here is the JSON:", "Here's the JSON:", "JSON:", "Output:"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        # 🔧 FIX: Remove trailing commas (common LLM mistake)
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # 🔧 FIX: Remove single-line comments
        text = re.sub(r'//.*?\n', '\n', text)
        
        # 3. Try direct parse
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            # 4. Extract JSON by finding braces
            start = text.find("{")
            end = text.rfind("}")
            
            if start != -1 and end != -1 and start < end:
                json_candidate = text[start:end+1]
                # Clean trailing commas again
                json_candidate = re.sub(r',(\s*[}\]])', r'\1', json_candidate)
                
                try:
                    data = json.loads(json_candidate)
                    self.log.info(f"✅ Extracted JSON from position {start} to {end}")
                except json.JSONDecodeError:
                    # 5. Last resort: bracket counting
                    ops_start = text.find('{"operations":')
                    if ops_start != -1:
                        bracket_count = 0
                        for i in range(ops_start, len(text)):
                            if text[i] == '{':
                                bracket_count += 1
                            elif text[i] == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    json_candidate = text[ops_start:i+1]
                                    json_candidate = re.sub(r',(\s*[}\]])', r'\1', json_candidate)
                                    try:
                                        data = json.loads(json_candidate)
                                        self.log.info("✅ Extracted JSON using bracket counting")
                                        break
                                    except:
                                        pass
                        else:
                            self.log.error(f"❌ JSON extraction failed. First 200 chars: {original_text[:200]}")
                            raise ValueError(f"Could not parse JSON: {e}")
                    else:
                        self.log.error(f"❌ No JSON structure found. First 200 chars: {original_text[:200]}")
                        raise ValueError(f"No valid JSON: {e}")
            else:
                self.log.error("❌ No JSON braces found")
                raise ValueError(f"No valid JSON: {e}")
        
        # 6. Validate with Pydantic
        try:
            validated = DeveloperOutput(**data)
            operations = [op.dict() for op in validated.operations]
            operations = self._fix_literal_escapes(operations)
            
            self.log.info(f"✅ Validated {len(operations)} operations")
            return operations
        except ValidationError as e:
            self.log.error(f"❌ JSON validation failed: {e}")
            raise ValueError(f"JSON validation failed: {e}")
    
    def _fix_literal_escapes(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        🔧 FIX: Corrige les séquences d'échappement littérales
        """
        fixed_operations = []
        
        for op in operations:
            op = op.copy()
            
            # Nettoyer les champs texte
            for field in ['content', 'search', 'replace']:
                if field in op and isinstance(op[field], str):
                    value = op[field]
                    # Détecter \n littéraux (pas de vrais retours à la ligne)
                    if '\\n' in value and '\n' not in value:
                        value = value.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                        op[field] = value
                        self.log.warning(f"⚠️ Fixed literal escapes in {field} for {op.get('path', 'unknown')}")
            
            fixed_operations.append(op)
        
        return fixed_operations
    
    def _validate_laravel_coherence(self, operations: List[Dict[str, Any]], stack: str) -> List[str]:
        """
        🔧 FIX: Validate Laravel-specific coherence rules
        Returns list of warning messages (non-blocking)
        """
        if stack != "laravel":
            return []
        
        warnings = []
        
        # Extract files being created/modified
        controller_files = []
        route_files = []
        
        for op in operations:
            path = op.get('path', '')
            
            if 'app/Http/Controllers/' in path:
                controller_files.append(path)
            elif 'routes/' in path:
                route_files.append(path)
        
        # Check routes for controller references
        for route_op in [op for op in operations if 'routes/' in op.get('path', '')]:
            content = route_op.get('content', '') or ''
            replace = route_op.get('replace', '') or ''
            full_content = content + replace
            
            # Find controller references: SomeController::class
            controller_refs = re.findall(r'([A-Z][a-zA-Z0-9]*Controller)::class', full_content)
            
            for controller_name in controller_refs:
                found = any(controller_name in ctrl_file for ctrl_file in controller_files)
                
                if not found:
                    warnings.append(
                        f"⚠️ Route references '{controller_name}' but controller not created in this step. "
                        f"Expected: app/Http/Controllers/{controller_name}.php"
                    )
        
        # Check for old asset() usage in views
        for view_op in [op for op in operations if 'resources/views/' in op.get('path', '')]:
            content = view_op.get('content', '') or ''
            
            if "{{ asset('css/" in content or '{{ asset("css/' in content:
                warnings.append(
                    f"⚠️ View '{view_op.get('path')}' uses old asset() syntax. "
                    f"Use @vite(['resources/css/app.css']) instead for Laravel 12."
                )
        
        # 🔧 FIX: Vérifier modification de la route '/' (INDENTATION CORRIGÉE)
        for route_op in [op for op in operations if 'routes/web.php' in op.get('path', '')]:
            content = route_op.get('content', '') or ''
            replace = route_op.get('replace', '') or ''
            search = route_op.get('search', '') or ''
            
            modifies_root_route = (
                "view('welcome')" in search or
                "return view('welcome')" in content or
                "Route::get('/'," in replace or
                "Route::redirect('/'," in replace
            )
            
            # Si création de routes mais pas de modif '/', warning
            if not modifies_root_route:
                route_count = content.count('Route::') + replace.count('Route::')
                if route_count > 0:
                    warnings.append(
                        "🚨 CRITICAL: Creating routes but NOT modifying '/' (root route). "
                        "Users will see Laravel welcome page instead of your app! "
                        "Add operation to replace default route."
                    )
        
        return warnings