# 🔥 PHASE 2: MODE ATTACH - IMPLÉMENTATION

**Date**: 2025-01-XX  
**Statut**: 🚧 EN COURS

---

## 📋 Résumé

Implémentation du mode "Attach" permettant de modifier des projets existants sans recréation. Inclut un chemin "no-LLM" pour tester end-to-end sans clés API.

---

## 🏗️ Modifications Implémentées

### **1. Modèles Pydantic (server.py)**

#### **RunCreate**
```python
class RunCreate(BaseModel):
    # ... champs existants ...
    
    # 🔥 PHASE 2
    project_mode: Literal["create", "attach"] = "create"
    project_id: Optional[str] = None
```

#### **Run**
```python
class Run(BaseModel):
    # ... champs existants ...
    
    # 🔥 PHASE 2
    project_mode: str = "create"
    project_id: Optional[str] = None
    attached_commit: Optional[str] = None  # Initial commit hash
```

#### **ExecuteOperationsRequest** (Nouveau)
```python
class ExecuteOperationsRequest(BaseModel):
    """Pour chemin no-LLM"""
    run_id: str
    project_id: str
    operations: List[Dict[str, Any]]  # min 1
    commit: Dict[str, Any]  # {title, step_number}
```

---

### **2. Endpoint POST /api/runs (Modifié)**

**Nouvelles fonctionnalités**:
- Détection du `project_mode` (create/attach)
- Si `attach`:
  - Valide `project_id` ou `project_path`
  - Appelle `project_manager.attach_to_project()`
  - Récupère infos projet existant
  - Met à jour run avec `attached_commit`
- Si `create`:
  - Comportement existant (création workspace isolé)

**Réponse**:
```json
{
  "id": "run-uuid",
  "project_mode": "attach",
  "project_id": "project-uuid",
  "project_path": "/app/projects/project-uuid/code",
  "attached_commit": "abc123...",
  "stack": "laravel",
  ...
}
```

---

### **3. Nouveau: POST /api/runs/execute-operations** 🆕

**Chemin no-LLM** pour tester sans clés API.

**Request**:
```json
{
  "run_id": "run-uuid",
  "project_id": "project-uuid",
  "operations": [
    {
      "type": "create",
      "path": "src/NewFile.php",
      "content": "<?php\n..."
    },
    {
      "type": "update",
      "path": "README.md",
      "content": "# Updated content"
    }
  ],
  "commit": {
    "title": "Add new feature",
    "step_number": 1
  }
}
```

**Response**:
```json
{
  "status": "success",
  "operations_executed": 2,
  "commit_hash": "def456...",
  "artifacts": {
    "operations_count": 2,
    "files_changed": ["src/NewFile.php", "README.md"],
    "commit_hash": "def456...",
    "operations_results": [...]
  }
}
```

**Pipeline complet**:
1. ✅ Validation (deny-list, path checks)
2. ✅ Exécution opérations via `execute_operations()`
3. ✅ Git commit atomique via `_commit_step_changes()`
4. ✅ RAG re-indexing (si files_changed)
5. ✅ Artifacts logging

---

### **4. ProjectManager.attach_to_project()** 🆕

**Signature**:
```python
async def attach_to_project(
    project_id: Optional[str] = None,
    project_path: Optional[str] = None,
    run_id: Optional[str] = None
) -> Dict[str, Any]
```

**Validations**:
- ✅ Projet existe (via `project_id` ou `project_path`)
- ✅ Git repo initialisé (sinon initialise)
- ✅ Git clean (commit uncommitted changes si nécessaire)
- ✅ Détection stack automatique
- ✅ Validation structure projet (non vide)

**Retour**:
```python
{
    "project_path": "/app/projects/.../code",
    "stack": "laravel",
    "project_id": "project-uuid",
    "initial_commit": "abc123...",
    "git_clean": True,
    "attached_at": "2025-01-XX..."
}
```

**Comportements**:
- Si Git dirty → commit automatique avec message `"Pre-attach commit for run <run_id>"`
- Si pas de Git → initialise repo
- Si stack unknown → warning mais continue
- Si projet vide → warning mais continue

---

## 🔒 Garde-fous (Hérités Phase 1)

1. **Deny-list** (19 chemins protégés)
2. **Validation chemins relatifs** (pas de `/`, pas de `..`)
3. **Limite taille fichier** (10 MB)
4. **Locks par projet** (asyncio.Lock)
5. **Git commits atomiques** par step

---

## 🧪 Tests à Effectuer

