"""
Validateur CRUD - Force la génération complète

Ce module valide que TOUS les fichiers nécessaires pour un CRUD
sont générés, sinon REJETTE la réponse du LLM.

Philosophie Emergent.sh : "TOUT OU RIEN"
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging


@dataclass
class CRUDValidationResult:
    """Résultat de la validation CRUD"""
    is_complete: bool
    missing_files: List[str]
    warnings: List[str]
    operations_count: int


class CRUDValidator:
    """
    Validateur de génération CRUD complète
    
    Force le LLM à générer TOUS les fichiers nécessaires
    en une seule fois, selon la philosophie Emergent.sh.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def validate_laravel_crud(
        self, 
        operations: List[Dict[str, Any]],
        step_description: str
    ) -> CRUDValidationResult:
        """
        Valide qu'un CRUD Laravel complet est généré.
        
        Args:
            operations: Liste des opérations générées
            step_description: Description du step (pour détecter si c'est un CRUD)
        
        Returns:
            CRUDValidationResult avec les fichiers manquants
        """
        # Détecter si c'est un step CRUD
        is_crud_step = self._is_crud_step(step_description)
        
        if not is_crud_step:
            # Pas un CRUD, validation basique
            return CRUDValidationResult(
                is_complete=True,
                missing_files=[],
                warnings=[],
                operations_count=len(operations)
            )
        
        # C'est un CRUD, validation stricte
        required_patterns = {
            'migration': 'database/migrations/*_create_*_table.php',
            'model': 'app/Models/*.php',
            'controller': 'app/Http/Controllers/*Controller.php',
            'routes': 'routes/web.php',
            'layout': 'resources/views/layouts/app.blade.php',
            'view_index': 'resources/views/*/index.blade.php',
            'view_create': 'resources/views/*/create.blade.php',
            'view_edit': 'resources/views/*/edit.blade.php',
            'view_show': 'resources/views/*/show.blade.php',
        }
        
        missing_files = []
        found_files = {}
        warnings = []
        
        # Vérifier chaque fichier obligatoire
        for file_type, pattern in required_patterns.items():
            found = self._find_matching_operation(operations, pattern)
            if found:
                found_files[file_type] = found['path']
            else:
                missing_files.append(f"{file_type} ({pattern})")
        
        # Vérifier le Controller (doit avoir 7 méthodes)
        if 'controller' in found_files:
            controller_op = next(
                (op for op in operations if 'Controller.php' in op.get('path', '')),
                None
            )
            if controller_op:
                content = controller_op.get('content', '')
                methods = ['index', 'create', 'store', 'show', 'edit', 'update', 'destroy']
                missing_methods = [m for m in methods if f'function {m}(' not in content]
                
                if missing_methods:
                    warnings.append(
                        f"⚠️ Controller missing methods: {', '.join(missing_methods)}"
                    )
        
        # Résultat
        is_complete = len(missing_files) == 0
        
        if not is_complete:
            self.logger.error(
                f"❌ CRUD VALIDATION FAILED: {len(missing_files)}/9 files missing"
            )
            for missing in missing_files:
                self.logger.error(f"   • Missing: {missing}")
        else:
            self.logger.info(f"✅ CRUD VALIDATION PASSED: All 9 files generated")
        
        return CRUDValidationResult(
            is_complete=is_complete,
            missing_files=missing_files,
            warnings=warnings,
            operations_count=len(operations)
        )
    
    def _is_crud_step(self, description: str) -> bool:
        """
        Détecte si un step est une création de CRUD.
        
        Keywords: CRUD, management, gestion, create/update/delete, etc.
        """
        description_lower = description.lower()
        
        crud_keywords = [
            'crud',
            'management',
            'gestion',
            'create',
            'update',
            'delete',
            'edit',
            'list',
            'resource',
            'model',
            'controller',
        ]
        
        # Si au moins 2 keywords présents, c'est probablement un CRUD
        matches = sum(1 for keyword in crud_keywords if keyword in description_lower)
        
        return matches >= 2
    
    def _find_matching_operation(
        self, 
        operations: List[Dict[str, Any]], 
        pattern: str
    ) -> Optional[Dict[str, Any]]:
        """
        Trouve une opération qui matche un pattern de chemin.
        
        Supporte wildcards * dans les patterns.
        """
        import fnmatch
        
        for op in operations:
            path = op.get('path', '')
            if fnmatch.fnmatch(path, pattern):
                return op
        
        return None
    
    def generate_missing_operations_prompt(
        self, 
        missing_files: List[str],
        original_operations: List[Dict[str, Any]]
    ) -> str:
        """
        Génère un prompt pour demander les fichiers manquants au LLM.
        
        Args:
            missing_files: Liste des fichiers manquants
            original_operations: Opérations déjà générées
        
        Returns:
            Prompt formaté pour compléter le CRUD
        """
        existing_files = [op.get('path', '') for op in original_operations]
        
        return f"""
🚨 CRUD INCOMPLETE - GENERATION REQUIRED

You generated {len(original_operations)} file(s), but a complete CRUD requires 9 files.

✅ Already generated:
{chr(10).join(f'  • {f}' for f in existing_files)}

❌ Still missing ({len(missing_files)} files):
{chr(10).join(f'  • {f}' for f in missing_files)}

🔥 CRITICAL INSTRUCTION:
You MUST now generate the MISSING files ONLY.
Return a JSON with operations for the missing files.

DO NOT regenerate files that already exist.
DO NOT return explanations.
ONLY return valid JSON with operations for missing files.

Required JSON format:
{{
  "operations": [
    {{"type": "create", "path": "...", "content": "..."}}
  ]
}}
"""


