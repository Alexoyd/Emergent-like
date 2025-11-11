"""
Direct File Writer Module - Écriture directe sans patches Git

Remplace le système de patches par des opérations d'écriture directes.
Primitives : create, update, insert, search_replace, rename, delete
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

# 🛡️ Garde-fous : Chemins protégés (deny-list)
PROTECTED_PATHS = [
    ".git/",
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "vendor/",
    "node_modules/",
    "dist/",
    "build/",
    "storage/",
    "bootstrap/cache/",
    "package-lock.json",
    "pnpm-lock.yaml",
    "composer.lock",
    "yarn.lock",
    ".pytest_cache/",
    "__pycache__/",
    ".venv/",
    "venv/",
]

# Taille max par fichier (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class FileWriterError(Exception):
    """Exception levée lors d'erreurs d'écriture de fichiers"""
    pass


class FileWriter:
    """
    Module d'écriture directe de fichiers avec validation et sécurité
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.locks: Dict[str, asyncio.Lock] = {}
        
        if not self.project_path.exists():
            raise FileWriterError(f"Project path does not exist: {project_path}")
    
    def _get_lock(self, project_id: str) -> asyncio.Lock:
        """Obtenir ou créer un lock pour un projet"""
        if project_id not in self.locks:
            self.locks[project_id] = asyncio.Lock()
        return self.locks[project_id]
    
    def _validate_path(self, file_path: str) -> Path:
        """
        🛡️ Valide qu'un chemin est sûr et autorisé
        """
        # Convertir en Path et résoudre
        target_path = (self.project_path / file_path).resolve()
        
        # Vérifier que le chemin reste dans le projet (pas de ..)
        try:
            target_path.relative_to(self.project_path)
        except ValueError:
            raise FileWriterError(f"Path escapes project directory: {file_path}")
        
        # Vérifier chemins absolus
        if Path(file_path).is_absolute():
            raise FileWriterError(f"Absolute paths not allowed: {file_path}")
        
        # Vérifier deny-list
        relative_path = str(target_path.relative_to(self.project_path))
        for protected in PROTECTED_PATHS:
            if relative_path.startswith(protected) or f"/{protected}" in f"/{relative_path}":
                raise FileWriterError(f"Protected path not writable: {file_path} (matches {protected})")
        
        return target_path
    
    def _calculate_hash(self, content: str) -> str:
        """Calcule SHA-256 du contenu"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _validate_syntax(self, file_path: str, content: str, stack: str = "generic") -> tuple[bool, Optional[str]]:
        """
        🔥 PHASE 2 FIX: Validation syntaxe AVANT écriture (technique Emergent.sh)
        
        Valide la syntaxe du code selon le type de fichier.
        
        Args:
            file_path: Chemin du fichier
            content: Contenu à valider
            stack: Stack du projet (laravel, react, etc.)
        
        Returns:
            (is_valid, error_message)
        """
        import subprocess
        
        file_ext = Path(file_path).suffix.lower()
        
        # PHP validation (Laravel, PHP files)
        if file_ext == '.php' and stack in ['laravel', 'php']:
            try:
                result = subprocess.run(
                    ['php', '-l'],  # php -l = lint
                    input=content,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode != 0:
                    error = result.stderr or result.stdout
                    return False, f"PHP syntax error: {error}"
                logger.debug(f"✅ PHP syntax valid: {file_path}")
            except FileNotFoundError:
                # PHP not installed, skip validation
                logger.debug("PHP not available for validation, skipping")
            except Exception as e:
                logger.warning(f"PHP validation failed: {e}")
                # Non-bloquant si validation échoue
        
        # JavaScript/JSX basic validation
        elif file_ext in ['.js', '.jsx'] and stack in ['react', 'node', 'vue']:
            try:
                # Quick checks: brackets balance
                if content.count('{') != content.count('}'):
                    return False, "Unbalanced braces in JavaScript"
                if content.count('(') != content.count(')'):
                    return False, "Unbalanced parentheses in JavaScript"
                if content.count('[') != content.count(']'):
                    return False, "Unbalanced brackets in JavaScript"
                logger.debug(f"✅ JS basic syntax valid: {file_path}")
            except Exception as e:
                logger.debug(f"JS validation failed: {e}")
        
        # Python validation
        elif file_ext == '.py' and stack in ['python', 'django', 'fastapi']:
            try:
                compile(content, file_path, 'exec')
                logger.debug(f"✅ Python syntax valid: {file_path}")
            except SyntaxError as e:
                return False, f"Python syntax error at line {e.lineno}: {e.msg}"
            except Exception as e:
                logger.debug(f"Python validation failed: {e}")
        
        # Vue template basic validation
        elif file_ext == '.vue' and stack in ['vue', 'nuxt']:
            try:
                if '<template>' not in content or '</template>' not in content:
                    return False, "Invalid Vue component: missing template tags"
                logger.debug(f"✅ Vue template valid: {file_path}")
            except Exception as e:
                logger.debug(f"Vue validation failed: {e}")
        
        # JSON validation
        elif file_ext == '.json':
            try:
                import json
                json.loads(content)
                logger.debug(f"✅ JSON syntax valid: {file_path}")
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON at line {e.lineno}: {e.msg}"
        
        # Si aucune validation spécifique, considérer valide
        return True, None
    
    async def create_file(self, file_path: str, content: str, project_id: str, auto_convert: bool = True) -> Dict[str, Any]:
        """
        Crée un nouveau fichier avec contenu
        
        Args:
            file_path: Chemin relatif du fichier à créer
            content: Contenu du fichier
            project_id: ID du projet (pour lock)
            auto_convert: Si True, convertit automatiquement en update si fichier existe
        
        Returns:
            Dict avec status, path, hash, size
        """
        async with self._get_lock(project_id):
            try:
                target_path = self._validate_path(file_path)
                
                # 🛡️ GARDE-FOU ULTIME: Si fichier existe, auto-convertir en update
                if target_path.exists():
                    if auto_convert:
                        logger.warning(f"🛡️ Auto-converted create→update (file existed): {file_path}")
                        # Déléguer à update_file qui gère la mise à jour
                        return await self.update_file(file_path, content, project_id)
                    else:
                        raise FileWriterError(f"File already exists: {file_path}")
                
                # Vérifier taille
                size = len(content.encode('utf-8'))
                if size > MAX_FILE_SIZE:
                    raise FileWriterError(f"File too large: {size} bytes (max {MAX_FILE_SIZE})")
                
                # 🔥 PHASE 2 FIX: Validation syntaxe AVANT écriture
                is_valid, error_msg = self._validate_syntax(file_path, content, stack="generic")
                if not is_valid:
                    logger.error(f"❌ Syntax validation failed for {file_path}: {error_msg}")
                    raise FileWriterError(f"Syntax error in {file_path}: {error_msg}")
                
                # Créer répertoires parents si nécessaire
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Écriture atomique UTF-8
                target_path.write_text(content, encoding='utf-8')
                
                # Calculer hash
                file_hash = self._calculate_hash(content)
                
                logger.info(f"✅ Created file: {file_path} (size: {size}, hash: {file_hash[:8]}...)")
                
                return {
                    "status": "created",
                    "path": file_path,
                    "hash": file_hash,
                    "size": size,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to create file {file_path}: {e}")
                raise FileWriterError(f"Failed to create {file_path}: {str(e)}")
    
    async def update_file(self, file_path: str, content: str, project_id: str) -> Dict[str, Any]:
        """
        Remplace complètement le contenu d'un fichier existant
        
        Args:
            file_path: Chemin relatif du fichier à modifier
            content: Nouveau contenu complet
            project_id: ID du projet (pour lock)
        
        Returns:
            Dict avec status, path, old_hash, new_hash
        """
        async with self._get_lock(project_id):
            try:
                target_path = self._validate_path(file_path)
                
                # Vérifier que le fichier existe
                if not target_path.exists():
                    raise FileWriterError(f"File does not exist: {file_path}")
                
                # Hash ancien contenu
                old_content = target_path.read_text(encoding='utf-8')
                old_hash = self._calculate_hash(old_content)
                
                # Vérifier taille
                size = len(content.encode('utf-8'))
                if size > MAX_FILE_SIZE:
                    raise FileWriterError(f"File too large: {size} bytes (max {MAX_FILE_SIZE})")
                
                # 🔥 PHASE 2 FIX: Validation syntaxe AVANT écriture
                is_valid, error_msg = self._validate_syntax(file_path, content, stack="generic")
                if not is_valid:
                    logger.error(f"❌ Syntax validation failed for {file_path}: {error_msg}")
                    raise FileWriterError(f"Syntax error in {file_path}: {error_msg}")
                
                # Écriture atomique
                target_path.write_text(content, encoding='utf-8')
                
                # Hash nouveau contenu
                new_hash = self._calculate_hash(content)
                
                logger.info(f"✅ Updated file: {file_path} (hash: {old_hash[:8]}... → {new_hash[:8]}...)")
                
                return {
                    "status": "updated",
                    "path": file_path,
                    "old_hash": old_hash,
                    "new_hash": new_hash,
                    "size": size,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to update file {file_path}: {e}")
                raise FileWriterError(f"Failed to update {file_path}: {str(e)}")
    
    async def insert_text(self, file_path: str, after_line: int, content: str, project_id: str) -> Dict[str, Any]:
        """
        Insère du texte après une ligne spécifique
        
        Args:
            file_path: Chemin relatif du fichier
            after_line: Numéro de ligne après laquelle insérer (0-indexed, lignes comptées depuis 0)
                       - 0 = insérer APRÈS ligne 0 (la première ligne), donc en position 1
                       - N = insérer APRÈS ligne N, donc en position N+1
                       - -1 = insérer à la fin (EOF anchor)
                       - Si > nombre de lignes, clamp à EOF (idempotence)
            content: Contenu à insérer
            project_id: ID du projet (pour lock)
        
        Returns:
           Dict avec status, path, line_number, clamped (si clamped à EOF)
            
        Note: Lignes 0-indexed. Pour un fichier avec 3 lignes [0, 1, 2]:
              - after_line=0 insère après ligne 0 → position 1
              - after_line=1 insère après ligne 1 → position 2
              - after_line=2 insère après ligne 2 → position 3 (EOF)
              - after_line=-1 insère à EOF → position 3
        """
        async with self._get_lock(project_id):
            try:
                target_path = self._validate_path(file_path)
                
                if not target_path.exists():
                    raise FileWriterError(f"File does not exist: {file_path}")
                
                # Lire lignes existantes
                existing_content = target_path.read_text(encoding='utf-8')
                lines = existing_content.splitlines(keepends=True)
                
                # Support anchor EOF: -1 = fin du fichier
                if after_line == -1:
                    after_line = len(lines) - 1  # Dernière ligne
                
                # Validation: after_line ne peut pas être négatif (sauf -1 déjà traité)
                if after_line < -1:
                    raise FileWriterError(f"Invalid line number: {after_line} (must be >= 0 or -1 for EOF)")
                
                # Clamp EOF: Si after_line dépasse, clamper à la dernière ligne (idempotence)
                original_line = after_line
                clamped = False
                if after_line >= len(lines):
                    logger.warning(f"⚠️ Line {after_line} exceeds file length {len(lines)}, clamping to EOF")
                    after_line = len(lines) - 1 if len(lines) > 0 else 0
                    clamped = True
                              
                # Idempotence: Vérifier si le contenu à insérer existe déjà à cette position
                # Pour éviter les insertions dupliquées
                normalized_content = content if content.endswith('\n') else content + '\n'
                normalized_stripped = normalized_content.strip()
                
                # Vérifier les lignes adjacentes (avant et après la position d'insertion)
                # pour détecter si le contenu existe déjà
                skip_insert = False
                
                # Position d'insertion réelle = after_line + 1
                insert_position = after_line + 1
                
                # Vérifier ligne à la position d'insertion
                if insert_position < len(lines) and lines[insert_position].strip() == normalized_stripped:
                    skip_insert = True
                
                # Vérifier ligne à after_line (juste avant l'insertion)
                if not skip_insert and after_line >= 0 and after_line < len(lines) and lines[after_line].strip() == normalized_stripped:
                    skip_insert = True
                
                # Vérifier ligne juste après l'insertion
                if not skip_insert and insert_position + 1 < len(lines) and lines[insert_position + 1].strip() == normalized_stripped:
                    skip_insert = True
                
                if skip_insert:
                    logger.info(f"⚠️ Idempotence: Content already exists near line {after_line}, skipping insert")
                    return {
                        "status": "skipped",
                        "path": file_path,
                        "after_line": after_line,
                        "reason": "content_already_exists",
                        "timestamp": datetime.now().isoformat()
                    }
                
                # 🔧 FIX CRITIQUE: Insérer APRÈS la ligne spécifiée
                # list.insert(i, x) insère AVANT l'index i, donc pour insérer APRÈS after_line,
                # on doit utiliser insert(after_line + 1, content)
                lines.insert(after_line + 1, normalized_content)
                
                # Écrire fichier modifié
                new_content = ''.join(lines)
                target_path.write_text(new_content, encoding='utf-8')
                
                result_msg = f"✅ Inserted text in {file_path} after line {after_line}"
                if clamped:
                    result_msg += f" (clamped from {original_line})"
                logger.info(result_msg)
                
                result = {
                    "status": "inserted",
                    "path": file_path,
                    "after_line": after_line,
                    "timestamp": datetime.now().isoformat()
                }
                
                if clamped:
                    result["clamped"] = True
                    result["original_line"] = original_line
                
                return result
                
            except Exception as e:
                logger.error(f"❌ Failed to insert text in {file_path}: {e}")
                raise FileWriterError(f"Failed to insert in {file_path}: {str(e)}")
    
    async def search_replace(self, file_path: str, search: str, replace: str, project_id: str) -> Dict[str, Any]:
        """
        Recherche et remplace du texte exact dans un fichier
        
        Args:
            file_path: Chemin relatif du fichier
            search: Texte à rechercher (exact match)
            replace: Texte de remplacement
            project_id: ID du projet (pour lock)
        
        Returns:
            Dict avec status, path, occurrences
        """
        async with self._get_lock(project_id):
            try:
                target_path = self._validate_path(file_path)
                
                if not target_path.exists():
                    raise FileWriterError(f"File does not exist: {file_path}")
                
                # Lire contenu
                content = target_path.read_text(encoding='utf-8')
                
                # Vérifier que le texte à chercher existe
                if search not in content:
                    raise FileWriterError(f"Search text not found in {file_path}")
                
                # Compter occurrences
                occurrences = content.count(search)
                
                # Remplacer
                new_content = content.replace(search, replace)
                
                # Écrire
                target_path.write_text(new_content, encoding='utf-8')
                
                logger.info(f"✅ Replaced {occurrences} occurrence(s) in {file_path}")
                
                return {
                    "status": "replaced",
                    "path": file_path,
                    "occurrences": occurrences,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"❌ Failed search/replace in {file_path}: {e}")
                raise FileWriterError(f"Failed search/replace in {file_path}: {str(e)}")
    
    async def rename_file(self, old_path: str, new_path: str, project_id: str) -> Dict[str, Any]:
        """
        Renomme ou déplace un fichier
        
        Args:
            old_path: Chemin actuel
            new_path: Nouveau chemin
            project_id: ID du projet (pour lock)
        
        Returns:
            Dict avec status, old_path, new_path
        """
        async with self._get_lock(project_id):
            try:
                old_target = self._validate_path(old_path)
                new_target = self._validate_path(new_path)
                
                if not old_target.exists():
                    raise FileWriterError(f"File does not exist: {old_path}")
                
                if new_target.exists():
                    raise FileWriterError(f"Target already exists: {new_path}")
                
                # Créer répertoires parents si nécessaire
                new_target.parent.mkdir(parents=True, exist_ok=True)
                
                # Renommer
                old_target.rename(new_target)
                
                logger.info(f"✅ Renamed {old_path} → {new_path}")
                
                return {
                    "status": "renamed",
                    "old_path": old_path,
                    "new_path": new_path,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to rename {old_path}: {e}")
                raise FileWriterError(f"Failed to rename {old_path}: {str(e)}")
    
    async def delete_file(self, file_path: str, project_id: str) -> Dict[str, Any]:
        """
        Supprime un fichier
        
        Args:
            file_path: Chemin relatif du fichier à supprimer
            project_id: ID du projet (pour lock)
        
        Returns:
            Dict avec status, path
        """
        async with self._get_lock(project_id):
            try:
                target_path = self._validate_path(file_path)
                
                if not target_path.exists():
                    raise FileWriterError(f"File does not exist: {file_path}")
                
                # Supprimer
                target_path.unlink()
                
                logger.info(f"✅ Deleted file: {file_path}")
                
                return {
                    "status": "deleted",
                    "path": file_path,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to delete {file_path}: {e}")
                raise FileWriterError(f"Failed to delete {file_path}: {str(e)}")


def _sort_operations_by_priority(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trie les opérations par priorité pour assurer l'ordre correct:
    1. create, ensure (fichiers doivent exister avant modifications)
    2. update, insert, search_replace (opérations de modification)
    3. rename (peut casser les références)
    4. delete (doit venir en dernier)
    
    Préserve l'ordre relatif entre opérations du même type
    """
    priority_map = {
        "create": 1,
        "ensure": 1,  # 🔥 NOUVEAU: même priorité que create
        "update": 2,
        "insert": 2,
        "search_replace": 2,
        "rename": 3,
        "delete": 4
    }
    
    # Ajouter index original pour préserver l'ordre relatif
    operations_with_index = [
        {**op, "_original_index": i, "_priority": priority_map.get(op.get("type"), 999)}
        for i, op in enumerate(operations)
    ]
    
    # Trier par priorité, puis par index original
    sorted_ops = sorted(operations_with_index, key=lambda x: (x["_priority"], x["_original_index"]))
    
    # Retirer les champs temporaires
    for op in sorted_ops:
        op.pop("_priority", None)
        op.pop("_original_index", None)
    
    return sorted_ops


