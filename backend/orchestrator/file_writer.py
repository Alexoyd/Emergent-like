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
    
    async def create_file(self, file_path: str, content: str, project_id: str) -> Dict[str, Any]:
        """
        Crée un nouveau fichier avec contenu
        
        Args:
            file_path: Chemin relatif du fichier à créer
            content: Contenu du fichier
            project_id: ID du projet (pour lock)
        
        Returns:
            Dict avec status, path, hash, size
        """
        async with self._get_lock(project_id):
            try:
                target_path = self._validate_path(file_path)
                
                # Vérifier que le fichier n'existe pas déjà
                if target_path.exists():
                    raise FileWriterError(f"File already exists: {file_path}")
                
                # Vérifier taille
                size = len(content.encode('utf-8'))
                if size > MAX_FILE_SIZE:
                    raise FileWriterError(f"File too large: {size} bytes (max {MAX_FILE_SIZE})")
                
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
            after_line: Numéro de ligne après laquelle insérer (1-indexed)
            content: Contenu à insérer
            project_id: ID du projet (pour lock)
        
        Returns:
            Dict avec status, path, line_number
        """
        async with self._get_lock(project_id):
            try:
                target_path = self._validate_path(file_path)
                
                if not target_path.exists():
                    raise FileWriterError(f"File does not exist: {file_path}")
                
                # Lire lignes existantes
                lines = target_path.read_text(encoding='utf-8').splitlines(keepends=True)
                
                # Vérifier numéro de ligne valide
                if after_line < 0 or after_line > len(lines):
                    raise FileWriterError(f"Invalid line number: {after_line} (file has {len(lines)} lines)")
                
                # Insérer contenu
                lines.insert(after_line, content if content.endswith('\n') else content + '\n')
                
                # Écrire fichier modifié
                new_content = ''.join(lines)
                target_path.write_text(new_content, encoding='utf-8')
                
                logger.info(f"✅ Inserted text in {file_path} after line {after_line}")
                
                return {
                    "status": "inserted",
                    "path": file_path,
                    "after_line": after_line,
                    "timestamp": datetime.now().isoformat()
                }
                
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


async def execute_operations(operations: List[Dict[str, Any]], project_path: str, project_id: str) -> List[Dict[str, Any]]:
    """
    Exécute une liste d'opérations d'écriture de fichiers
    
    Args:
        operations: Liste d'opérations à exécuter
        project_path: Chemin du projet
        project_id: ID du projet
    
    Returns:
        Liste des résultats d'exécution
    """
    writer = FileWriter(project_path)
    results = []
    
    for i, operation in enumerate(operations):
        op_type = operation.get("type")
        
        try:
            if op_type == "create":
                result = await writer.create_file(
                    operation["path"],
                    operation["content"],
                    project_id
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
            
        except Exception as e:
            logger.error(f"❌ Operation {i} ({op_type}) failed: {e}")
            results.append({
                "status": "failed",
                "operation_index": i,
                "operation_type": op_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            # Continue avec les autres opérations (fail-safe)
    
    return results
