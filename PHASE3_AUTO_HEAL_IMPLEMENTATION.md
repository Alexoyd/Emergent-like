# 🔥 PHASE 3: AUTO-HEAL STACK-AGNOSTIQUE - IMPLÉMENTATION

**Date**: 2025-01-XX  
**Statut**: ✅ IMPLÉMENTÉ, EN ATTENTE TESTS

---

## 📋 Résumé

Système Auto-Heal complet permettant de détecter, corriger et valider automatiquement des projets via pipelines de santé stack-agnostiques. Crée des branches `autofix/*` dédiées avec tagging ready-to-merge/needs-review. **JAMAIS d'auto-merge vers main**.

---

## 🏗️ Modules Créés

### **1. orchestrator/auto_heal.py**

**AutoHealManager**:
- `start_auto_heal()`: Workflow complet auto-heal
- `_detect_stack()`: Détection Laravel/Node/Python/Generic
- `_tag_branch()`: Tagging avec statut santé
- `get_branches()`: Liste branches autofix + statuts
- `get_branch_artifacts()`: Diffs, commits, logs, résultats
- `close_branch()`: Cleanup branche + status files

**Workflow**:
```
1. Validate project exists
2. Ensure Git clean (auto-commit si dirty)
3. Create branch autofix/YYYYMMDD-HHMMSS from HEAD
4. Detect stack (heuristics)
5. Apply fixes:
   - LLM path: DeveloperAgentDirect → operations[]
   - No-LLM: Injection operations[] directe
6. Execute operations via file_writer
7. Commit: fix(autofix:<run_id>): step <n> – <titre>
8. Run health pipelines
9. Tag branch: ready-to-merge | needs-review
10. Return to original branch
```

---

### **2. orchestrator/health_pipelines.py**

**HealthPipelineRunner**:
- `run_health_pipeline()`: Pipeline complet par stack
- `_run_laravel_pipeline()`: composer, pint, pest, phpstan, smoke
- `_run_node_pipeline()`: npm ci, eslint, jest, build, smoke
- `_run_python_pipeline()`: pip, ruff, mypy, pytest, smoke
- `_run_generic_pipeline()`: Git clean, README, file sizes

**Checks par Stack**:

#### **Laravel**
1. ✅ `composer install --no-interaction --prefer-dist`
2. ⚡ `vendor/bin/pint --test` (si disponible)
3. 🧪 `vendor/bin/pest` ou `vendor/bin/phpunit`
4. 🔍 `vendor/bin/phpstan analyse` (si disponible)
5. 💨 `php artisan route:list` (smoke test)

#### **Node/JS**
1. ✅ `npm ci`
2. ⚡ `npm run lint` (si config ESLint)
3. 🧪 `npm test -- --watchAll=false`
4. 📦 `npm run build` (si script existe)
5. 💨 Smoke test (optionnel)

#### **Python**
1. ✅ `pip install -r requirements.txt`
2. ⚡ `ruff check .` (si config)
3. 🔍 `mypy .` (si config)
4. 🧪 `pytest -q`
5. 💨 Smoke test (optionnel)

#### **Generic Fallback**
1. ✅ Git working directory clean
2. 📝 README exists
3. 📏 No files > 10 MB

---

## 🌐 Endpoints API

### **1. POST /api/projects/{id}/auto-heal**

Démarre le processus auto-heal.

**Request**:
```json
{
  "max_steps": 5,
  "branch_name": null,
  "auto_merge": false,
  "operations": [...]  // Optional no-LLM
}
```

**Response**:
```json
{
  "branch_name": "autofix/20250120-143022",
  "branch_commit": "abc123...",
  "steps_applied": 1,
  "files_changed": ["file1.php", "file2.js"],
  "health_status": "ready-to-merge",
  "health_results": {
    "stack": "laravel",
    "checks": [...],
    "overall_status": "passed"
  },
  "stack": "laravel",
  "created_at": "2025-01-20T14:30:22Z"
}
```

---

### **2. GET /api/projects/{id}/branches**

Liste toutes les branches autofix avec statuts.