### **Case A: Attacher projet Laravel existant**
```bash
# 1. Créer projet test Laravel
cd /app/projects
mkdir test-laravel-attach && cd test-laravel-attach
composer create-project laravel/laravel code --no-interaction

# 2. Créer run en mode attach
curl -X POST http://localhost:8001/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Add hello world controller",
    "project_mode": "attach",
    "project_path": "/app/projects/test-laravel-attach/code",
    "stack": "laravel"
  }'

# 3. Exécuter opérations (no-LLM)
curl -X POST http://localhost:8001/api/runs/execute-operations \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "<run_id>",
    "project_id": "test-laravel-attach",
    "operations": [
      {
        "type": "create",
        "path": "app/Http/Controllers/HelloController.php",
        "content": "<?php\nnamespace App\\Http\\Controllers;\nclass HelloController extends Controller { public function index() { return \"Hello World\"; } }"
      }
    ],
    "commit": {"title": "Add HelloController", "step_number": 1}
  }'

# 4. Vérifier commit Git
cd /app/projects/test-laravel-attach/code
git log --oneline -n 3
# Attendu: feat(run:<run_id>): step 1 – Add HelloController
```

### **Case B: Attacher projet Node simple**
```bash
# 1. Créer projet test Node
mkdir -p /app/projects/test-node-attach/code
cd /app/projects/test-node-attach/code
npm init -y

# 2. Attach + operations...
# (même pattern que Case A)
```

### **Case C: Tentative écriture chemins protégés**
```bash
curl -X POST http://localhost:8001/api/runs/execute-operations \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "<run_id>",
    "project_id": "test-laravel-attach",
    "operations": [
      {
        "type": "update",
        "path": ".env",
        "content": "MALICIOUS=true"
      }
    ],
    "commit": {"title": "Evil", "step_number": 1}
  }'

# Attendu: 422 ou 500 avec message "Protected path not writable: .env"
```

---

## 📝 Points d'Attention

### **Limitations Actuelles**
1. **Frontend non adapté**: Pas encore de sélecteur Create/Attach dans UI
2. **Artifacts display**: Pas d'affichage des commits/fichiers modifiés dans frontend
3. **LLM path**: DeveloperAgentDirect nécessite clés pour génération (workaround: no-LLM)

### **Comportements Attendus**
- Attach sur projet avec uncommitted changes → commit auto
- Attach sur projet sans Git → init repo
- Operations échouées → status "failed" avec détails erreurs
- Git commit échoué → warning mais continue (pas bloquant)
- RAG reindex échoué → warning mais continue

---

## 🎯 Prochaines Étapes Phase 2

### **Backend Restant**
- [ ] Tests d'acceptation (Cases A, B, C)
- [ ] Endpoint GET /api/runs/{id}/commits (timeline)
- [ ] Endpoint GET /api/runs/{id}/artifacts (détails)

### **Frontend**
- [ ] Sélecteur projet (Create/Attach) dans formulaire
- [ ] Liste projets existants (GET /api/projects)
- [ ] Affichage timeline commits par step
- [ ] Panel artifacts (files changed, sha256, diffs)
- [ ] Toggle "auto-merge on green" (UI only)

### **Phase 3 (Auto-Heal)**
- [ ] POST /api/projects/{id}/auto-heal
- [ ] Création branche autofix/*
- [ ] Health pipelines stack-agnostic
- [ ] Tagging ready-to-merge/needs-review

---

## 📚 Documentation Technique

### **Flux Attach Mode**
```
1. User: POST /api/runs {"project_mode":"attach", "project_id":"..."}
   ↓
2. Backend: project_manager.attach_to_project()
   ↓ Validations: Git clean, structure OK, stack detection
   ↓
3. Backend: execute_run() (background task)
   ↓
4. Si LLM dispo: DeveloperAgentDirect → generate_operations()
   Si LLM indispo: Attente POST /api/runs/execute-operations
   ↓
5. Backend: execute_operations() → file writes
   ↓
6. Backend: _commit_step_changes() → Git commit atomique
   ↓
7. Backend: RAG re-indexing (si files_changed)
   ↓
8. Response: artifacts + commit_hash
```

### **Format Commit Git**
```
feat(run:<run_id>): step <n> – <titre>

Example:
feat(run:abc123): step 1 – Add HelloController
feat(run:def456): step 2 – Update routes
```

---

**Auteur**: AI Engineer E1.1  
**Status Backend**: ✅ Implémenté, compilation OK  
**Status Tests**: ⏳ En attente (Cases A, B, C)
