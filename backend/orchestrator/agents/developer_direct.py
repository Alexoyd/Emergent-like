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
import os
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

    # --- AJOUT 1 : méthode utilitaire avec LIMITES STRICTES (de developer_direct2.py) ---
    def _read_important_files(
        self, 
        project_path: str, 
        stack: str,
        max_files: int = 8,  # 🔧 FIX: Limiter le nombre de fichiers pour éviter dépassement contexte
        max_bytes_per_file: int = 10000  # 🔧 FIX: Réduire la taille max par fichier
    ) -> Dict[str, str]:
        """
        Lit un sous-ensemble de fichiers critiques pour fournir un contexte fiable
        aux opérations 'search_replace' (contenu exact attendu).
        
        🔧 FIX CRITIQUE: Ajout de limites strictes pour éviter les dépassements de contexte LLM
        - Max 8 fichiers (vs illimité avant)
        - Max 10KB par fichier (vs 20KB avant)
        - Système de priorités (critical files first)
        """
        root = Path(project_path)
        files: Dict[str, str] = {}
        file_count = 0  # 🔧 Compteur global

        def safe_read(relpath: str, max_bytes: int = None) -> bool:
            """Returns True if file was read successfully"""
            nonlocal file_count
            if file_count >= max_files:  # 🔧 PROTECTION: Stop si limite atteinte
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

        # 🎯 PRIORITÉ 1: Fichiers critiques (toujours lire)
        critical_files = [
            "routes/web.php",
            "routes/api.php",
            "composer.json",
            "package.json",
            "config/app.php",
            "bootstrap/app.php",
        ]
        
        for f in critical_files:
            if file_count >= max_files:
                break
            safe_read(f)
        
        # 🎯 PRIORITÉ 2: Assets (si encore de la place)
        if file_count < max_files:
            safe_read("resources/css/app.css")
        if file_count < max_files:
            safe_read("resources/js/app.js")
        
        # 🎯 PRIORITÉ 3: Seeders (si encore de la place)
        if file_count < max_files:
            safe_read("database/seeders/DatabaseSeeder.php")

        # 🎯 PRIORITÉ 4: Controllers Laravel (si encore de la place)
        if stack == "laravel" and file_count < max_files:
            controllers_dir = root / "app" / "Http" / "Controllers"
            if controllers_dir.exists():
                for p in controllers_dir.rglob("*.php"):
                    if file_count >= max_files:  # 🔧 STOP si limite atteinte
                        break
                    rel = str(p.relative_to(root))
                    safe_read(rel, max_bytes=8000)  # Controllers plus petits

        self.log.info(f"📚 Loaded {file_count}/{max_files} files for context ({sum(len(c) for c in files.values())} chars total)")
        return files
    
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
                # Build semantic query contextualized by step
                goal = (project_context.metadata or {}).get("goal", "")
                rag_query = f"""Run goal: {goal}
Stack: {stack}
Current step: {step.description}"""
                
                if hasattr(self.rag_system, "get_context"):
                    rag_context = await self.rag_system.get_context(rag_query, max_chunks=8)
                elif hasattr(self.rag_system, "get_relevant_chunks"):
                    rag_context = await self.rag_system.get_relevant_chunks(rag_query, max_chunks=8)
                else:
                    rag_context = []
            except Exception as e:
                self.log.warning(f"RAG context fetching failed: {e}")
                rag_context = []
        
        rag_context = rag_context or []
        
        # --- AJOUT 2 : initialiser last_error avant la boucle ---
        last_error: Optional[str] = None
        
        # 🔥 PHASE 2 FIX: Smart Content Reading (technique Emergent.sh)
        # Lire les fichiers importants AVANT génération pour contexte précis
        file_contents: Optional[Dict[str, str]] = {}
        if project_path:
            try:
                file_contents = self._read_important_files(str(project_path), stack)
                self.log.info(f"📚 [Smart Reading] Loaded {len(file_contents)} files for precise context")
            except Exception as e:
                self.log.warning(f"Could not read important files: {e}")
                file_contents = {}
        
        # 🔥 SOLUTION 3: Smart Content Reading + File Existence Detection (Emergent.sh strategy)
        # Exemple: "modify routes/web.php" → lire ce fichier spécifiquement
        # NOUVEAU: Détecter fichiers manquants et en informer le LLM
        missing_files = []
        if project_path and file_contents is not None:
            try:
                # Extraire fichiers mentionnés dans la description du step
                import re
                step_desc = step.description.lower()
                potential_files = re.findall(r'[\w/]+\.(?:php|js|py|vue|tsx|jsx|blade\.php)', step_desc)
                
                # Also check common Laravel files
                if stack == "laravel":
                    potential_files.extend(["routes/web.php", "routes/api.php", "routes/channels.php"])
                
                # Remove duplicates
                potential_files = list(set(potential_files))
                
                for file_path in potential_files:
                    if file_path not in file_contents:
                        full_path = Path(project_path) / file_path
                        if full_path.exists():
                            try:
                                content = full_path.read_text(encoding='utf-8', errors='replace')
                                file_contents[file_path] = content[:10000]  # Max 10KB
                                self.log.info(f"📖 [Smart Reading] Loaded target file: {file_path}")
                            except:
                                pass
                        else:
                            # File doesn't exist - track it
                            missing_files.append(file_path)
                            self.log.info(f"❌ [Smart Reading] File does NOT exist: {file_path}")
            except Exception as e:
                self.log.debug(f"Target file detection failed: {e}")
        
        ast_error: Optional[str] = None
        for attempt in range(1, self.max_attempts + 1):
            # 2) Build JSON prompt with enhanced error feedback
            prompt = self._build_json_prompt(
                step=step,
                stack=stack,
                rag_context=rag_context,
                file_tree=file_tree_snippet,
                attempt=attempt,
                last_error=last_error,
                file_contents=file_contents,  # 🔥 NOUVEAU
                missing_files=missing_files,  # 🔥 SOLUTION 3
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
                last_error = f"LLM API error: {e}"
                self.log.warning(f"❌ Attempt {attempt}/{self.max_attempts}: {last_error}")
                continue
            
            # 4) Extract and validate JSON with auto-repair
            try:
                operations = self._extract_and_validate_json(llm_text)
                if not operations:
                    last_error = (
                        "No valid JSON operations found in LLM response. "
                        "CRITICAL: Your response MUST be valid JSON starting with {\"operations\": ["
                    )
                    self.log.warning(f"❌ Attempt {attempt}/{self.max_attempts}: {last_error}")
                    # 🔥 NOUVEAU: Log first 500 chars of response for debugging
                    self.log.debug(f"LLM response preview: {llm_text[:500]}")
                    continue

                # 🔥 NOUVEAU: Normaliser les opérations avant validation Laravel
                operations = self._normalize_operations(operations, project_path, stack)

                # 5) Laravel-specific coherence validation (warnings only)
                if stack == "laravel":
                    warnings = self._validate_laravel_coherence(operations, stack)
                    if warnings:
                        self.log.warning(f"🔍 Laravel coherence checks found {len(warnings)} potential issues:")
                        for warning in warnings:
                            self.log.warning(f"  {warning}")
                        # Don't fail, just log warnings for debugging
                
                # Success!
                self.log.info(f"✅ Generated {len(operations)} valid file operations on attempt {attempt}/{self.max_attempts}")
                if attempt > 1:
                    self.log.info(f"📊 Success after {attempt} attempts (auto-repair may have been applied)")
                return OperationsResult(
                    step_id=step.id,
                    stack=stack,
                    operations=operations,
                    attempts=attempt,
                    validated=True,
                )
                
            except Exception as e:
                # 🔥 AMÉLIORATION: Feedback détaillé pour le prochain essai
                error_details = str(e)
                if "Field required" in error_details:
                    last_error = (
                        f"JSON validation error: {error_details}"
                        f"🚨 CRITICAL: The 'operations' field is REQUIRED!"
                        f"Your JSON MUST have this exact structure:"
                        f'{{"operations": [{{"type": "create", "path": "...", "content": "..."}}]}}'
                        f"DO NOT return just a single operation object. Wrap it in an 'operations' array!")
                elif "not a dict" in error_details:
                    last_error = (
                        f"JSON validation error: {error_details}"
                        f"🚨 Your response must be a JSON OBJECT starting with {{"
                        f"NOT a string, NOT an array, NOT plain text.")
                else:
                    last_error = f"JSON validation error: {error_details}"
                
                self.log.warning(f"❌ Attempt {attempt}/{self.max_attempts}: {last_error}")
                # Log response preview for last attempt
                if attempt == self.max_attempts:
                    self.log.error(f"💀 Final attempt failed. LLM response preview: {llm_text[:500]}")
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
        file_contents: Optional[Dict[str, str]] = None,  # 🔥 NOUVEAU
        missing_files: List[str] = None,  # 🔥 SOLUTION 3
    ) -> str:
        """
        🔥 SOLUTION 3: Construit un prompt avec information sur fichiers existants/manquants
        """
        guidelines = self._stack_guidelines(stack)
        rag_block = "\n".join(rag_context[:8]) if rag_context else "(no additional context)"
        error_hint = f"\n⚠️ Previous attempt failed: {last_error}\nPlease fix the issue and try again.\n" if last_error else ""
        
        file_tree_block = (
            f"Existing project structure (partial):\n{file_tree.strip()}\n\n" if file_tree else ""
        )

        # 🔥 RADICAL REDESIGN: Block avec contenu ET instructions ultra-explicites
        file_contents_block = ""
        if file_contents:
            file_contents_block = (
                "\n" + "="*80 + "\n"
                "📄 CURRENT FILE CONTENTS - MANDATORY READING\n"
                "="*80 + "\n\n"
                "🚨🚨🚨 CRITICAL INSTRUCTIONS FOR search_replace OPERATIONS 🚨🚨🚨\n\n"
                "IF YOU USE 'search_replace' WITHOUT READING THIS, YOUR OPERATION WILL FAIL!\n\n"
                "RULES (FOLLOW EXACTLY OR OPERATION FAILS):\n"
                "1. ✅ DO: Copy the EXACT text from the file contents below\n"
                "2. ✅ DO: Include surrounding lines for context (5-10 lines)\n"
                "3. ✅ DO: Preserve ALL whitespace, indentation, quotes exactly\n"
                "4. ❌ DON'T: Invent or guess what the file contains\n"
                "5. ❌ DON'T: Paraphrase or summarize the content\n"
                "6. ❌ DON'T: Use partial matches or fragments\n\n"
                "⚠️ CONSEQUENCE: If your 'search' text doesn't match EXACTLY → Operation FAILS\n\n"
                "📖 EXAMPLE OF CORRECT search_replace:\n"
                "Given file content:\n"
                "```php\n"
                "Route::get('/', function () {\n"
                "    return view('welcome');\n"
                "});\n"
                "```\n\n"
                "✅ CORRECT search_replace:\n"
                "{\n"
                '  "type": "search_replace",\n'
                '  "path": "routes/web.php",\n'
                '  "search": "Route::get(\'/\', function () {\\n    return view(\'welcome\');\\n});",\n'
                '  "replace": "Route::get(\'/\', function () {\\n    return view(\'dashboard\');\\n});"\n'
                "}\n\n"
                "❌ WRONG (will FAIL):\n"
                "{\n"
                '  "type": "search_replace",\n'
                '  "search": "return view(\'welcome\')",  // ❌ Missing context\n'
                '  "replace": "return view(\'dashboard\')"\n'
                "}\n\n"
                "NOW READ THE ACTUAL FILE CONTENTS BELOW:\n"
                "="*80 + "\n\n"
            )
            for file_path, content in file_contents.items():
                # Montrer PLUS de contenu pour tous les fichiers
                max_chars = 5000  # Augmenté de 2000 à 5000
                truncated = content if len(content) <= max_chars else content[:max_chars] + "\n... (truncated - but you have enough context)"
                
                file_contents_block += (
                    f"FILE: {file_path}\n"
                    f"{'─'*80}\n"
                    f"CONTENT (Use this EXACT text for search_replace):\n"
                    f"```\n{truncated}\n```\n"
                    f"{'─'*80}\n"
                    f"⚠️ To modify this file, copy lines from above EXACTLY!\n\n"
                )
        
        # 🔥 SOLUTION 3: Block pour fichiers manquants (Emergent.sh strategy)
        missing_files_block = ""
        if missing_files and len(missing_files) > 0:
            missing_files_block = (
                "\n❌ MISSING FILES (DO NOT EXIST YET):\n"
                "🚨 The following files DO NOT exist in the project:\n"
                "🚨 You MUST use 'create' operation (NOT 'search_replace' or 'update')!\n"
                "🚨 Using 'search_replace' on these files WILL FAIL!\n\n"
            )
            for file_path in missing_files:
                missing_files_block += f"  • {file_path} - DOES NOT EXIST (use 'create')\n"
            missing_files_block += "\n"
        
        return (
            "You are a senior software developer. Implement the following step by generating file operations.\n\n"
            f"Step #{step.id}: {step.description}\n\n"
            f"Target stack: {stack}\n\n"
            f"Context from RAG (may include code excerpts, constraints):\n{rag_block}\n\n"
            f"{file_tree_block}"
            f"{file_contents_block}"  # 🔥 Ajout du contenu des fichiers
            f"{missing_files_block}"  # 🔥 SOLUTION 3: Fichiers manquants
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
            "    },\n"
            "   {\n"
            '      "type": "ensure",\n'
            '      "path": "relative/path/to/existing.ext",\n'
            '      "content": "complete new content"\n'
            "   }\n"
            "  ]\n"
            "}\n\n"
            "📋 OPERATION TYPES:\n"
            "• create: New file (must not exist)\n"
            "• update: Replace entire file content (must exist)\n"
            "• ensure: Idempotent operation - creates if missing, updates if exists (RECOMMENDED for robustness)"
            "• insert: Insert text AFTER specific line number (0-indexed lines)\n"
            "  ⚠️ Line numbers are 0-INDEXED! Line 0 is the first line.\n"
            "  ⚠️ after_line=0 means insert AFTER line 0 (first line) → becomes line 1\n"
            "  ⚠️ after_line=1 means insert AFTER line 1 (second line) → becomes line 2)\n"
            "  🚨 For PHP files (routes/web.php, etc): NEVER use after_line=0!\n"
            "     This would insert after <?php, breaking imports. Use search_replace instead!\n"
            "• search_replace: Find and replace exact text (RECOMMENDED for routes/web.php)\n"
            "  🚨 CRITICAL: You MUST know the EXACT current content before using search_replace!\n"
            "  ⚠️ If unsure of file content, use RAG context or read file structure from plan\n"
            "  ⚠️ Common files content:\n"
            "     - Laravel 12 DatabaseSeeder.php has: public function run(): void { // User::factory(10)->create(); }\n"
            "     - Laravel 12 routes/web.php has: Route::get('/', function () { return view('welcome'); });\n"
            "  ✅ Match whitespace, line breaks, and indentation EXACTLY\n"
            "• rename: Move or rename file\n"
            "• delete: Remove file\n\n"
            "⚠️ MANDATORY RULES:\n"
            "1. ⛔ NO explanatory text - ONLY JSON\n"
            "2. ⛔ NO markdown code fences (```json)\n"
            "3. ⛔ NO comments inside or outside JSON\n"
            "4. ✅ START your response with {  (opening brace)\n"
            "5. ✅ END your response with }  (closing brace)\n"
            "6. ✅ All paths must be relative (no leading /, no ..)\n"
            "7. ✅ Use SIMPLE JSON escaping - NO DOUBLE/TRIPLE ESCAPING:\n"
            "   ✅ CORRECT escaping:\n"
            "      • Newline: \\n (2 characters: backslash + n)\n"
            "      • Tab: \\t (2 characters: backslash + t)\n"
            "      • Quote: \\\" (2 characters: backslash + quote)\n"
            "      • Backslash: \\\\ (2 backslashes)\n"
            "   ❌ WRONG - DO NOT use multiple backslashes:\n"
            "      • \\\\n (4 backslashes) ❌\n"
            "      • \\\\\\\" (3+ backslashes) ❌\n"
            "      • \\\\\\\\n (6+ backslashes) ❌\n"
            "   📝 Examples of CORRECT content:\n"
            "      • \"content\": \"<html>\\n<head>\\n\" ✅\n"
            "      • \"content\": \"<meta charset=\\\"UTF-8\\\">\" ✅\n"
            "      • \"content\": \"<?php\\nnamespace App;\\n\" ✅\n"
            "   📝 Examples of WRONG content (will cause errors):\n"
            "      • \"content\": \"<html>\\\\n<head>\\\\n\" ❌ (double-escaped)\n"
            "      • \"content\": \"<meta charset=\\\\\\\"UTF-8\\\\\\\">\" ❌ (triple-escaped)\n"
            "   🎯 RULE: In valid JSON, you should see EXACTLY ONE backslash before special chars\n"
            "8. ✅ Maximum 5 operations per step\n"
            "9. ✅ Operations execute in order automatically (create before insert/update)\n"
            "10. ✅ Use 0-indexed line numbers for insert operations\n"
            "🎯 YOUR RESPONSE MUST START EXACTLY LIKE THIS:\n"
            '{"operations": [\n'
        )
    
    def _stack_guidelines(self, stack: str) -> str:
        """Guidelines par stack (réutilise la logique existante)"""
        stack = (stack or "").lower()
        if stack == "laravel":
            return (
            """🎯 TARGET: Laravel 12+ (PHP 8.3+, Vite assets, modern conventions)

📋 CORE PRINCIPLES:
- PHP 8.3+, PSR-12 coding standards, Laravel 12 conventions
- Prefer dependency injection, FormRequests validation, Eloquent models
- Update routes, controllers, tests (Pest/PHPUnit)
- Provide migrations/seeders/factories when schema changes

🎨 ASSETS & VITE (Laravel 10+/11+/12+):
  ⚠️ CRITICAL: Laravel 12 uses Vite for asset compilation
  ✅ ALWAYS use @vite() directive in Blade templates:
     @vite(['resources/css/app.css', 'resources/js/app.js'])
  ❌ NEVER use {{ asset('css/app.css') }} for main stylesheets
  ✅ Assets location: resources/css/ and resources/js/ (NOT public/)
  ✅ Compiled output goes to public/build/ automatically
  📝 Example Blade head section:
     <head>
         <meta charset="UTF-8">
         <meta name="viewport" content="width=device-width, initial-scale=1.0">
         <title>{{ $title ?? 'Laravel App' }}</title>
         @vite(['resources/css/app.css', 'resources/js/app.js'])
     </head>

🎯 CONTROLLERS & ROUTES (CRITICAL ORDER):
  ⚠️ MANDATORY: Create controllers BEFORE referencing in routes
  1️⃣ FIRST: Create controller file in app/Http/Controllers/
  2️⃣ THEN: Add route that references the controller
  3️⃣ FINALLY: Create corresponding Blade views
  📝 Controller naming: PascalCase + 'Controller' suffix (e.g., ProductController)
  📝 Controller template:
     <?php
     namespace App\Http\Controllers;
     use Illuminate\Http\Request;
     class YourController extends Controller {
         public function index() {
             return view('your_view');
         }
     }
  ✅ Each route action MUST have corresponding controller method
  ✅ Use resource controllers for CRUD: Route::resource('products', ProductController::class)

🚨 ROUTES FILE MODIFICATION (routes/web.php) - CRITICAL RULES:
  ⛔ NEVER insert before <?php tag - file will be corrupted!
  ⛔ NEVER insert at line 0 or 1 - this puts code before <?php
  ✅ ALWAYS use "search_replace" operation for routes/web.php
  ✅ ALWAYS read the ENTIRE file first to see existing structure
  ✅ Use search_replace to add new "use" imports after existing ones
  ✅ Use search_replace to add new routes after existing routes or at EOF
  
  📝 CORRECT Example for adding a route:
  {
    "type": "search_replace",
    "path": "routes/web.php",
    "search": "use Illuminate\Support\Facades\Route;",
    "replace": "use Illuminate\Support\Facades\Route;
use App\Http\Controllers\ProductController;"
  }
  Then add the route itself at the end:
  {
    "type": "search_replace", 
    "path": "routes/web.php",
    "search": "Route::get('/', function () {
    return view('welcome');
});",
    "replace": "Route::get('/', function () {
    return view('welcome');
});

Route::get('/products', [ProductController::class, 'index']);"
  }
  
  ❌ WRONG Example (NEVER DO THIS):
  {
    "type": "insert",
    "path": "routes/web.php", 
    "after_line": 0,  // ❌ This inserts BEFORE <?php tag!
    "content": "use App\Http\Controllers\ProductController;"
  }

🏠 DEFAULT ROUTE HANDLING (MANDATORY):
  🚨 CRITICAL: When building ANY application, ALWAYS modify the '/' route!
  
  ⛔ NEVER leave the default Laravel welcome page as entry point
  ⛔ Users should see YOUR application, not "Let's get started"
  
  ✅ REQUIRED: Replace or redirect the '/' route in routes/web.php:
  
  Option 1 - Direct replacement (PREFERRED):
  {
    "type": "search_replace",
    "path": "routes/web.php",
    "search": "Route::get('/', function () {
    return view('welcome');
});",
    "replace": "Route::get('/', [ProductController::class, 'index']);"
  }
  
  Option 2 - Redirect to main feature:
  {
    "type": "search_replace",
    "path": "routes/web.php",
    "search": "Route::get('/', function () {
    return view('welcome');
});",
    "replace": "Route::redirect('/', '/products');"
  }
  
  📝 Examples:
  - Product listing app → Route::get('/', [ProductController::class, 'index']);
  - Dashboard app → Route::get('/', [DashboardController::class, 'index']);
  - Multi-feature → Route::redirect('/', '/main-feature');
  
  🎯 Goal: User visits http://localhost:8000 and sees YOUR app, not Laravel default

🗄️ DATABASE & SEEDERS (Laravel 12):
  📋 Default DatabaseSeeder.php content (Laravel 12):
  <?php
  namespace Database\Seeders;
  use Illuminate\Database\Seeder;
  
  class DatabaseSeeder extends Seeder {
      public function run(): void {
          // User::factory(10)->create();
          // User::factory()->create(['name' => 'Test User', 'email' => 'test@example.com']);
      }
  }
  
  ✅ To call custom seeders, use search_replace:
  {
    "type": "search_replace",
    "path": "database/seeders/DatabaseSeeder.php",
    "search": "    public function run(): void
    {
        // User::factory(10)->create();",
    "replace": "    public function run(): void
    {
        $this->call(CharacterSeeder::class);
        // User::factory(10)->create();"
  }
  
  ⚠️ CRITICAL: Match EXACT indentation (4 spaces in Laravel 12)
  ⚠️ Include enough context to make search unique
  ⚠️ Always check RAG context for actual file content before search_replace

✅ VALIDATION & SECURITY:
  - Always use FormRequest classes for complex validation
  - Include @csrf token in all forms
  - Use route model binding when appropriate
  - Implement authorization policies for sensitive actions

🧪 TESTING:
  - Write Pest tests for new features (Laravel 12 default)
  - Test controller actions, validation rules, database operations
  - Location: tests/Feature/ and tests/Unit/

📦 COMMON PATTERNS:
  - API responses: return response()->json($data)
  - Redirects with data: return redirect()->route('name')->with('status', 'Success!')
  - Flash messages: session()->flash('message', 'Saved successfully')
  - Validation: $request->validate(['field' => 'required|string|max:255'])
"""
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
        
        # 🔥 FIX CRITIQUE: Nettoyer les échappements littéraux AVANT parsing JSON
        text = self._fix_literal_escapes_in_raw_json(text)
        
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
                            # 🔥 NOUVEAU: Try auto-repair before failing
                            repaired_data = self._try_repair_json(original_text)
                            if repaired_data:
                                data = repaired_data
                                self.log.info(f"✅ JSON auto-repaired successfully!")
                            else:
                                raise ValueError(f"Could not parse JSON: {e}")
                    else:
                        self.log.error(f"❌ No JSON structure found in response")
                        self.log.error(f"First 200 chars: {original_text[:200]}")
                        # 🔥 NOUVEAU: Try auto-repair before failing
                        repaired_data = self._try_repair_json(original_text)
                        if repaired_data:
                            data = repaired_data
                            self.log.info(f"✅ JSON auto-repaired successfully!")
                        else:
                            raise ValueError(f"No valid JSON found in response: {e}")
            else:
                self.log.error(f"❌ No JSON braces found in response")
                # 🔥 NOUVEAU: Try auto-repair before failing
                repaired_data = self._try_repair_json(original_text)
                if repaired_data:
                    data = repaired_data
                    self.log.info(f"✅ JSON auto-repaired successfully!")
                else:
                    raise ValueError(f"No valid JSON found in response: {e}")
        
        # 🔥 NOUVEAU: Auto-repair if data is missing \"operations\" wrapper
        if isinstance(data, dict) and "operations" not in data:
            self.log.warning(f"⚠️ JSON missing 'operations' wrapper - attempting auto-repair")
            repaired_data = self._try_repair_missing_wrapper(data)
            if repaired_data:
                data = repaired_data
                self.log.info(f"✅ Auto-wrapped single operation into operations array")
        
        # 6. Validate with Pydantic
        try:
            validated = DeveloperOutput(**data)
            # Convert Pydantic models to dicts
            operations = [op.dict() for op in validated.operations]
            
            # 🔧 FIX CRITIQUE: Nettoyer les séquences d'échappement littérales dans le contenu
            operations = self._fix_literal_escapes(operations)
            
            self.log.info(f"✅ Validated {len(operations)} operations")
            return operations
        except ValidationError as e:
            self.log.error(f"❌ JSON validation failed: {e}")
            self.log.error(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            
            # 🔥 NOUVEAU: One last repair attempt for validation errors
            repaired_data = self._try_repair_validation_error(data, str(e))
            if repaired_data:
                try:
                    validated = DeveloperOutput(**repaired_data)
                    operations = [op.dict() for op in validated.operations]
                    operations = self._fix_literal_escapes(operations)
                    self.log.info(f"✅ Validated {len(operations)} operations after repair")
                    return operations
                except:
                    pass
            
            raise ValueError(f"JSON validation failed: {e}")
    
    def _try_repair_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        🔥 NOUVEAU: Tente de réparer automatiquement un JSON mal formé
        Inspiré d'Emergent.sh - Ne jamais bloquer le développement!
        
        Stratégies de réparation:
        1. Wrapper manquant {"operations": [...]}
        2. Virgules manquantes
        3. Quotes mal échappées
        4. Structure d'objet simple au lieu d'array
        """
        try:
            # Strategy 1: Le LLM a retourné juste un objet au lieu de {"operations": [...]}
            # Pattern: {"type": "create", "path": "...", ...}
            if '"type"' in text and '"operations"' not in text:
                self.log.info("🔧 Attempting repair: wrapping single operation")
                # Try to parse as single operation
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    try:
                        single_op = json.loads(text[start:end+1])
                        if isinstance(single_op, dict) and "type" in single_op:
                            # Wrap it
                            repaired = {"operations": [single_op]}
                            self.log.info(f"✅ Repaired: wrapped single operation of type '{single_op.get('type')}'")
                            return repaired
                    except:
                        pass
            
            # Strategy 2: Trailing comma avant }
            if text.endswith(",}") or text.endswith(", }"):
                self.log.info("🔧 Attempting repair: removing trailing comma")
                cleaned = text.replace(",}", "}").replace(", }", "}")
                try:
                    return json.loads(cleaned)
                except:
                    pass
            
            # Strategy 3: Missing closing braces
            open_braces = text.count("{")
            close_braces = text.count("}")
            if open_braces > close_braces:
                self.log.info(f"🔧 Attempting repair: adding {open_braces - close_braces} closing braces")
                repaired_text = text + ("}" * (open_braces - close_braces))
                try:
                    return json.loads(repaired_text)
                except:
                    pass
            
            return None
        except Exception as e:
            self.log.debug(f"JSON repair failed: {e}")
            return None
    
    def _try_repair_missing_wrapper(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        🔥 NOUVEAU: Répare un JSON qui manque le wrapper {"operations": [...]}
        
        Si le LLM retourne {"type": "create", ...} au lieu de {"operations": [{"type": "create", ...}]}
        """
        if not isinstance(data, dict):
            return None
        
        # Check if data looks like a single operation
        if "type" in data and "path" in data:
            self.log.info(f"🔧 Auto-wrapping: single operation of type '{data.get('type')}' detected")
            return {"operations": [data]}
        
        # Check if data is already correct format
        if "operations" in data:
            return data
        
        return None
    
    def _try_repair_validation_error(self, data: Dict[str, Any], error_msg: str) -> Optional[Dict[str, Any]]:
        """
        🔥 NOUVEAU: Répare des erreurs de validation Pydantic communes
        
        Exemples:
        - Champ requis manquant
        - Type incorrect
        - Structure incorrecte
        """
        if not isinstance(data, dict):
            return None
        
        try:
            # Si "operations" manque mais qu'il y a un "operation" (typo)
            if "operation" in data and "operations" not in data:
                self.log.info("🔧 Fixing typo: 'operation' → 'operations'")
                data["operations"] = data.pop("operation")
                # Ensure it's a list
                if not isinstance(data["operations"], list):
                    data["operations"] = [data["operations"]]
                return data
            
            # Si "operations" existe mais n'est pas une liste
            if "operations" in data and not isinstance(data["operations"], list):
                self.log.info("🔧 Converting operations to list")
                data["operations"] = [data["operations"]]
                return data
            
            # Si l'erreur dit "Field required" pour "operations"
            if "operations" in error_msg and "Field required" in error_msg:
                # Try to extract any operation-like structure
                for key in ["operation", "files", "changes"]:
                    if key in data:
                        self.log.info(f"🔧 Using '{key}' as operations")
                        ops = data[key] if isinstance(data[key], list) else [data[key]]
                        return {"operations": ops}
            
            return None
        except Exception as e:
            self.log.debug(f"Validation repair failed: {e}")
            return None
    
    def _fix_literal_escapes(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        🔧 FIX: Corrige les séquences d'échappement littérales dans le contenu
        
        Problème: Le LLM génère parfois du texte avec des \n littéraux au lieu de retours à la ligne
        Exemple: "use App\Http\Controllers\ProductController;\n"
        
        Cette fonction détecte et corrige ces cas.
        """
        fixed_operations = []
        
        for op in operations:
            op = op.copy()  # Ne pas modifier l'original
            
            # Nettoyer le champ "content" s'il existe
            if 'content' in op and isinstance(op['content'], str):
                content = op['content']
                
                # Détecter si le contenu a des \n littéraux (non interprétés)
                # Pattern: Si on voit \n mais pas de vrais retours à la ligne
                if '\\n' in content and '\n' not in content:
                    # C'est du \n littéral, remplacer par de vrais 
                    content = content.replace('\\n', '\n')
                    content = content.replace('\\t', '\t')
                    content = content.replace('\\n', '\n')
                    op['content'] = content
                    self.log.warning(f"⚠️ Fixed literal escape sequences in content for {op.get('path', 'unknown')}")
            
            # Nettoyer "search" et "replace" pour search_replace operations
            if 'search' in op and isinstance(op['search'], str):
                search = op['search']
                if '\\n' in search and '\n' not in search:
                    op['search'] = search.replace('\\n', '\n').replace('\\t', '\t')
                    self.log.warning(f"⚠️ Fixed literal escapes in search pattern")
            
            if 'replace' in op and isinstance(op['replace'], str):
                replace = op['replace']
                if '\\n' in replace and '\n' not in replace:
                    op['replace'] = replace.replace('\\n', '\n').replace('\\t', '\t')
                    self.log.warning(f"⚠️ Fixed literal escapes in replace pattern")
            
            fixed_operations.append(op)
        
        return fixed_operations
    
    
    def _fix_literal_escapes_in_raw_json(self, text: str) -> str:
        """
        🔥 FIX CRITIQUE: Nettoie les échappements littéraux AVANT parsing JSON
        
        Architecture multi-couches ITERATIVE inspirée d'Emergent.sh :
        - COUCHE 1: Nettoyage des triples+ échappements (\\\" → \", passes multiples)
        - COUCHE 2: Nettoyage des doubles+ échappements (\\n → \n, passes multiples)
        - COUCHE 3: Regex avancées pour cas complexes (système existant)
        
        NOUVEAU: Approche itérative pour gérer les échappements profonds (4, 5, 6+ backslashes)
        Le LLM peut générer \\\\n (4 backslashes) ou \\\\\\" (5 backslashes)
        
        Exemples résolus: 
        - "content": "Hello \\\\\\"World\\\\\\"" → "Hello \"World\""
        - "content": "Line1\\\\\\\\nLine2" → "Line1\nLine2"
        """
        if not text or not isinstance(text, str):
            return text
        
        import re
        original_text = text
        fixes_applied = []
        
        # ============================================================
        # COUCHE 1: Nettoyage ITÉRATIF des échappements de guillemets
        # ============================================================
        # Approche: Répéter jusqu'à stabilisation (max 5 passes)
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            text_before = text
            
            # Réduire les échappements multiples de guillemets
            # Pattern: \\\\" → \\" (réduit de 1 niveau à chaque passe)
            if '\\\\"' in text:
                text = text.replace('\\\\"', '\\"')
                if iteration == 0:
                    fixes_applied.append("quote-escaping-reduction")
            
            # Si pas de changement, on a terminé
            if text == text_before:
                break
            iteration += 1
        
        if iteration > 0:
            self.log.info(f"🔧 [Couche 1] Guillemets: {iteration} passes de nettoyage (\\\\\" → \\\")")
        
        # ============================================================
        # COUCHE 2: Nettoyage ITÉRATIF des échappements de newlines/tabs
        # ============================================================
        iteration = 0
        
        while iteration < max_iterations:
            text_before = text
            
            # Réduire les échappements multiples de \n
            # Pattern: \\\\n → \\n (réduit de 1 niveau à chaque passe)
            if '\\\\n' in text:
                text = text.replace('\\\\n', '\\n')
                if iteration == 0:
                    fixes_applied.append("newline-escaping-reduction")
            
            # Réduire les échappements multiples de \t
            if '\\\\t' in text:
                text = text.replace('\\\\t', '\\t')
                if iteration == 0:
                    fixes_applied.append("tab-escaping-reduction")
            
            # Si pas de changement, on a terminé
            if text == text_before:
                break
            iteration += 1
        
        if iteration > 0:
            self.log.info(f"🔧 [Couche 2] Newlines/Tabs: {iteration} passes de nettoyage (\\\\\\\\n → \\\\n → \\n)")
        
        # ============================================================
        # COUCHE 2.5: Normalisation FINALE des quotes dans attributs HTML/XML
        # ============================================================
        # Problème: Après nettoyage itératif, il peut rester \\" dans du HTML
        # Exemple: charset=\\"UTF-8\\" doit devenir charset=\"UTF-8\"
        # Pattern: = suivi de \\" dans du contenu HTML/XML
        if '=\\\\"' in text or '=\\"' in text:
            # Normaliser les attributs HTML: attr=\\"value\\" → attr=\"value\"
            text = re.sub(r'=\\\\"([^"]*)\\\\"', r'=\"\1\"', text)
            text = re.sub(r'=\\"([^"]*)\\"', r'=\"\1\"', text)
            fixes_applied.append("html-attribute-normalization")
            self.log.info("🔧 [Couche 2.5] Normalisation quotes attributs HTML (attr=\\\\\"val\\\\\" → attr=\"val\")")
        
        # ============================================================
        # COUCHE 3: Regex avancées pour cas complexes (système existant)
        # ============================================================
        # Chercher les patterns JSON avec des échappements littéraux dans les champs spécifiques
        # Pattern: "field": "value with \\n literal"
        pattern = r'("(?:content|search|replace)"\s*:\s*"[^"]*?)\\\\n([^"]*")'
        
        def fix_escapes(match):
            prefix = match.group(1)  # "content": "text before
            suffix = match.group(2)  # text after"
            # Remplacer \\n par \n (vrai retour à la ligne)
            return prefix + '\n' + suffix
        
        # Appliquer la correction regex pour \n
        text_after_regex = re.sub(pattern, fix_escapes, text)
        if text_after_regex != text:
            fixes_applied.append("regex newlines in fields")
            text = text_after_regex
        
        # Aussi corriger \\t avec regex
        pattern_tab = r'("(?:content|search|replace)"\s*:\s*"[^"]*?)\\\\t([^"]*")'
        def fix_tabs(match):
            prefix = match.group(1)
            suffix = match.group(2)
            return prefix + '\t' + suffix
        
        text_after_tab_regex = re.sub(pattern_tab, fix_tabs, text)
        if text_after_tab_regex != text:
            fixes_applied.append("regex tabs in fields")
            text = text_after_tab_regex
        
        # Log final si corrections appliquées
        if text != original_text:
            self.log.info(f"🔧 [Multi-couches] Nettoyage JSON terminé: {', '.join(fixes_applied)}")
        
        return text
    def _normalize_operations(
        self,
        operations: List[Dict[str, Any]],
        project_path: Optional[str],
        stack: str
    ) -> List[Dict[str, Any]]:
        """
        🛡️ NORMALISATION INTELLIGENTE DES OPÉRATIONS (DÉFENSE NIVEAU 2)
        
        Applique des transformations intelligentes pour éviter les erreurs communes:
        1. Détecte les doublons (2 create sur même path) → garde le premier
        2. Détecte create sur fichier existant → convertit en update
        3. Log toutes les conversions pour feedback
        
        Cette normalisation rend le système plus robuste face à des plans imparfaits.
        
        Args:
            operations: Liste d'opérations validées par Pydantic
            project_path: Chemin du projet (pour vérifier existence fichiers)
            stack: Stack du projet
            
        Returns:
            Liste d'opérations normalisées
        """
        if not operations:
            return operations
            
        normalized = []
        seen_paths = {}  # path → (op_type, index) pour détecter doublons
        conversions_log = []
        
        for i, op in enumerate(operations):
            op_type = op.get("type")
            path = op.get("path")
            
            # Skip operations sans path (rename a old_path/new_path)
            if not path and op_type != "rename":
                normalized.append(op)
                continue
            
            # 1️⃣ Détecter doublons de 'create' sur même path
            if op_type == "create" and path in seen_paths:
                prev_type, prev_idx = seen_paths[path]
                if prev_type == "create":
                    self.log.warning(
                        f"🔄 Duplicate create detected for '{path}' (operations {prev_idx} and {i}). "
                        f"Keeping first, skipping second."
                    )
                    conversions_log.append(f"Skipped duplicate create: {path} (kept op#{prev_idx}, skipped op#{i})")
                    continue  # Skip cette opération
            
            # 2️⃣ Convertir 'create' en 'update' si fichier existe déjà
            if op_type == "create" and project_path:
                target_file = Path(project_path) / path
                if target_file.exists():
                    self.log.warning(
                        f"🔄 Auto-converted create→update (file exists): {path}"
                    )
                    op = {**op, "type": "update"}
                    conversions_log.append(f"create→update: {path} (file existed)")
            
            # Enregistrer ce path pour détecter futurs doublons
            if path:
                seen_paths[path] = (op.get("type"), i)
            
            normalized.append(op)
        
        # Log résumé des conversions
        if conversions_log:
            self.log.info(f"📝 Normalization summary: {len(conversions_log)} conversions")
            for log_entry in conversions_log:
                self.log.info(f"  - {log_entry}")
        else:
            self.log.debug("✅ No normalizations needed - operations are already coherent")
        
        return normalized
    
    def _validate_laravel_coherence(self, operations: List[Dict[str, Any]], stack: str) -> List[str]:
        """
        🔥 Validate Laravel-specific coherence rules
        Returns list of warning messages (non-blocking, for logging)
        """
        if stack != "laravel":
            return []
        
        warnings = []
        
        # Extract files being created/modified
        controller_files = []
        route_files = []
        view_files = []
        
        for op in operations:
            path = op.get('path', '')
            op_type = op.get('type', '')
            
            if 'app/Http/Controllers/' in path:
                controller_files.append(path)
            elif 'routes/' in path:
                route_files.append(path)
            elif 'resources/views/' in path:
                view_files.append(path)
        
        # Check routes for controller references
        import re
        for route_op in [op for op in operations if 'routes/' in op.get('path', '')]:
            content = route_op.get('content', '')
            
            # Find controller class references: SomeController::class
            controller_refs = re.findall(r'([A-Z][a-zA-Z0-9]*Controller)::class', content)
            
            for controller_name in controller_refs:
                # Check if this controller is being created in the operations
                expected_path = f"app/Http/Controllers/{controller_name}.php"
                
                # Also check for namespaced controllers (e.g., Admin\ProductController)
                namespace_refs = re.findall(rf'([A-Za-z0-9\\]+{controller_name})::class', content)
                
                found = False
                for ctrl_file in controller_files:
                    if controller_name in ctrl_file:
                        found = True
                        break
                
                if not found:
                    warnings.append(
                        f"⚠️ Route references '{controller_name}' but controller file not created in this step. "
                        f"Expected file: {expected_path}"
                    )
        
        # Check for asset() usage with css/js (should use @vite instead)
        for view_op in [op for op in operations if 'resources/views/' in op.get('path', '')]:
            content = view_op.get('content', '')
            
            # Check for old asset() pattern
            if "{{ asset('css/" in content or '{{ asset("css/' in content:
                warnings.append(
                    f"⚠️ View '{view_op.get('path')}' uses {{ asset('css/...') }} which may not work with Vite. "
                    f"Consider using @vite(['resources/css/app.css']) instead."
                )
            
            if "{{ asset('js/" in content or '{{ asset("js/' in content:
                warnings.append(
                    f"⚠️ View '{view_op.get('path')}' uses {{ asset('js/...') }} which may not work with Vite. "
                    f"Consider using @vite(['resources/js/app.js']) instead."
                )

                        # 🚨 CHECK: Verify that default '/' route is being replaced/redirected
        # This is CRITICAL - users should see the app, not Laravel welcome page
        for route_op in [op for op in operations if 'routes/web.php' in op.get('path', '')]:
            content = route_op.get('content', '') or ''
            replace = route_op.get('replace', '') or ''
            search = route_op.get('search', '') or ''
            
            # Check if operations modify the default welcome route
            modifies_root_route = (
                "view('welcome')" in search or  # search_replace that touches welcome
                "return view('welcome')" in content or  # Direct content modification
                "Route::get('/'," in replace or  # Replacing root route
                "Route::redirect('/'," in replace  # Redirecting root route
            )
            
            # If creating routes but NOT modifying '/', warn
            if not modifies_root_route and ('Route::' in content or 'Route::' in replace):
                # Check if there are multiple routes being created
                route_count = content.count('Route::') + replace.count('Route::')
                if route_count > 0:
                    warnings.append(
                        f"🚨 CRITICAL: Creating routes but NOT modifying '/' (root route). "
                        f"Users will see Laravel welcome page instead of your app! "
                        f"Add a search_replace operation to change the default route."
                    )
        
        return warnings

