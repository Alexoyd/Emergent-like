"""
Pydantic Schemas pour File Operations (écriture directe)

Définit les modèles de validation pour les opérations d'écriture de fichiers
retournées par le DeveloperAgent.
"""

from pydantic import BaseModel, Field, validator
from typing import Literal, Union, List
from enum import Enum


class OperationType(str, Enum):
    """Types d'opérations supportées"""
    CREATE = "create"
    UPDATE = "update"
    INSERT = "insert"
    SEARCH_REPLACE = "search_replace"
    RENAME = "rename"
    DELETE = "delete"


class CreateOperation(BaseModel):
    """Créer un nouveau fichier"""
    type: Literal["create"] = "create"
    path: str = Field(..., description="Chemin relatif du fichier à créer")
    content: str = Field(..., description="Contenu complet du fichier")
    
    @validator('path')
    def validate_path(cls, v):
        if not v or v.startswith('/'):
            raise ValueError("Path must be relative and non-empty")
        if '..' in v:
            raise ValueError("Path cannot contain '..'")
        return v


class UpdateOperation(BaseModel):
    """Remplacer complètement le contenu d'un fichier existant"""
    type: Literal["update"] = "update"
    path: str = Field(..., description="Chemin relatif du fichier à modifier")
    content: str = Field(..., description="Nouveau contenu complet du fichier")
    
    @validator('path')
    def validate_path(cls, v):
        if not v or v.startswith('/'):
            raise ValueError("Path must be relative and non-empty")
        if '..' in v:
            raise ValueError("Path cannot contain '..'")
        return v


class InsertOperation(BaseModel):
    """Insérer du texte après une ligne spécifique"""
    type: Literal["insert"] = "insert"
    path: str = Field(..., description="Chemin relatif du fichier")
    after_line: int = Field(..., ge=-1, description="Numéro de ligne après laquelle insérer (0-indexed). 0=début, N=après ligne N, -1=EOF")
    content: str = Field(..., description="Contenu à insérer")
    
    @validator('path')
    def validate_path(cls, v):
        if not v or v.startswith('/'):
            raise ValueError("Path must be relative and non-empty")
        if '..' in v:
            raise ValueError("Path cannot contain '..'")
        return v


class SearchReplaceOperation(BaseModel):
    """Rechercher et remplacer du texte exact"""
    type: Literal["search_replace"] = "search_replace"
    path: str = Field(..., description="Chemin relatif du fichier")
    search: str = Field(..., min_length=1, description="Texte à rechercher (exact match)")
    replace: str = Field(..., description="Texte de remplacement")
    
    @validator('path')
    def validate_path(cls, v):
        if not v or v.startswith('/'):
            raise ValueError("Path must be relative and non-empty")
        if '..' in v:
            raise ValueError("Path cannot contain '..'")
        return v


class RenameOperation(BaseModel):
    """Renommer ou déplacer un fichier"""
    type: Literal["rename"] = "rename"
    old_path: str = Field(..., description="Chemin actuel")
    new_path: str = Field(..., description="Nouveau chemin")
    
    @validator('old_path', 'new_path')
    def validate_paths(cls, v):
        if not v or v.startswith('/'):
            raise ValueError("Path must be relative and non-empty")
        if '..' in v:
            raise ValueError("Path cannot contain '..'")
        return v


class DeleteOperation(BaseModel):
    """Supprimer un fichier"""
    type: Literal["delete"] = "delete"
    path: str = Field(..., description="Chemin relatif du fichier à supprimer")
    
    @validator('path')
    def validate_path(cls, v):
        if not v or v.startswith('/'):
            raise ValueError("Path must be relative and non-empty")
        if '..' in v:
            raise ValueError("Path cannot contain '..'")
        return v


# Union type pour toutes les opérations
FileOperation = Union[
    CreateOperation,
    UpdateOperation,
    InsertOperation,
    SearchReplaceOperation,
    RenameOperation,
    DeleteOperation
]


class DeveloperOutput(BaseModel):
    """
    Output du DeveloperAgent en mode écriture directe
    
    Le LLM doit retourner ce JSON au lieu d'un diff Git
    """
    operations: List[FileOperation] = Field(
        ..., 
        description="Liste des opérations d'écriture à effectuer",
        min_items=1
    )
    
    class Config:
        # Allow discriminated unions based on 'type' field
        use_enum_values = True


class StepCommit(BaseModel):
    """Métadonnées pour le commit Git après chaque step"""
    run_id: str
    step_number: int
    step_title: str
    
    def format_message(self) -> str:
        """Format: feat(run:<run_id>): step <n> – <titre>"""
        return f"feat(run:{self.run_id}): step {self.step_number} – {self.step_title}"


# Exemple de JSON attendu du LLM:
EXAMPLE_DEVELOPER_OUTPUT = """
{
  "operations": [
    {
      "type": "create",
      "path": "resources/views/home.blade.php",
      "content": "<!DOCTYPE html>\\n<html>\\n<head>\\n    <title>Home</title>\\n</head>\\n<body>\\n    <h1>Welcome</h1>\\n</body>\\n</html>"
    },
    {
      "type": "search_replace",
      "path": "routes/web.php",
      "search": "Route::get('/', function () {",
      "replace": "Route::get('/home', function () {"
    },
    {
      "type": "insert",
      "path": "app/Http/Controllers/Controller.php",
      "after_line": 10,
      "content": "use Illuminate\\\\Support\\\\Facades\\\\Log;"
    }
  ]
}
"""