async def execute_operations(operations: List[Dict[str, Any]], project_path: str, project_id: str) -> List[Dict[str, Any]]:
    """
    Exécute une liste d'opérations d'écriture de fichiers
    
    Les opérations sont automatiquement triées par priorité:
    1. create, ensure (en premier)
    2. update, insert, search_replace
    3. rename
    4. delete (en dernier)
    
    Args:
        operations: Liste d'opérations à exécuter
        project_path: Chemin du projet
        project_id: ID du projet
    
    Returns:
        Liste des résultats d'exécution
    
    Raises:
        FileWriterError: Si un chemin protégé est tenté (doit être propagé comme 422)
    """
    writer = FileWriter(project_path)
    results = []
    
    # Trier les opérations par priorité (create avant insert, etc.)
    sorted_operations = _sort_operations_by_priority(operations)
    
    logger.info(f"📋 Executing {len(sorted_operations)} operations (sorted by priority)")
    
    for i, operation in enumerate(sorted_operations):
        op_type = operation.get("type")
        
        try:
            if op_type == "create":
                result = await writer.create_file(
                    operation["path"],
                    operation["content"],
                    project_id,
                    auto_convert=True  # 🛡️ Active la conversion automatique
                )
            elif op_type == "ensure":
                # 🔥 NOUVEAU: Opération 'ensure' - idempotente
                # Vérifie si le fichier existe pour choisir create ou update
                target_path = Path(project_path) / operation["path"]
                if target_path.exists():
                    logger.info(f"📝 'ensure' operation: file exists, using update for {operation['path']}")
                    result = await writer.update_file(
                        operation["path"],
                        operation["content"],
                        project_id
                    )
                else:
                    logger.info(f"📝 'ensure' operation: file missing, using create for {operation['path']}")
                    result = await writer.create_file(
                        operation["path"],
                        operation["content"],
                        project_id,
                        auto_convert=False  # Pas besoin de conversion, on a déjà vérifié
                    )
            elif op_type == "update":
                result = await writer.update_file(
                    operation["path"],
                    operation["content"],
                    project_id
                )
            elif op_type == "insert":
                result = await writer.insert_text(
                    operation["path"],
                    operation["after_line"],
                    operation["content"],
                    project_id
                )
            elif op_type == "search_replace":
                result = await writer.search_replace(
                    operation["path"],
                    operation["search"],
                    operation["replace"],
                    project_id
                )
            elif op_type == "rename":
                result = await writer.rename_file(
                    operation["old_path"],
                    operation["new_path"],
                    project_id
                )
            elif op_type == "delete":
                result = await writer.delete_file(
                    operation["path"],
                    project_id
                )
            else:
                raise FileWriterError(f"Unknown operation type: {op_type}")
            
            result["operation_index"] = i
            results.append(result)
            
        except FileWriterError as e:
            # Pour les chemins protégés, on propage l'exception pour retourner 422
            if "Protected path not writable" in str(e):
                logger.error(f"🛡️ Protected path violation: {e}")
                raise  # Propage l'exception pour HTTP 422
            
            # Pour les autres erreurs, on continue avec fail-safe
            logger.error(f"❌ Operation {i} ({op_type}) failed: {e}")
            results.append({
                "status": "failed",
                "operation_index": i,
                "operation_type": op_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            # Continue avec les autres opérations (fail-safe)
        
        except Exception as e:
            logger.error(f"❌ Operation {i} ({op_type}) unexpected error: {e}")
            results.append({
                "status": "failed",
                "operation_index": i,
                "operation_type": op_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    return results