**Response**:
```json
{
  "project_id": "proj-123",
  "branches": [
    {
      "branch_name": "autofix/20250120-143022",
      "commit": "abc123...",
      "commit_message": "fix(autofix:proj-123): step 1 – ...",
      "author": "AI Engineer",
      "committed_at": "2025-01-20T14:30:30Z",
      "status": "ready-to-merge",
      "health_results": {...}
    }
  ],
  "total": 1
}
```

---

### **3. POST /api/projects/{id}/branches/{branch}/test**

Relance le pipeline de santé pour une branche.

**Response**:
```json
{
  "branch_name": "autofix/20250120-143022",
  "health_status": "ready-to-merge",
  "health_results": {
    "stack": "laravel",
    "checks": [
      {
        "name": "composer_install",
        "status": "passed",
        "output": "...",
        "duration_seconds": 12.5,
        "description": "Install dependencies"
      }
    ],
    "overall_status": "passed"
  }
}
```

---

### **4. GET /api/projects/{id}/branches/{branch}/artifacts**

Récupère artefacts complets (diffs, logs, résultats).

**Response**:
```json
{
  "branch_name": "autofix/20250120-143022",
  "diff": "diff --git a/file1.php ...",
  "commits": [
    {
      "hash": "abc123...",
      "message": "fix(autofix:proj-123): step 1 – ...",
      "author": "AI Engineer",
      "date": "2025-01-20T14:30:30Z"
    }
  ],
  "status": "ready-to-merge",
  "health_results": {...},
  "retrieved_at": "2025-01-20T14:35:00Z"
}
```

---

### **5. POST /api/projects/{id}/branches/{branch}/close**

Ferme et nettoie une branche autofix.

**Response**:
```json
{
  "status": "success",
  "message": "Branch autofix/20250120-143022 closed successfully"
}
```

---

## 🔒 Garde-fous Hérités

1. **Deny-list** (19 chemins): `.git/`, `.env*`, `vendor/`, `node_modules/`, etc.
2. **Validation chemins**: Relatifs uniquement, pas de `..`
3. **Limite taille**: 10 MB par fichier
4. **Locks**: asyncio.Lock par projet
5. **Timeouts**: 300s par commande pipeline
6. **Auto-merge**: TOUJOURS `False` (jamais vers main)

---

## 🧪 Tests d'Acceptation

### **Case A: Laravel Auto-Heal**
```bash
# Setup
mkdir -p /app/projects/test-laravel-heal/code
cd /app/projects/test-laravel-heal/code
echo '{"require": {"laravel/framework": "^10.0"}}' > composer.json
git init && git add . && git commit -m "Initial"

# Auto-heal with no-LLM
curl -X POST http://localhost:8001/api/projects/test-laravel-heal/auto-heal \
  -H "Content-Type: application/json" \
  -d '{
    "max_steps": 1,
    "operations": [
      {
        "type": "create",
        "path": "routes/api.php",
        "content": "<?php\nRoute::get(\"/health\", fn() => [\"status\" => \"ok\"]);"
      }
    ]
  }'

# Expected:
# - Branch autofix/YYYYMMDD-HHMMSS created
# - Commit: fix(autofix:test-laravel-heal): step 1 – ...
# - Health pipeline runs: composer, pint, pest, phpstan, smoke
# - Status: ready-to-merge OR needs-review based on results
```

### **Case B: Node Auto-Heal**
```bash
# Setup
mkdir -p /app/projects/test-node-heal/code
cd /app/projects/test-node-heal/code
echo '{"name": "test", "scripts": {"test": "jest"}}' > package.json
git init && git add . && git commit -m "Initial"

# Auto-heal
curl -X POST http://localhost:8001/api/projects/test-node-heal/auto-heal \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      {"type": "create", "path": "index.js", "content": "console.log(\"Hello\");"}
    ]
  }'

# Expected: Similar to Laravel, but with npm ci, eslint, npm test, build
```

### **Case C: Stack Inconnu (Generic)**
```bash
# Setup
mkdir -p /app/projects/test-generic-heal/code
cd /app/projects/test-generic-heal/code
echo "# Test Project" > README.md
git init && git add . && git commit -m "Initial"

# Auto-heal
curl -X POST http://localhost:8001/api/projects/test-generic-heal/auto-heal \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      {"type": "create", "path": "file.txt", "content": "Hello"}
    ]
  }'

# Expected: Generic pipeline (Git clean, README check, file sizes)
```