def validate_and_complete_crud(
    operations: List[Dict[str, Any]],
    step_description: str,
    llm_callback: callable,
    max_retries: int = 2,
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Valide un CRUD et complète automatiquement si incomplet.
    
    Wrapper utilitaire qui :
    1. Valide le CRUD
    2. Si incomplet, demande au LLM les fichiers manquants
    3. Retourne la liste complète d'opérations
    
    Args:
        operations: Opérations initiales générées
        step_description: Description du step
        llm_callback: Fonction pour appeler le LLM (signature: prompt → operations)
        max_retries: Nombre max de tentatives de complétion
        logger: Logger optionnel
    
    Returns:
        Liste complète d'opérations (initiales + complétées)
    """
    validator = CRUDValidator(logger=logger)
    
    # Validation initiale
    result = validator.validate_laravel_crud(operations, step_description)
    
    if result.is_complete:
        if logger:
            logger.info("✅ CRUD already complete, no completion needed")
        return operations
    
    # CRUD incomplet, tentatives de complétion
    if logger:
        logger.warning(
            f"⚠️ CRUD incomplete: {len(result.missing_files)} files missing, "
            f"attempting auto-completion ({max_retries} retries max)"
        )
    
    all_operations = operations.copy()
    
    for attempt in range(1, max_retries + 1):
        # Générer prompt pour fichiers manquants
        completion_prompt = validator.generate_missing_operations_prompt(
            result.missing_files,
            all_operations
        )
        
        try:
            # Appeler le LLM pour compléter
            additional_ops = llm_callback(completion_prompt)
            
            if additional_ops:
                if logger:
                    logger.info(
                        f"✅ Completion attempt {attempt}/{max_retries}: "
                        f"generated {len(additional_ops)} additional operations"
                    )
                
                all_operations.extend(additional_ops)
                
                # Re-valider
                result = validator.validate_laravel_crud(all_operations, step_description)
                
                if result.is_complete:
                    if logger:
                        logger.info(
                            f"🎉 CRUD completed successfully after {attempt} attempt(s)"
                        )
                    return all_operations
            else:
                if logger:
                    logger.warning(
                        f"⚠️ Completion attempt {attempt}/{max_retries}: "
                        f"LLM returned no operations"
                    )
        
        except Exception as e:
            if logger:
                logger.error(
                    f"❌ Completion attempt {attempt}/{max_retries} failed: {e}"
                )
    
    # Échec après max_retries
    if logger:
        logger.error(
            f"❌ CRUD completion failed after {max_retries} attempts. "
            f"Still missing {len(result.missing_files)} files."
        )
    
    return all_operations