### **Case D: Protected Paths Rejection**
```bash
curl -X POST http://localhost:8001/api/projects/test-laravel-heal/auto-heal \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      {"type": "update", "path": ".env", "content": "MALICIOUS=true"}
    ]
  }'

# Expected: HTTP 422, error "Protected path not writable: .env"
```

---

## 📊 Format Commits Git

```
fix(autofix:<run_id>): step <n> – <titre>

Examples:
fix(autofix:proj-123): step 1 – Add health endpoint
fix(autofix:proj-456): step 2 – Fix linting errors
```

(Différent de Phase 2 qui utilise `feat(run:...)`)

---

## 📝 Artifacts & Traçabilité

**Stockage**:
- Status files: `.git/autofix-status/{branch_name}.json`
- Contenu: `{branch, status, health_results, tagged_at}`

**Artefacts disponibles via API**:
1. **Diffs Git**: Entre merge-base (main) et branch head
2. **Commits**: Liste des 10 derniers commits de la branche
3. **Status**: ready-to-merge | needs-review | unknown
4. **Health Results**: Tous les checks avec outputs, durées, codes retour

---

## 🎯 Comportements Attendus

### **Auto-Heal Success**
```
1. Branch autofix/* créée
2. Operations appliquées
3. Commit créé
4. Health pipeline: ALL PASSED
5. Tag: ready-to-merge
6. Return to original branch
```

### **Auto-Heal Partial Failure**
```
1-3: Same as success
4. Health pipeline: SOME FAILED
5. Tag: needs-review
6. Artifacts logged for debugging
7. NO auto-merge
```

### **Auto-Heal Hard Failure**
```
1-2: Same as success
3. Operations failed (e.g., protected path)
4. HTTP 422/500 returned
5. No commit, no health pipeline
6. Return to original branch
7. Branch may exist partially (cleanup required)
```

---

## 🚫 Ce Qui N'Est PAS Implémenté (Intentionnel)

1. **Auto-merge vers main**: TOUJOURS `False`, design decision
2. **LLM path**: Pas de génération automatique via DeveloperAgentDirect (à ajouter si clés LLM)
3. **Merge conflict resolution**: Assume branches isolées
4. **Multi-step iterations**: Actuellement single-step, extensible
5. **UI Frontend**: Phase 4

---

## 📚 Documentation Technique

### **Détection Stack (Heuristics)**
```python
# Laravel
composer.json + laravel/framework OR artisan exists

# Node
package.json exists

# Python
pyproject.toml OR requirements.txt exists

# Generic
Fallback si aucun match
```

### **Health Check Structure**
```json
{
  "name": "check_name",
  "status": "passed" | "failed" | "skipped",
  "output": "stdout + stderr (truncated 2000 chars)",
  "return_code": 0,
  "duration_seconds": 12.5,
  "description": "Human-readable description"
}
```

---

## 🎉 Conclusion Phase 3

✅ **INFRASTRUCTURE AUTO-HEAL COMPLÈTE**

Le système peut maintenant:
- Créer branches autofix/* depuis HEAD
- Détecter stack automatiquement (Laravel, Node, Python, Generic)
- Appliquer fixes via operations[] (no-LLM)
- Exécuter pipelines de santé stack-agnostiques
- Tagger branches (ready-to-merge / needs-review)
- Exposer artefacts complets via API
- Fermer/cleanup branches

**Prêt pour**: Tests d'acceptation backend + Phase 4 (Frontend UI)

**Tests requis**:
- [ ] Case A: Laravel auto-heal
- [ ] Case B: Node auto-heal
- [ ] Case C: Stack inconnu (generic)
- [ ] Case D: Protected paths rejection
- [ ] Case E: Branch artifacts retrieval
- [ ] Case F: Rerun health pipeline
- [ ] Case G: Close branch

---

**Auteur**: AI Engineer E1.1  
**Status**: ✅ Implémentation complète, compilation OK  
**Next**: Backend testing agent validation
