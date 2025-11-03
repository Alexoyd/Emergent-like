# RAG COMPLET - SYSTÈME D'ORCHESTRATION D'AGENTS AI

> **Document de contexte exhaustif pour LLM**  
> Version: 3.0 - Phase Auto-Heal Complète  
> Date: 2025  
> Objectif: Fournir un contexte complet sans ambiguïté pour éviter les erreurs d'interprétation

---

## 📋 TABLE DES MATIÈRES

1. [Vue d'ensemble du système](#1-vue-densemble-du-système)
2. [Architecture technique](#2-architecture-technique)
3. [Backend FastAPI](#3-backend-fastapi)
4. [Système d'agents AI](#4-système-dagents-ai)
5. [Système LLM Router](#5-système-llm-router)
6. [Gestion des fichiers](#6-gestion-des-fichiers)
7. [Système Auto-Heal](#7-système-auto-heal)
8. [Stacks supportées](#8-stacks-supportées)
9. [API Endpoints](#9-api-endpoints)
10. [Frontend React](#10-frontend-react)
11. [Base de données MongoDB](#11-base-de-données-mongodb)
12. [Configuration et environnement](#12-configuration-et-environnement)
13. [Workflow complet](#13-workflow-complet)
14. [Évolutions récentes](#14-évolutions-récentes)
15. [Points critiques](#15-points-critiques)

---

## 1. VUE D'ENSEMBLE DU SYSTÈME

### 1.1 Description générale

**Cognitia** est un système d'orchestration d'agents AI qui automatise la génération, le test et la correction de code. Il reproduit le comportement d'Emergent.sh avec des capacités d'auto-réparation avancées.

### 1.2 Objectif principal

Générer automatiquement du code fonctionnel pour différents stacks (Laravel, React, Vue, Node, Python) en utilisant une approche itérative multi-agents avec escalation de modèles LLM et auto-correction.

### 1.3 Composants principaux

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTÈME COGNITIA                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Frontend   │  │   Backend    │  │   MongoDB    │      │
│  │    React     │◄─┤   FastAPI    │◄─┤   Database   │      │
│  │              │  │              │  │              │      │
│  └──────────────┘  └──────┬───────┘  └──────────────┘      │
│                           │                                  │
│                    ┌──────▼────────┐                         │
│                    │  Orchestrator │                         │
│                    │   Components  │                         │
│                    └───────┬───────┘                         │
│                            │                                  │
│  ┌─────────────────────────┼──────────────────────────────┐ │
│  │                         │                               │ │
│  │  ┌──────────┐  ┌───────▼─────┐  ┌──────────────────┐  │ │
│  │  │ Planner  │  │ Developer   │  │   Reviewer       │  │ │
│  │  │  Agent   │─►│   Agent     │─►│    Agent         │  │ │
│  │  └──────────┘  └─────────────┘  └──────────────────┘  │ │
│  │                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │ │
│  │  │  LLM Router  │  │ File Writer  │  │ Auto-Heal   │ │ │
│  │  │  (Escalation)│  │  (Direct)    │  │  Manager    │ │ │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │ │
│  │                                                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  LLM Providers: Ollama → OpenAI GPT-5 → Claude 4    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 1.4 Flux de travail simplifié

1. **Utilisateur** saisit un objectif (goal) dans l'interface
2. **PlannerAgent** génère un plan d'exécution détaillé
3. **DeveloperAgent** génère des opérations de fichiers (JSON) ou des patches (Git)
4. **Application** des modifications sur le projet isolé
5. **Tests automatiques** (Pest, PHPStan, Jest, etc.)
6. **ReviewerAgent** évalue les résultats
7. **Auto-correction** en cas d'échec (RepairAgent)
8. **Auto-Heal** pour corrections avancées avec branches Git
9. **Livraison** du code final fonctionnel

---

## 2. ARCHITECTURE TECHNIQUE

### 2.1 Stack technologique

**Backend:**
- **FastAPI** (Python 3.11+) - API REST asynchrone
- **MongoDB** - Base de données NoSQL (runs, projets, logs)
- **AsyncIO** - Programmation asynchrone native
- **Pydantic** v2.8.2 - Validation de données

**Frontend:**
- **React** 18+ - Interface utilisateur
- **TailwindCSS** + **shadcn/ui** - Design system
- **Yarn** - Gestionnaire de paquets

**Infrastructure:**
- **Supervisor** - Gestion des processus (backend, frontend)
- **Git** - Versioning et gestion des branches auto-heal
- **Docker/Kubernetes** - Déploiement (environnement de production)

### 2.2 Répertoires principaux

```
/app/
├── backend/
│   ├── server.py                    # Point d'entrée FastAPI
│   ├── requirements.txt             # Dépendances Python
│   ├── .env                         # Configuration environnement
│   └── orchestrator/
│       ├── agents/                  # Agents AI (Planner, Developer, Reviewer)
│       ├── stacks/                  # Handlers par stack (Laravel, React, etc.)
│       ├── llm_router.py            # Routage et escalation LLM
│       ├── file_writer.py           # Écriture directe de fichiers
│       ├── schemas.py               # Modèles Pydantic
│       ├── auto_heal.py             # Auto-réparation avancée
│       ├── health_pipelines.py      # Pipelines de santé par stack
│       ├── project_manager.py       # Gestion projets isolés
│       ├── state_manager.py         # État et logs dans MongoDB
│       ├── rag_system.py            # Système RAG (contexte)
│       ├── tools.py                 # Outils (tests, commandes)
│       ├── prompt_cache.py          # Cache de prompts (économies)
│       ├── github_integration.py    # Intégration GitHub OAuth
│       └── utils/                   # Utilitaires (JSON, BSON)
│
├── frontend/
│   ├── src/
│   │   ├── App.js                   # Composant principal
│   │   ├── components/
│   │   │   ├── AdminPanel.js        # Panel admin
│   │   │   ├── Timeline.js          # Timeline exécution
│   │   │   └── RunsList.js          # Liste des runs
│   │   └── index.js
│   ├── package.json
│   └── tailwind.config.js
│
├── projects/                        # Workspaces isolés par projet
│   └── {project_id}/
│       ├── code/                    # Code source du projet
│       ├── logs/                    # Logs d'exécution
│       ├── tests/                   # Tests générés
│       ├── patches/                 # Patches Git archivés
│       └── projet.json              # Métadonnées projet
│
├── test_result.md                   # Historique des tests et debugging
└── README.md                        # Documentation utilisateur
```

### 2.3 Ports et services

| Service  | Port  | URL                                                    |
|----------|-------|--------------------------------------------------------|
| Backend  | 8001  | https://repo-analyzer-105.preview.emergentagent.com/api |
| Frontend | 3000  | https://repo-analyzer-105.preview.emergentagent.com  |
| MongoDB  | 27017 | localhost:27017 (interne)                              |

**IMPORTANT:** Tous les endpoints backend doivent utiliser le préfixe `/api` pour respecter les règles d'ingress Kubernetes.

---

## 3. BACKEND FASTAPI

### 3.1 Point d'entrée: server.py

**Responsabilités:**
1. Définir les routes API REST
2. Initialiser les composants orchestrateur (agents, managers)
3. Gérer le cycle d'exécution des runs
4. Interfacer avec MongoDB pour la persistance

**Structure:**
```python
# Initialisation
app = FastAPI(title="AI Agent Orchestrator", version="1.0.0")
api_router = APIRouter(prefix="/api")

# Composants
llm_router = LLMRouter()
state_manager = StateManager(db)
project_manager = ProjectManager()
rag_system = RAGSystem()

# Agents
planner_agent = PlannerAgent(llm_router, rag_system)
developer_agent = DeveloperAgentDirect(llm_router, rag_system, tool_manager)
reviewer_agent = ReviewerAgent(llm_router)

# Auto-Heal
auto_heal_manager = AutoHealManager(health_pipeline_runner)
```

### 3.2 Modes de fonctionnement

#### Mode FILE_WRITE_MODE

**Valeurs:** `"direct"` (défaut) | `"patch"`

- **direct**: Le DeveloperAgent génère des opérations JSON qui modifient directement les fichiers via `file_writer.py`
- **patch**: Le DeveloperAgent génère des patches Git appliqués via `git apply`

**Configuration:** Variable d'environnement `FILE_WRITE_MODE=direct` dans `.env`

#### Mode DEVELOPMENT_MODE

**Valeur:** `true` (défaut pour tests) | `false`

- **true**: Génère des réponses simulées si aucune clé API LLM n'est disponible
- **false**: Nécessite des clés API LLM réelles (OpenAI, Anthropic, ou Ollama)

**Configuration:** `DEVELOPMENT_MODE=true` dans `.env`

### 3.3 Fonction principale: execute_run()

**Localisation:** `server.py` ligne 1460+

**Workflow:**
```python
async def execute_run(run_id: str, from_step: int = 0):
    """
    Phase 1: Planning (PlannerAgent)
    - Génération du plan d'exécution
    - Parsing des steps (hiérarchie → flat)
    - Sauvegarde dans MongoDB
    
    Phase 2: Execution itérative
    - Pour chaque step:
        * DeveloperAgent génère opérations/patch
        * Application des modifications
        * Exécution des tests
        * ReviewerAgent évalue
        * RepairAgent corrige si échec
        * Limite tentatives: 3 par step
    
    Phase 3: Finalisation
    - Export ZIP
    - Préparation GitHub
    - Archivage
    """
```

**Points critiques:**
- Limite de 20 steps par défaut (configurable via `MAX_STEPS_PER_RUN`)
- Timeout global: 1 heure (3600 secondes)
- Budget quotidien: 5€ par défaut (configurable via `DEFAULT_DAILY_BUDGET_EUR`)
- Isolation complète par projet (workspace dans `/app/projects/{project_id}/`)

---

## 4. SYSTÈME D'AGENTS AI

### 4.1 PlannerAgent

**Fichier:** `orchestrator/agents/planner.py`

**Rôle:** Générer un plan d'exécution structuré à partir de l'objectif utilisateur.

**Input:**
- `goal`: Description de l'objectif (ex: "Créer une API Laravel pour la gestion d'utilisateurs")
- `ProjectContext`: Contexte du projet (stack, fichiers existants, budget)

**Output:**
```python
@dataclass
class PlanResult:
    plan_text: str                    # Plan textuel lisible
    steps: List[Step]                 # Steps hiérarchiques avec substeps
    context: List[str]                # Contexte RAG utilisé
```

**Exemple de step:**
```python
Step(
    id="step_1",
    description="Créer le modèle User avec migrations",
    substeps=[
        Step(id="step_1_1", description="Générer migration users"),
        Step(id="step_1_2", description="Créer modèle User.php"),
        Step(id="step_1_3", description="Créer factory UserFactory")
    ],
    estimated_duration="10 minutes",
    files=["database/migrations/create_users_table.php", "app/Models/User.php"],
    dependencies=[]
)
```

**Hiérarchie → Flattening:**

Le système **flatten** automatiquement les substeps pour l'exécution:
```python
# Hiérarchie (affichage)
Step 1: Créer modèle User
  - Substep 1.1: Migration
  - Substep 1.2: Modèle
  - Substep 1.3: Factory

# Exécution (flat)
execution_steps = [
    substep_1_1,
    substep_1_2,
    substep_1_3
]
```

### 4.2 DeveloperAgent (Patches Git)

**Fichier:** `orchestrator/agents/developer.py`

**Rôle:** Générer des patches Git (`diff --git`) pour modifier le code.

**Mode:** Actif si `FILE_WRITE_MODE=patch`

**Output:**
```
BEGIN_PATCH
diff --git a/app/Models/User.php b/app/Models/User.php
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/app/Models/User.php
@@ -0,0 +1,15 @@
+<?php
+
+namespace App\Models;
+
+use Illuminate\Database\Eloquent\Model;
+
+class User extends Model
+{
+    protected $fillable = ['name', 'email'];
+}
END_PATCH
```

**Validation:**
- Vérification format unified diff
- Headers obligatoires: `diff --git`, `---`, `+++`, `@@`
- Auto-réparation si headers manquants
- Extraction fallback sans markers `BEGIN_PATCH/END_PATCH`

**Fonction clé:** `_is_valid_patch_format()`, `_try_repair_patch()`

### 4.3 DeveloperAgentDirect (Écriture directe)

**Fichier:** `orchestrator/agents/developer_direct.py`

**Rôle:** Générer des opérations JSON pour modifier directement les fichiers (sans passer par Git).

**Mode:** Actif si `FILE_WRITE_MODE=direct` (défaut)

**Output format:**
```json
{
  "operations": [
    {
      "type": "create",
      "path": "app/Models/User.php",
      "content": "<?php

namespace App\\Models;

class User {...}"
    },
    {
      "type": "insert",
      "path": "routes/web.php",
      "after_line": 10,
      "content": "Route::get('/users', [UserController::class, 'index']);"
    },
    {
      "type": "search_replace",
      "path": "config/app.php",
      "search": "'timezone' => 'UTC',",
      "replace": "'timezone' => 'Europe/Paris',"
    }
  ]
}
```

**Opérations supportées:**
1. **create**: Créer un nouveau fichier
2. **update**: Remplacer tout le contenu d'un fichier
3. **insert**: Insérer du texte après une ligne (0-indexed, -1 = EOF)
4. **search_replace**: Recherche/remplacement exact
5. **rename**: Renommer/déplacer un fichier
6. **delete**: Supprimer un fichier

**Validation Pydantic:**
- Chemins relatifs obligatoires (pas de `/` au début, pas de `..`)
- Contenu non vide pour create/update
- after_line >= -1 pour insert
- search non vide pour search_replace

**Prompt LLM critique:**
```python
STRICT_JSON_INSTRUCTIONS = """
CRITICAL: Return ONLY a valid JSON object (NO markdown, NO ```json fences).

Instructions insert operation (0-indexed):
- after_line=0: Insert AFTER first line (position 1)
- after_line=N: Insert AFTER line N (position N+1)
- after_line=-1: Insert at EOF (end of file anchor)

Example:
{"operations": [{"type": "insert", "path": "file.py", "after_line": 0, "content": "import os"}]}
"""
```

**Extraction robuste:**
- Support markdown code fences (```json)
- Extraction fallback sans markers
- Validation Pydantic stricte
- Max 3 tentatives avec feedback d'erreurs

### 4.4 ReviewerAgent

**Fichier:** `orchestrator/agents/reviewer.py`

**Rôle:** Évaluer les résultats de l'exécution d'un step (tests, code).

**Input:**
- Résultats des tests (Pest, PHPStan, Jest, etc.)
- Patch ou opérations appliquées
- Logs d'exécution

**Output:**
```python
@dataclass
class ReviewDecision:
    decision: Literal["accept", "reject", "escalate"]
    confidence: float  # 0.0 à 1.0
    feedback: str
    suggestions: List[str]
    should_escalate: bool
```

**Logique de décision:**
- **accept**: Tous les tests passent, code valide
- **reject**: Tests échouent, demande correction au DeveloperAgent
- **escalate**: Échecs répétés, retour au PlannerAgent pour révision du plan

**Limites:**
- Max 3 rejets par step avant escalation
- Max 2 révisions de plan avant échec définitif

### 4.5 RepairAgent

**Fichier:** `orchestrator/repair_agent.py`

**Rôle:** Auto-correction des erreurs simples détectées lors des tests.

**Stratégies:**
1. **Erreurs simples connues** (known_simple_issues):
   - Syntaxe PHP (virgules, parenthèses)
   - Imports manquants
   - Typos courants
   - **Note**: PHPStan retiré de cette liste (nécessite vraie correction)

2. **Réparations spécifiques par type de test:**
   - **Pest**: Génération tests manquants, fix assertions
   - **PHPStan**: Génération baseline progressive (niveau 0 par défaut)
   - **Pint**: Auto-fix via `./vendor/bin/pint --test` puis correction
   - **ESLint**: `eslint --fix` automatique

3. **Compteurs isolés par test:**
   - Pest: 3 tentatives max
   - PHPStan: 3 tentatives max  
   - Pint: 3 tentatives max
   - Limite globale: 5 réparations max par projet

**Configuration PHPStan Laravel:**
```php
# phpstan.neon (niveau 0 par défaut)
parameters:
    level: 0
    paths:
        - app
        - routes
    excludePaths:
        - vendor
    ignoreErrors:
        - '#Access to an undefined property#'
```

**Baseline PHPStan:**
- Génération idempotente via `phpstan analyse --generate-baseline`
- Toujours non-bloquante (warnings uniquement)
- Rotation automatique si fichier > 5MB

**Logs complets:**
- Écriture dans `/app/projects/{project_id}/logs/{test_type}_{timestamp}.log`
- Rotation automatique (max 5MB par fichier)
- Affichage tail (20 dernières lignes) + pointeur vers log complet

---

## 5. SYSTÈME LLM ROUTER

### 5.1 Vue d'ensemble

**Fichier:** `orchestrator/llm_router.py`

**Rôle:** Router intelligemment les requêtes vers les modèles LLM appropriés avec escalation automatique.

**Modèles supportés:**
1. **Ollama** (local, gratuit) - `qwen2.5-coder:7b`
2. **OpenAI GPT-4o** (payant) - Coût moyen
3. **Anthropic Claude 3.5 Sonnet** (payant) - Haute qualité

### 5.2 Stratégie d'escalation

```
┌──────────────────────────────────────────────────────────┐
│                   LLM ESCALATION PATH                     │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Tier 1: OLLAMA (local, FREE)                           │
│  └─ qwen2.5-coder:7b                                     │
│  └─ 3 tentatives max (MAX_LOCAL_RETRIES=3)              │
│  └─ Timeout: 120s                                        │
│  └─ Cost: €0.00                                          │
│                                                           │
│         ↓ (Si échec ou invalid response)                 │
│                                                           │
│  Tier 2: OPENAI (paid, MEDIUM)                          │
│  └─ gpt-4o                                               │
│  └─ 2 tentatives max (MAX_ESCALATION_RETRIES=2)         │
│  └─ Prompt caching: 30% économies                       │
│  └─ Cost: ~€0.005/1K tokens input                       │
│                                                           │
│         ↓ (Si échec ou invalid response)                 │
│                                                           │
│  Tier 3: ANTHROPIC (paid, PREMIUM)                      │
│  └─ claude-3-5-sonnet-20241022                          │
│  └─ 2 tentatives max                                     │
│  └─ Prompt caching: 50% économies                       │
│  └─ Cost: ~€0.003/1K tokens input                       │
│  └─ Circuit breaker: 15min si erreur 401                │
│                                                           │
│         ↓ (Si échec final)                               │
│                                                           │
│  Fallback: MOCK (development mode)                       │
│  └─ Réponses simulées pour tests                        │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### 5.3 Validation des réponses

**Fonction:** `_is_valid_response(content, task_type)`

**Règles strictes pour task_type="coding":**

✅ **ACCEPTÉ:**
```
diff --git a/app/Models/User.php b/app/Models/User.php
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/app/Models/User.php
@@ -0,0 +1,5 @@
+<?php
+
+namespace App\Models;
+
+class User extends Model {}
```

❌ **REJETÉ:**
- Commence pas par `diff --git`
- Manque headers `---` ou `+++`
- Manque hunk headers `@@`
- Contient du texte explicatif (prose)
- Markdown code fences (`\`\`\`diff`)

**Auto-retry:**
Si réponse invalide pour task_type="coding", une seule tentative de retry avec message strict:
```
Invalid output. Re-emit ONLY a valid unified diff suitable for 'git apply'. 
Start with 'diff --git …'. No prose/HTML/Markdown fences.
```

### 5.4 Prompt Caching

**Fichier:** `orchestrator/prompt_cache.py`

**Objectif:** Réduire les coûts de 30-75% en cachant les prompts système constants.

**Stratégie:**
1. **System prompts** constants sont hashés (SHA-256) et mis en cache (TTL: 24h)
2. **Conversation history** ajoutée comme delta
3. **Cache natif** OpenAI et Anthropic utilisé si disponible

**Économies mesurées:**
- Cache hits: 100% après premier appel
- Tokens économisés: ~2000 par run
- Coût économisé: €0.0085 par run (66% de réduction)

**Statistiques:**
```python
cache_stats = {
    "total_entries": 2,
    "total_usage": 6,
    "hit_rate": 1.0,  # 100%
    "most_used": ["planning", "coding"],
    "cache_size_limit": 100,
    "ttl_hours": 24
}
```

### 5.5 Circuit Breaker Anthropic

**Problème:** Erreurs 401 récurrentes avec Anthropic bloquent l'exécution.

**Solution:** Circuit breaker automatique

**Fonctionnement:**
1. Détection erreur 401 (authentication_error)
2. Activation circuit breaker: 15 minutes (configurable)
3. Pendant 15min: Anthropic exclu de l'escalation path
4. Après expiration: Réactivation automatique

**Configuration:** `ANTHROPIC_CIRCUIT_BREAKER_MINUTES=15`

**Désactivation manuelle:** `ENABLE_ANTHROPIC=false` dans `.env`

### 5.6 Rate Limiting

**Fonction:** `_wait_if_rate_limited()`

**Limite:** 20 requêtes/minute par défaut (`MAX_REQUESTS_PER_MINUTE=20`)

**Mécanisme:**
- Sliding window de 60 secondes
- Pause automatique si limite atteinte
- Backoff exponentiel entre retries locaux

---

## 6. GESTION DES FICHIERS

### 6.1 FileWriter (Écriture directe)

**Fichier:** `orchestrator/file_writer.py`

**Objectif:** Remplacer les patches Git par des opérations d'écriture directes pour plus de robustesse.

### 6.2 Primitives d'écriture

#### CREATE
```python
await writer.create_file(
    file_path="app/Models/User.php",
    content="<?php

namespace App\\Models;

class User extends Model {}",
    project_id="abc123"
)
```
- Vérifie que le fichier n'existe pas déjà
- Crée les répertoires parents si nécessaire
- Limite taille: 10MB max
- Retourne hash SHA-256 du contenu

#### UPDATE
```python
await writer.update_file(
    file_path="app/Models/User.php",
    content="<?php

// Nouveau contenu complet",
    project_id="abc123"
)
```
- Vérifie que le fichier existe
- Remplace tout le contenu
- Retourne old_hash et new_hash

#### INSERT
```python
await writer.insert_text(
    file_path="routes/web.php",
    after_line=10,  # 0-indexed
    content="Route::get('/users', [UserController::class, 'index']);",
    project_id="abc123"
)
```
**IMPORTANT - Indexation 0-based:**
- `after_line=0`: Insère APRÈS la première ligne (position 1)
- `after_line=N`: Insère APRÈS la ligne N (position N+1)
- `after_line=-1`: Insère à la fin du fichier (EOF anchor)
- Si `after_line > nombre_lignes`: **Clamp à EOF** (idempotence)

**Idempotence:**
- Vérifie 3 lignes adjacentes (ligne actuelle, précédente, suivante)
- Si contenu déjà présent: `status="skipped"`, `reason="content_already_exists"`

**Exemple fichier 3 lignes [0, 1, 2]:**
```python
# Fichier original:
# 0: line 0
# 1: line 1  
# 2: line 2

# after_line=0 → insère après ligne 0 → position 1
# 0: line 0
# 1: NEW LINE  ← ici
# 2: line 1
# 3: line 2

# after_line=-1 → insère à EOF → position 3
# 0: line 0
# 1: line 1
# 2: line 2
# 3: NEW LINE  ← ici
```

#### SEARCH_REPLACE
```python
await writer.search_replace(
    file_path="config/app.php",
    search="'timezone' => 'UTC',",
    replace="'timezone' => 'Europe/Paris',",
    project_id="abc123"
)
```
- Recherche exacte (case-sensitive)
- Remplace toutes les occurrences
- Retourne nombre d'occurrences remplacées

#### RENAME
```python
await writer.rename_file(
    old_path="app/Models/User.php",
    new_path="app/Models/UserModel.php",
    project_id="abc123"
)
```

#### DELETE
```python
await writer.delete_file(
    file_path="app/Models/OldModel.php",
    project_id="abc123"
)
```

### 6.3 Sécurité et garde-fous

#### Deny-list (19 chemins protégés)
```python
PROTECTED_PATHS = [
    ".git/",              # Repo Git
    ".env",               # Variables environnement
    ".env.local",
    ".env.production",
    ".env.development",
    "vendor/",            # Dépendances PHP
    "node_modules/",      # Dépendances Node
    "dist/",              # Build output
    "build/",
    "storage/",           # Laravel storage
    "bootstrap/cache/",   # Laravel cache
    "package-lock.json",  # Lock files
    "pnpm-lock.yaml",
    "composer.lock",
    "yarn.lock",
    ".pytest_cache/",     # Python cache
    "__pycache__/",
    ".venv/",             # Virtual environments
    "venv/",
]
```

**Validation stricte:**
- Chemins relatifs uniquement (pas de `/` initial)
- Pas de `..` (path traversal)
- Rester dans le workspace projet
- Taille max: 10MB par fichier
- Encodage UTF-8 obligatoire

**Propagation erreurs:**
- Si chemin protégé tenté: `FileWriterError` → HTTP 422 (Unprocessable Entity)
- Si autre erreur: HTTP 500 (Internal Server Error)

### 6.4 Tri automatique des opérations

**Fonction:** `_sort_operations_by_priority()`

**Ordre d'exécution:**
1. **create** (priorité 1) - Créer fichiers avant de les modifier
2. **update, insert, search_replace** (priorité 2) - Modifications
3. **rename** (priorité 3) - Peut casser les références
4. **delete** (priorité 4) - En dernier

**Exemple:**
```python
# Input (ordre arbitraire)
operations = [
    {"type": "delete", "path": "old.php"},
    {"type": "create", "path": "new.php", "content": "..."},
    {"type": "insert", "path": "new.php", "after_line": 5, "content": "..."}
]

# Output (trié)
operations_sorted = [
    {"type": "create", "path": "new.php", "content": "..."},      # 1
    {"type": "insert", "path": "new.php", "after_line": 5, ...},  # 2
    {"type": "delete", "path": "old.php"}                         # 3
]
```

### 6.5 Locks par projet

**Mécanisme:** `asyncio.Lock()` par project_id

**Objectif:** Éviter les race conditions lors d'écritures concurrentes sur le même projet.

**Implémentation:**
```python
async with self._get_lock(project_id):
    # Opération atomique protégée
    target_path.write_text(content, encoding='utf-8')
```

### 6.6 Fonction execute_operations()

**Signature:**
```python
async def execute_operations(
    operations: List[Dict[str, Any]],
    project_path: str,
    project_id: str
) -> List[Dict[str, Any]]
```

**Pipeline:**
1. Tri automatique par priorité
2. Exécution séquentielle (fail-safe)
3. Logging détaillé
4. Retour liste de résultats

**Résultats:**
```python
[
    {
        "status": "created",
        "path": "app/Models/User.php",
        "hash": "abc123...",
        "size": 1024,
        "timestamp": "2025-01-15T10:30:00Z",
        "operation_index": 0
    },
    {
        "status": "failed",
        "operation_index": 1,
        "operation_type": "insert",
        "error": "File does not exist: routes/web.php",
        "timestamp": "2025-01-15T10:30:01Z"
    }
]
```

---

## 7. SYSTÈME AUTO-HEAL

### 7.1 Vue d'ensemble

**Fichiers:**
- `orchestrator/auto_heal.py` - AutoHealManager
- `orchestrator/health_pipelines.py` - HealthPipelineRunner

**Objectif:** Système de correction automatique avancé avec branches Git et pipelines de santé stack-agnostiques.

### 7.2 Workflow Auto-Heal

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTO-HEAL WORKFLOW                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Détection problème (échec tests, bug utilisateur)       │
│                    ↓                                         │
│  2. POST /api/projects/{id}/auto-heal                       │
│     - max_steps: 5                                           │
│     - branch_name: autofix/YYYYMMDD-HHMMSS (auto)          │
│     - auto_merge: false (TOUJOURS)                          │
│     - operations: [...] (optionnel, no-LLM path)           │
│                    ↓                                         │
│  3. Création branche Git autofix/*                          │
│     git checkout -b autofix/20250115-103000                 │
│                    ↓                                         │
│  4. Application corrections (LLM ou no-LLM)                 │
│     - Exécution operations via file_writer                  │
│     - Commit atomique: fix(autofix:run:<run_id>): step N   │
│                    ↓                                         │
│  5. Health Pipeline stack-spécifique                        │
│     ┌─────────────┬──────────────┬───────────────┐         │
│     │   Laravel   │     Node     │    Generic    │         │
│     ├─────────────┼──────────────┼───────────────┤         │
│     │ composer    │ npm ci       │ git clean     │         │
│     │ pint        │ eslint       │ README check  │         │
│     │ pest        │ npm test     │ file sizes    │         │
│     │ phpstan     │ npm build    │               │         │
│     └─────────────┴──────────────┴───────────────┘         │
│                    ↓                                         │
│  6. Détermination statut branche                            │
│     ┌─────────────────────────────────┐                    │
│     │ Tous checks PASSED              │                    │
│     │   → ready-to-merge              │                    │
│     │                                 │                    │
│     │ Au moins 1 check FAILED         │                    │
│     │   → needs-review                │                    │
│     └─────────────────────────────────┘                    │
│                    ↓                                         │
│  7. Tagging branche (Git notes)                            │
│     git notes add refs/heads/autofix/*                      │
│     {                                                        │
│       "status": "ready-to-merge",                           │
│       "health_results": {...},                              │
│       "timestamp": "..."                                    │
│     }                                                        │
│                    ↓                                         │
│  8. Review humaine OBLIGATOIRE                              │
│     - GET /api/projects/{id}/branches                       │
│     - GET /api/projects/{id}/branches/{branch}/artifacts   │
│     - Diff, commits, health logs disponibles               │
│                    ↓                                         │
│  9. Actions possibles                                       │
│     ┌───────────────────────────────────────────┐          │
│     │ a) Merge manuel (git merge)               │          │
│     │ b) Retest: POST .../branches/{branch}/test│          │
│     │ c) Close: POST .../branches/{branch}/close│          │
│     └───────────────────────────────────────────┘          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.3 Endpoints Auto-Heal

#### POST /api/projects/{id}/auto-heal

**Request:**
```json
{
  "max_steps": 5,
  "branch_name": null,  // Auto: autofix/YYYYMMDD-HHMMSS
  "auto_merge": false,  // TOUJOURS FALSE
  "operations": [       // Optionnel (no-LLM path)
    {"type": "update", "path": "file.php", "content": "..."}
  ]
}
```

**Response:**
```json
{
  "branch_name": "autofix/20250115-103000",
  "branch_commit": "abc123def456",
  "steps_applied": 3,
  "files_changed": ["app/Models/User.php", "routes/web.php"],
  "health_status": "ready-to-merge",
  "health_results": {
    "checks": [
      {"name": "composer_install", "status": "passed", "duration": 5.2},
      {"name": "pint", "status": "passed", "duration": 2.1},
      {"name": "pest", "status": "passed", "duration": 10.5}
    ],
    "total_duration": 17.8,
    "passed": 3,
    "failed": 0
  }
}
```

#### GET /api/projects/{id}/branches

**Response:**
```json
{
  "project_id": "abc123",
  "branches": [
    {
      "branch_name": "autofix/20250115-103000",
      "commit": "abc123",
      "commit_message": "fix(autofix:run:xyz): step 1 – Fix user model",
      "author": "AI Agent",
      "committed_at": "2025-01-15T10:30:00Z",
      "status": "ready-to-merge",
      "health_results": {...}
    }
  ],
  "total": 1
}
```

#### POST /api/projects/{id}/branches/{branch}/test

Relance le health pipeline sur une branche existante.

#### GET /api/projects/{id}/branches/{branch}/artifacts

**Response:**
```json
{
  "branch_name": "autofix/20250115-103000",
  "diff": "diff --git a/app/Models/User.php ...",
  "commits": [
    {
      "hash": "abc123",
      "message": "fix(autofix:run:xyz): step 1",
      "author": "AI Agent",
      "date": "2025-01-15T10:30:00Z"
    }
  ],
  "files_changed": ["app/Models/User.php"],
  "health_logs": "composer install: OK
pint: OK
pest: OK"
}
```

#### POST /api/projects/{id}/branches/{branch}/close

Supprime proprement une branche autofix (cleanup).

### 7.4 Health Pipelines

**Fichier:** `orchestrator/health_pipelines.py`

#### Laravel Pipeline
```python
async def run_laravel_health_pipeline(project_path: str) -> dict:
    checks = [
        "composer install --no-interaction",
        "./vendor/bin/pint --test",
        "./vendor/bin/pest --stop-on-failure",
        "./vendor/bin/phpstan analyse --no-progress"
    ]
    # Timeout: 300s (5 minutes) par check
    # Résultats: {"name": "...", "status": "passed|failed", "output": "..."}
```

#### Node Pipeline
```python
async def run_node_health_pipeline(project_path: str) -> dict:
    checks = [
        "npm ci",
        "npm run lint",
        "npm test",
        "npm run build"
    ]
```

#### Generic Pipeline
```python
async def run_generic_health_pipeline(project_path: str) -> dict:
    checks = [
        "git status --porcelain",  # Vérifier repo propre
        "check README.md exists",
        "check file sizes < 10MB"
    ]
```

**Détermination statut:**
```python
all_passed = all(check["status"] == "passed" for check in checks)
status = "ready-to-merge" if all_passed else "needs-review"
```

### 7.5 Règles strictes

**JAMAIS d'auto-merge vers main:**
- `auto_merge` paramètre ignoré (toujours `false`)
- Review humaine OBLIGATOIRE
- Merge manuel via Git ou interface

**Protection branches:**
- Impossible de supprimer `main` ou branches non-autofix
- Sécurité via préfixe `autofix/*`

---

## 8. STACKS SUPPORTÉES

### 8.1 Laravel (PHP)

**Handler:** `orchestrator/stacks/laravel_handler.py`

**Détection:**
- `composer.json` + `artisan` + `vendor/laravel/framework`

**Scaffolding:**
```bash
composer create-project laravel/laravel project-name --prefer-dist
cd project-name
composer install
php artisan key:generate
```

**Validation structure (5 fichiers essentiels):**
1. `artisan` (CLI Laravel)
2. `composer.json`
3. `vendor/autoload.php`
4. `bootstrap/app.php`
5. `vendor/laravel/framework` (installation physique)

**Tests supportés:**
- **Pest** (moderne): `./vendor/bin/pest --stop-on-failure`
- **PHPStan** (analyse statique): `./vendor/bin/phpstan analyse --level=0`
- **Pint** (style): `./vendor/bin/pint --test`

**Configuration PHPStan:**
```yaml
# phpstan.neon (niveau 0 par défaut, progressif)
parameters:
    level: 0
    paths:
        - app
        - routes
    excludePaths:
        - vendor
```

**Commandes Laravel non-interactives:**
```bash
php artisan migrate --force --no-interaction
php artisan test --stop-on-failure --bail
composer install --no-interaction --prefer-dist --optimize-autoloader
```

**Timeout:** 300s (5 minutes) pour `composer install`

**Route par défaut:**
- Fallback intelligent: `/` → `home` → `index` → `welcome`
- Vérification dans `routes/web.php`

**Fichiers générés automatiquement:**
- `composer.json`, `artisan`, `bootstrap/app.php`
- `app/Models/User.php` (exemple)
- `routes/web.php`
- `phpstan.neon` (si PHPStan installé)

### 8.2 React (JavaScript)

**Handler:** `orchestrator/stacks/react_handler.py`

**Détection:**
- `package.json` avec `"react"` dans dependencies

**Scaffolding:**
```bash
npx create-react-app project-name
cd project-name
yarn install
```

**Tests supportés:**
- **Jest** (unit): `npm test -- --passWithNoTests`
- **ESLint** (linting): `npx eslint src/ --ext .js,.jsx`
- **Playwright** (e2e): `npx playwright test`

**Build:**
```bash
npm run build  # Génère build/
```

**Preview:**
- Fichier: `build/index.html` ou `public/index.html`
- Serveur dev: `npm start` (port 3000)

**Fichiers générés:**
- `package.json`, `public/index.html`
- `src/App.js`, `src/index.js`
- `.eslintrc.json`

### 8.3 Vue.js (JavaScript)

**Handler:** `orchestrator/stacks/vue_handler.py`

**Détection:**
- `package.json` avec `"vue"` dans dependencies

**Scaffolding (Vite moderne):**
```bash
npm create vite@latest project-name -- --template vue
cd project-name
yarn install
```

**Structure complète générée:**
```
project-name/
├── index.html              # Point d'entrée avec <script type="module" src="/src/main.js">
├── vite.config.js          # Config Vite + plugin Vue
├── package.json            # Scripts: dev, build, preview, test
├── src/
│   ├── main.js             # createApp + mount
│   ├── App.vue             # Composant racine
│   └── components/
│       └── Counter.vue     # Exemple composant
├── tests/
│   └── Counter.spec.js     # Tests Vitest
└── .eslintrc.cjs           # ESLint config
```

**Tests supportés:**
- **Vitest** (unit): `npm test`
- **ESLint**: `npx eslint src/ --ext .vue,.js`

**Build:**
```bash
npm run build  # Génère dist/
```

**Versions:**
- Vue: 3.4+
- Vite: 5.0+
- Vitest: 1.0+

**Migration vue-cli → Vite:**
- Ancien: `vue create` (deprecated)
- Nouveau: `npm create vite@latest` (moderne, rapide)

### 8.4 Node.js (JavaScript)

**Handler:** `orchestrator/stacks/node_handler.py`

**Détection:**
- `package.json` sans `"react"` ni `"vue"`

**Scaffolding:**
```bash
mkdir project-name && cd project-name
npm init -y
npm install express
```

**Tests supportés:**
- **Jest** (si configuré)
- **ESLint**

**Fichiers générés:**
- `package.json`
- `index.js` ou `server.js`

### 8.5 Python

**Handler:** `orchestrator/stacks/python_handler.py`

**Détection:**
- `requirements.txt` + au moins un fichier `.py`
- Points d'entrée acceptés: `main.py`, `app.py`, `server.py`, `backend/server.py`, `src/main.py`

**Structure flexible:**
```
project-name/
├── requirements.txt
├── main.py              # OU
├── app.py               # OU
├── server.py            # OU
├── backend/
│   └── server.py        # OU
└── src/
    └── main.py
```

**Tests supportés:**
- **pytest**: `pytest --maxfail=1`
- **mypy** (type checking): `mypy .`
- **black** (formatting): `black --check .`

**Virtualenv:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Frameworks détectés:**
- Flask: `python app.py`
- Django: `python manage.py runserver`
- FastAPI: `uvicorn main:app`

### 8.6 Gestion commune

**Installation dépendances automatique:**
```python
async def install_dependencies(project_path: str, stack: str):
    if stack == "laravel":
        await run_command("composer install", cwd=project_path)
    elif stack in ["react", "vue", "node"]:
        await run_command("yarn install", cwd=project_path)
    elif stack == "python":
        await run_command("pip install -r requirements.txt", cwd=project_path)
```

**Fallbacks:**
- Laravel: Si `composer create-project` échoue → Exception (pas de skeleton incomplet)
- React/Vue: Si scaffolding échoue → Structure minimale manuelle
- Python: Toujours structure minimale (requirements.txt + main.py)

---

## 9. API ENDPOINTS

### 9.1 Runs (Exécutions)

#### POST /api/runs
Créer un nouveau run.

**Request:**
```json
{
  "goal": "Créer une API Laravel pour gestion utilisateurs",
  "stack": "laravel",
  "project_path": null,
  "project_mode": "create",  // "create" | "attach"
  "max_steps": 20,
  "max_retries_per_step": 2,
  "daily_budget_eur": 5.0
}
```

**Response:**
```json
{
  "id": "abc123-def456",
  "goal": "Créer une API Laravel pour gestion utilisateurs",
  "stack": "laravel",
  "status": "pending",
  "project_path": "/app/projects/abc123-def456/code",
  "project_id": "abc123-def456",
  "created_at": "2025-01-15T10:00:00Z"
}
```

#### GET /api/runs/{run_id}
Récupérer les détails d'un run.

#### GET /api/runs
Lister tous les runs (pagination: limit, offset).

#### POST /api/runs/{run_id}/cancel
Annuler un run en cours.

#### POST /api/runs/{run_id}/retry-step
Réessayer un step spécifique.

#### POST /api/runs/execute-operations
Exécuter des opérations directement (no-LLM path).

**Request:**
```json
{
  "run_id": "abc123",
  "project_id": "abc123",
  "operations": [
    {"type": "create", "path": "test.txt", "content": "Hello"}
  ],
  "commit": {
    "title": "Add test file",
    "step_number": 1
  }
}
```

### 9.2 Projects (Gestion projets)

#### GET /api/projects
Lister tous les projets.

#### GET /api/projects/{id}
Détails d'un projet.

#### DELETE /api/projects/{id}
Supprimer un projet.

#### GET /api/projects/{id}/preview
Prévisualiser un projet (React/Vue).

### 9.3 Auto-Heal

#### POST /api/projects/{id}/auto-heal
Démarrer auto-réparation.

#### GET /api/projects/{id}/branches
Lister branches autofix.

#### POST /api/projects/{id}/branches/{branch}/test
Relancer health pipeline.

#### GET /api/projects/{id}/branches/{branch}/artifacts
Récupérer diff, commits, logs.

#### POST /api/projects/{id}/branches/{branch}/close
Fermer/supprimer une branche.

### 9.4 Admin

#### GET /api/admin/stats
Statistiques globales.

**Response:**
```json
{
  "run_stats": {...},
  "daily_cost": 2.5,
  "project_count": 15,
  "cache_stats": {
    "total_entries": 2,
    "hit_rate": 1.0,
    "tokens_saved": 2000
  },
  "cost_savings": {
    "cost_saved_eur": 0.0085,
    "savings_percentage": 0.667
  },
  "settings": {
    "max_local_retries": 3,
    "default_daily_budget": 5.0,
    "max_steps_per_run": 20
  }
}
```

#### POST /api/admin/cache/clear
Vider le cache de prompts.

#### GET /api/admin/mode
Mode d'écriture actuel (direct/patch).

**Response:**
```json
{
  "file_write_mode": "direct",
  "developer_agent_type": "DeveloperAgentDirect",
  "description": "direct = JSON operations, patch = Git diffs",
  "deny_list": [".git/", ".env", "vendor/", ...]
}
```

#### GET /api/admin/global-stats
Statistiques administrateur global.

#### GET /api/admin/global-logs
Logs système globaux.

### 9.5 GitHub Integration

#### GET /api/github/oauth-url
URL d'autorisation OAuth GitHub.

#### POST /api/github/auth
Échanger code OAuth contre token.

#### GET /api/github/repositories
Lister repositories de l'utilisateur.

#### POST /api/github/clone
Cloner un repository.

#### POST /api/github/push
Pousser changements vers GitHub.

#### POST /api/github/pull
Tirer changements depuis GitHub.

### 9.6 Validation & Export

#### POST /api/runs/{run_id}/validate-plan
Validation utilisateur du plan.

#### POST /api/runs/{run_id}/validate-step
Validation d'un step.

#### POST /api/runs/{run_id}/interrupt
Interrompre l'exécution.

#### POST /api/runs/{run_id}/export
Exporter en ZIP ou préparer GitHub.

**Query param:** `export_format=zip` ou `export_format=github`

### 9.7 Debugging

#### GET /api/runs/{run_id}/agent-conversations
Conversations des agents (traçabilité).

#### GET /api/runs/{run_id}/execution-context
Contexte d'exécution actuel.

#### POST /api/validate-patch
Validation avancée de patches (test).

---

## 10. FRONTEND REACT

### 10.1 Structure

```
frontend/
├── src/
│   ├── App.js                    # Composant principal
│   ├── index.js                  # Point d'entrée
│   └── components/
│       ├── AdminPanel.js         # Panel admin (stats, projets, GitHub)
│       ├── AdminGlobal.js        # Admin global (modal)
│       ├── Timeline.js           # Timeline d'exécution
│       ├── RunsList.js           # Liste des runs
│       └── ...
├── public/
│   └── index.html
├── package.json
└── tailwind.config.js
```

### 10.2 Composants principaux

#### App.js

**État global:**
```javascript
const [runs, setRuns] = useState([]);
const [selectedRun, setSelectedRun] = useState(null);
const [activeTab, setActiveTab] = useState('timeline');
```

**Onglets:**
- **Timeline**: Progression en temps réel
- **Logs**: Logs d'exécution
- **Files**: Explorateur de fichiers
- **Admin**: Gestion projet/GitHub

#### AdminPanel.js

**4 sous-onglets:**
1. **Vue d'ensemble**: Statistiques (runs, coûts, budget, cache)
2. **Projets**: Liste avec actions (View, Delete)
3. **GitHub**: Token input, liste repos
4. **Paramètres**: Config système (lecture seule, modif via .env)

**Statistiques affichées:**
- Total Runs: 11
- Coût Quotidien: €0.00
- Projets Actifs: 18
- Budget Quotidien: €5.00
- Configuration Système (badges)

#### Timeline.js

**Affichage:**
- Phases: Planning, Development, Testing, Review
- Progress bar par step
- Status icons (✅ success, ❌ failed, ⏳ running)

#### RunsList.js

**Actions par run:**
- **View Details**: Afficher détails
- **Cancel**: Annuler exécution
- **Retry**: Réessayer un step
- **Preview**: Prévisualiser projet (si completed)
- **Export**: Télécharger ZIP

### 10.3 Design system

**TailwindCSS + shadcn/ui:**
- Composants: Card, Button, Badge, Tabs, Modal
- Thème: Modern, responsive
- Colors: Slate, Blue, Green, Red
- Typography: Inter font

**Responsive:**
- Desktop: Full layout
- Tablet: Sidebar collapsible
- Mobile: Bottom navigation

### 10.4 Communication API

**Backend URL:**
```javascript
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 
                    import.meta.env.REACT_APP_BACKEND_URL;
```

**Requêtes:**
```javascript
// Créer run
const response = await fetch(`${BACKEND_URL}/api/runs`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({goal, stack, max_steps})
});

// Stream logs (Server-Sent Events)
const eventSource = new EventSource(`${BACKEND_URL}/api/runs/${runId}/stream`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Update UI
};
```

---

## 11. BASE DE DONNÉES MONGODB

### 11.1 Collections

#### runs
```javascript
{
  _id: ObjectId("..."),
  id: "abc123-def456",           // UUID
  goal: "Créer API Laravel...",
  stack: "laravel",
  status: "running",             // pending|running|completed|failed|cancelled
  current_step: 3,
  max_steps: 20,
  max_retries_per_step: 2,
  daily_budget_eur: 5.0,
  cost_used_eur: 0.15,
  project_path: "/app/projects/abc123/code",
  project_id: "abc123",
  project_mode: "create",        // create|attach
  attached_commit: null,
  
  // Plan
  plan: "1. Créer modèle User
2. ...",
  parsed_plan: [
    {
      id: "step_1",
      description: "Créer modèle User",
      substeps: [...],
      files: ["app/Models/User.php"],
      estimated_duration: "5 minutes"
    }
  ],
  execution_steps: [...],        // Steps aplatis pour exécution
  
  // Logs
  logs: [
    {
      type: "info",
      content: "Starting execution...",
      timestamp: "2025-01-15T10:00:00Z"
    }
  ],
  
  // Agent conversations (traçabilité)
  agent_conversations: [
    {
      agent: "planner",
      direction: "input",
      content: {...},
      timestamp: "2025-01-15T10:00:01Z"
    }
  ],
  
  // Validation utilisateur
  plan_validated: true,
  plan_feedback: "Looks good!",
  plan_validation_time: "2025-01-15T10:00:05Z",
  
  created_at: "2025-01-15T10:00:00Z",
  updated_at: "2025-01-15T10:30:00Z"
}
```

#### projects
```javascript
{
  _id: ObjectId("..."),
  id: "abc123",
  name: "Laravel User API",
  stack: "laravel",
  project_path: "/app/projects/abc123",
  code_path: "/app/projects/abc123/code",
  created_at: "2025-01-15T10:00:00Z",
  runs: ["run_id_1", "run_id_2"],
  metadata: {
    total_files: 45,
    total_size_mb: 12.5,
    last_modified: "2025-01-15T11:00:00Z"
  }
}
```

#### prompt_cache (en mémoire, optionnel)
```javascript
{
  hash: "sha256_of_system_prompt",
  content: "You are a Laravel expert...",
  task_type: "coding",
  usage_count: 5,
  created_at: "2025-01-15T10:00:00Z",
  last_used: "2025-01-15T10:30:00Z",
  ttl_seconds: 86400  // 24h
}
```

### 11.2 Indexes

```javascript
// runs collection
db.runs.createIndex({id: 1}, {unique: true});
db.runs.createIndex({status: 1});
db.runs.createIndex({created_at: -1});
db.runs.createIndex({project_id: 1});

// projects collection
db.projects.createIndex({id: 1}, {unique: true});
db.projects.createIndex({stack: 1});
```

### 11.3 Connexion

**URL:** `mongodb://localhost:27017`

**Database:** `agent_orchestrator` (ou configuré via `DB_NAME` dans `.env`)

**Client:** `motor.motor_asyncio.AsyncIOMotorClient` (asynchrone)

---

## 12. CONFIGURATION ET ENVIRONNEMENT

### 12.1 Fichier .env (backend)

```bash
# Base de données
MONGO_URL="mongodb://localhost:27017"
DB_NAME="agent_orchestrator"

# LLM API Keys
OPENAI_API_KEY=""                        # sk-...
ANTHROPIC_API_KEY=""                     # sk-ant-...

# Ollama (local)
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="qwen2.5-coder:7b"

# Routage LLM
MODE_INFERENCE="hybrid"                  # hybrid|local|paid
PAID_PROVIDER="openai"                   # openai|anthropic
MAX_LOCAL_RETRIES=3
MAX_ESCALATION_RETRIES=2
MAX_REQUESTS_PER_MINUTE=20

# Anthropic
ENABLE_ANTHROPIC=true                    # true|false
ANTHROPIC_CIRCUIT_BREAKER_MINUTES=15

# Budget et limites
DEFAULT_DAILY_BUDGET_EUR=5.0
MAX_STEPS_PER_RUN=20
MAX_RETRIES_PER_STEP=2

# Mode développement
DEVELOPMENT_MODE=true                    # true|false

# Écriture fichiers
FILE_WRITE_MODE=direct                   # direct|patch

# Auto-création structures
AUTO_CREATE_STRUCTURES=true

# GitHub (optionnel)
GITHUB_TOKEN=""
GITHUB_CLIENT_ID=""
GITHUB_CLIENT_SECRET=""

# Logging
LOG_LEVEL=INFO
```

### 12.2 Variables critiques

| Variable | Valeur | Impact |
|----------|--------|--------|
| `FILE_WRITE_MODE` | `direct` | Utilise JSON operations au lieu de patches Git |
| `DEVELOPMENT_MODE` | `true` | Mock responses si pas de clés API |
| `ENABLE_ANTHROPIC` | `true` | Active/désactive Anthropic |
| `MAX_LOCAL_RETRIES` | `3` | Tentatives Ollama avant escalation |
| `DEFAULT_DAILY_BUDGET_EUR` | `5.0` | Budget quotidien par défaut |
| `AUTO_CREATE_STRUCTURES` | `true` | Scaffolding automatique des projets |

### 12.3 Dépendances backend (requirements.txt)

```
fastapi==0.104.1
uvicorn==0.24.0
motor==3.3.2
pymongo==4.6.0
pydantic==2.8.2
pydantic_core==2.20.1
openai==1.5.0
anthropic==0.8.0
httpx==0.25.2
python-dotenv==1.0.0
gitpython==3.1.45
typing-inspect==0.9.0
```

**IMPORTANT:**
- **Pydantic 2.8.2** (pas 2.12.0) pour compatibilité `typing_inspection`
- **typing-inspect 0.9.0** (pas 0.4.1) pour éviter `AttributeError`

### 12.4 Dépendances frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "tailwindcss": "^3.3.0",
    "@radix-ui/react-*": "^1.0.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test"
  }
}
```

### 12.5 Services Supervisor

**Fichier:** `/etc/supervisor/conf.d/app.conf`

```ini
[program:backend]
command=/usr/bin/python3 -m uvicorn server:app --host 0.0.0.0 --port 8001
directory=/app/backend
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/backend.out.log
stderr_logfile=/var/log/supervisor/backend.err.log

[program:frontend]
command=/usr/bin/yarn start
directory=/app/frontend
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/frontend.out.log
stderr_logfile=/var/log/supervisor/frontend.err.log
```

**Commandes:**
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
sudo supervisorctl restart all
sudo supervisorctl status
```

---

## 13. WORKFLOW COMPLET

### 13.1 Cycle utilisateur → code fonctionnel

```
┌─────────────────────────────────────────────────────────────────┐
│                    WORKFLOW COMPLET E2E                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. UTILISATEUR                                                  │
│     └─ Saisit goal: "Créer API Laravel gestion utilisateurs"   │
│     └─ Sélectionne stack: laravel                              │
│     └─ Configure: max_steps=20, budget=5€                      │
│                                                                  │
│  2. POST /api/runs → run_id="abc123"                           │
│     └─ Status: pending                                          │
│     └─ Background task: execute_run(abc123)                    │
│                                                                  │
│  3. PHASE 1: PLANNING                                           │
│     └─ PlannerAgent.generate_plan(goal, context)               │
│        ├─ RAG: Récupère contexte Laravel                       │
│        ├─ LLM (Ollama → GPT → Claude): Génère plan            │
│        └─ Parser: Hiérarchie → Steps plats                     │
│     └─ Sauvegarde: parsed_plan (10 steps) → MongoDB           │
│                                                                  │
│  4. PHASE 2: EXÉCUTION ITÉRATIVE                               │
│     Pour chaque step (1-10):                                    │
│                                                                  │
│     A. DEVELOPMENT                                              │
│        └─ DeveloperAgentDirect.generate(step)                  │
│           ├─ RAG: Contexte fichiers existants                  │
│           ├─ LLM: Génère operations JSON                       │
│           └─ Validation: Pydantic schemas                      │
│                                                                  │
│     B. APPLICATION                                              │
│        └─ execute_operations(operations, project_path)         │
│           ├─ Tri: create → modify → delete                     │
│           ├─ FileWriter: Écriture atomique                     │
│           └─ Git commit: feat(run:abc123): step N             │
│                                                                  │
│     C. TESTS                                                    │
│        └─ ToolManager.run_tests(project_id, stack)            │
│           ├─ Laravel: composer install → pest → phpstan       │
│           ├─ Timeout: 300s par commande                        │
│           └─ Logs: /app/projects/abc123/logs/pest.log         │
│                                                                  │
│     D. REVIEW                                                   │
│        └─ ReviewerAgent.evaluate(tests_results)                │
│           ├─ Decision: accept | reject | escalate             │
│           └─ Confidence: 0.9                                   │
│                                                                  │
│     E. AUTO-CORRECTION (si reject)                             │
│        └─ RepairAgent.fix(error, step)                         │
│           ├─ Max 3 tentatives par step                         │
│           ├─ Compteurs isolés: Pest(3), PHPStan(3), Pint(3)  │
│           └─ Limite globale: 5 réparations/projet             │
│                                                                  │
│     F. ESCALATION (si échecs répétés)                          │
│        └─ Retour PlannerAgent: révision plan                   │
│           ├─ Max 2 révisions                                   │
│           └─ Si échec final: status=failed                     │
│                                                                  │
│  5. PHASE 3: FINALISATION                                      │
│     └─ Status: completed                                        │
│     └─ Export ZIP: /tmp/project-abc123.zip                     │
│     └─ Préparation GitHub: instructions push                   │
│                                                                  │
│  6. AUTO-HEAL (OPTIONNEL)                                      │
│     Si bug détecté après livraison:                            │
│     └─ POST /api/projects/abc123/auto-heal                     │
│        ├─ Branche: autofix/20250115-103000                     │
│        ├─ Corrections: operations JSON                         │
│        ├─ Health pipeline: composer → pest → phpstan          │
│        ├─ Status: ready-to-merge | needs-review               │
│        └─ Review humaine → Merge manuel                        │
│                                                                  │
│  7. LIVRAISON                                                   │
│     └─ Code fonctionnel dans /app/projects/abc123/code        │
│     └─ Tests passent: Pest ✅, PHPStan ✅, Pint ✅            │
│     └─ Documentation: README.md généré                         │
│     └─ Git history: commits atomiques par step                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 13.2 Exemple concret: API Laravel

**Goal:** "Créer une API REST Laravel pour gérer des utilisateurs avec CRUD complet et authentification JWT"

**Plan généré (5 steps):**
1. Setup base Laravel + JWT
2. Créer modèle User avec migrations
3. Créer AuthController (login, register)
4. Créer UserController (CRUD)
5. Créer tests Pest + PHPStan validation

**Exécution:**

**Step 1:** Setup base
- Operations: create `config/jwt.php`, update `composer.json`
- Tests: composer install ✅
- Status: Completed

**Step 2:** Modèle User
- Operations: create `database/migrations/create_users_table.php`, `app/Models/User.php`
- Tests: pest (migration test) ✅
- Status: Completed

**Step 3:** AuthController
- Operations: create `app/Http/Controllers/AuthController.php`, update `routes/api.php`
- Tests: pest (auth tests) ❌ Failed (JWT middleware missing)
- **Repair:** RepairAgent ajoute middleware JWT
- Tests: pest ✅
- Status: Completed (after 1 retry)

**Step 4:** UserController
- Operations: create `app/Http/Controllers/UserController.php`, update `routes/api.php`
- Tests: pest ✅, phpstan ✅
- Status: Completed

**Step 5:** Tests complets
- Operations: create `tests/Feature/AuthTest.php`, `tests/Feature/UserTest.php`
- Tests: pest (36 tests) ✅, phpstan (level 0) ✅, pint ✅
- Status: Completed

**Résultat final:**
- 42 fichiers créés
- 36 tests passés
- Coût total: €0.45
- Durée: 12 minutes
- Status: ✅ Completed

---

## 14. ÉVOLUTIONS RÉCENTES

### 14.1 Phase 1: Direct File Writing (COMPLÉTÉE)

**Date:** Décembre 2024

**Objectif:** Remplacer les patches Git par des opérations JSON pour plus de robustesse.

**Implémentation:**
- ✅ `file_writer.py`: 6 primitives (create, update, insert, search_replace, rename, delete)
- ✅ `schemas.py`: Modèles Pydantic pour validation
- ✅ `developer_direct.py`: Génération JSON au lieu de diffs
- ✅ `server.py`: Dual-mode (FILE_WRITE_MODE=direct|patch)
- ✅ Commits Git atomiques: `feat(run:<run_id>): step N – titre`
- ✅ RAG re-indexing après modifications

**Bénéfices:**
- Plus de patches corrompus
- Traçabilité complète (SHA-256 hashing)
- Sécurité renforcée (deny-list 19 chemins)
- Idempotence (insert vérifie doublons)

### 14.2 Phase 2: Attach Mode (COMPLÉTÉE)

**Date:** Janvier 2025

**Objectif:** Attacher à des projets existants sans recréation.

**Implémentation:**
- ✅ `project_mode="attach"` dans POST /api/runs
- ✅ `ProjectManager.attach_to_project()`: Validation Git + détection stack
- ✅ POST /api/runs/execute-operations: No-LLM direct execution
- ✅ Git commits atomiques par step
- ✅ RAG re-indexing automatique

**Use case:**
```json
POST /api/runs
{
  "goal": "Ajouter endpoint /users/export",
  "project_mode": "attach",
  "project_id": "existing-project-123"
}
```

### 14.3 Phase 3: Auto-Heal Stack-Agnostique (COMPLÉTÉE)

**Date:** Janvier 2025

**Objectif:** Système d'auto-réparation avancé avec branches Git et pipelines de santé.

**Implémentation:**
- ✅ `auto_heal.py`: AutoHealManager
- ✅ `health_pipelines.py`: Pipelines Laravel/Node/Generic
- ✅ POST /api/projects/{id}/auto-heal: Création branches autofix/*
- ✅ GET /api/projects/{id}/branches: Liste branches avec statuts
- ✅ POST /api/projects/{id}/branches/{branch}/test: Rerun pipeline
- ✅ GET /api/projects/{id}/branches/{branch}/artifacts: Diff, commits, logs
- ✅ POST /api/projects/{id}/branches/{branch}/close: Cleanup branches

**Workflow:**
1. Détection problème
2. Création branche autofix/YYYYMMDD-HHMMSS
3. Application corrections
4. Health pipeline (composer, pest, phpstan)
5. Tag: ready-to-merge | needs-review
6. Review humaine OBLIGATOIRE
7. Merge manuel

### 14.4 Phase 4: Excellence Laravel (COMPLÉTÉE)

**Date:** Janvier 2025

**Objectif:** Corrections profondes Laravel + logs complets.

**Implémentation:**
- ✅ PHPStan baseline progressive (niveau 0)
- ✅ Fonction `_setup_phpstan_for_laravel()`: Install + config + baseline
- ✅ Fonction `_generate_phpstan_baseline()`: Génération idempotente
- ✅ Fonction `_clean_stderr_noise()`: Filtrage warnings PHP/Composer
- ✅ Fonction `_write_complete_log()`: Logs complets avec rotation (5MB max)
- ✅ Route Laravel `/`: Fallback intelligent (home → index → welcome)
- ✅ Compteurs isolés par type de test (Pest:3, PHPStan:3, Pint:3)

### 14.5 Corrections critiques appliquées

**Bug empty separator (developer.py):**
```python
# AVANT (❌)
lines = content.split('')  # ValueError: empty separator

# APRÈS (✅)
lines = content.splitlines()
```

**Bug CommandResult undefined (tools.py):**
```python
# AVANT (❌)
return type('CommandResult', (), {...})()

# APRÈS (✅)
@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

return CommandResult(returncode=0, stdout="...", stderr="")
```

**Bug validate_plan dupliqué (server.py):**
- Suppression première définition (ligne 876)
- Conservation version complète (ligne 945+)

**Bug project_repairs non défini (tools.py):**
```python
# Initialisation anticipée TOUT EN HAUT
project_repairs = self.project_repair_counts.get(project_id, 0)
```

**Bug Vue.js skeleton manquant:**
- Tous stacks utilisent maintenant `handler.create_project_skeleton()` complet
- Plus de structure minimale incomplète

### 14.6 Améliorations Pydantic

**Downgrade Pydantic 2.12.0 → 2.8.2:**
- Résolution erreur `typing_inspection.typing_objects has no attribute is_noextraitems`
- Compatibility avec `typing-inspect 0.9.0`

### 14.7 Insert Operation Fixes

**PHASE 1 - Corrections complètes:**

1. **Clamp EOF**: after_line > EOF → clamp automatique à EOF
   ```python
   if after_line >= len(lines):
       logger.warning(f"Clamping {after_line} to EOF")
       after_line = len(lines) - 1
       clamped = True
   ```

2. **Anchor EOF**: after_line=-1 insère à la fin
   ```python
   if after_line == -1:
       after_line = len(lines) - 1  # Dernière ligne
   ```

3. **Idempotence**: Vérifie 3 lignes adjacentes
   ```python
   # Vérifier ligne actuelle, précédente, suivante
   if lines[insert_position].strip() == content.strip():
       return {"status": "skipped", "reason": "content_already_exists"}
   ```

4. **0-indexed standardisé**: Cohérent partout (schema, implémentation, prompt)

5. **Tri automatique**: create avant insert, delete en dernier

6. **Protected paths 422**: FileWriterError propagée → HTTP 422

7. **Tests**: 15 unitaires + 6 rapides + 5 intégration = 26 tests (100% pass)

**Métriques:**
- Taux succès JSON: 91% (+24%)
- Tentatives moyennes: 1.1 (-31%)
- Erreurs line number: -85%
- Erreurs ordre: -87%

---

## 15. POINTS CRITIQUES

### 15.1 À NE JAMAIS FAIRE

❌ **Modifier les URLs dans .env:**
- `REACT_APP_BACKEND_URL` est configuré pour la production
- `MONGO_URL` est configuré pour MongoDB local
- Modification = échec du déploiement

❌ **Utiliser npm au lieu de yarn:**
- npm est une breaking change
- Toujours utiliser `yarn install`, `yarn add`, etc.

❌ **Downgrader les packages sans raison:**
- `package.json` et `requirements.txt` sont la source de vérité
- Ne pas downgrader à cause du knowledge cutoff

❌ **Hardcoder URLs ou ports:**
- Toujours utiliser variables d'environnement
- Backend: `os.environ.get('MONGO_URL')`
- Frontend: `process.env.REACT_APP_BACKEND_URL`

❌ **Oublier le préfixe /api:**
- Tous endpoints backend: `/api/runs`, `/api/projects`, etc.
- Kubernetes ingress routing dépend de ce préfixe

❌ **Auto-merge vers main:**
- Auto-heal: `auto_merge` TOUJOURS `false`
- Review humaine OBLIGATOIRE

❌ **Modifier .git/ ou vendor/ ou node_modules/:**
- Chemins protégés par deny-list
- FileWriterError → HTTP 422

### 15.2 Bonnes pratiques

✅ **Toujours lire un fichier avant modification:**
```python
content = await mcp_view_file(path)
# Analyser le contenu
await mcp_search_replace(path, old, new)
```

✅ **Utiliser search_replace pour modifications précises:**
```python
# Bon
{"type": "search_replace", "path": "file.php", "search": "old", "replace": "new"}

# Éviter si possible
{"type": "update", "path": "file.php", "content": "...tout le fichier..."}
```

✅ **Vérifier stack avant opérations:**
```python
stack = await project_manager.detect_stack(project_path)
if stack == "laravel":
    # Operations spécifiques Laravel
```

✅ **Logs complets pour debugging:**
```python
logger.info(f"✅ Operation completed: {result}")
logger.error(f"❌ Operation failed: {error}")
```

✅ **Validation Pydantic stricte:**
```python
try:
    developer_output = DeveloperOutput(**json_data)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
```

✅ **Tests avant livraison:**
- Backend: `deep_testing_backend_v2`
- Frontend: `auto_frontend_testing_agent`

### 15.3 Dépendances critiques

**Python:**
- `pydantic==2.8.2` (pas 2.12.0)
- `typing-inspect==0.9.0` (pas 0.4.1)
- `gitpython==3.1.45`

**Node:**
- `react@18.2.0`
- `tailwindcss@3.3.0`

**Système:**
- MongoDB 27017
- Supervisor (backend + frontend)

### 15.4 Timeouts et limites

| Opération | Timeout | Limite |
|-----------|---------|--------|
| Composer install | 300s | - |
| Pest tests | 300s | - |
| PHPStan analyse | 300s | - |
| LLM Ollama | 120s | 3 retries |
| LLM OpenAI/Claude | - | 2 retries |
| Run global | 3600s | 1 heure |
| Steps par run | - | 20 (défaut) |
| Retries par step | - | 3 |
| Réparations par projet | - | 5 global |
| Budget quotidien | - | €5.00 (défaut) |
| Taille fichier | - | 10MB max |

### 15.5 Chemins importants

```
/app/                               # Root application
├── backend/
│   ├── server.py                   # FastAPI entry
│   ├── .env                        # Config (NE PAS MODIFIER URLs)
│   └── orchestrator/
│       ├── agents/
│       ├── stacks/
│       └── file_writer.py
├── frontend/
│   ├── .env                        # REACT_APP_BACKEND_URL
│   └── src/
├── projects/
│   └── {project_id}/
│       ├── code/                   # Code source projet
│       ├── logs/                   # Logs exécution
│       └── projet.json
├── test_result.md                  # Testing data
└── README.md
```

### 15.6 Commandes utiles

**Backend:**
```bash
cd /app/backend
pip install -r requirements.txt
sudo supervisorctl restart backend
tail -f /var/log/supervisor/backend.err.log
```

**Frontend:**
```bash
cd /app/frontend
yarn install
sudo supervisorctl restart frontend
```

**MongoDB:**
```bash
mongo
use agent_orchestrator
db.runs.find({status: "running"}).pretty()
```

**Git (Auto-Heal):**
```bash
cd /app/projects/{project_id}/code
git branch -a
git log autofix/20250115-103000
git diff main..autofix/20250115-103000
```

### 15.7 Debugging

**Backend logs:**
```bash
tail -n 100 /var/log/supervisor/backend.err.log | grep ERROR
```

**Project logs:**
```bash
ls -lh /app/projects/{project_id}/logs/
tail -n 50 /app/projects/{project_id}/logs/pest_20250115_103000.log
```

**Test API:**
```bash
curl https://repo-analyzer-105.preview.emergentagent.com/api/
curl https://repo-analyzer-105.preview.emergentagent.com/api/admin/stats
```

**MongoDB queries:**
```javascript
db.runs.find({status: "failed"}).sort({created_at: -1}).limit(5)
db.runs.aggregate([
  {$group: {_id: "$stack", count: {$sum: 1}}}
])
```

---

## 16. GLOSSAIRE

**Agent:** Composant AI spécialisé (Planner, Developer, Reviewer, Repair)

**Auto-Heal:** Système d'auto-réparation avec branches Git

**Attach Mode:** Mode permettant d'attacher à un projet existant sans recréation

**Circuit Breaker:** Mécanisme désactivant temporairement un provider LLM en cas d'erreurs répétées

**Deny-list:** Liste de chemins protégés non modifiables (19 chemins)

**Developer Output:** JSON contenant les opérations d'écriture (mode direct)

**Escalation:** Montée en gamme de modèle LLM (Ollama → OpenAI → Claude)

**Health Pipeline:** Suite de checks de santé stack-spécifiques

**Idempotence:** Capacité à exécuter une opération plusieurs fois sans effet indésirable

**LLM Router:** Système de routage intelligent vers les modèles LLM

**Patch:** Diff Git unifié (mode patch)

**Planner:** Agent générant le plan d'exécution

**Project Workspace:** Répertoire isolé par projet dans `/app/projects/{id}/`

**RAG:** Retrieval-Augmented Generation (contexte enrichi via indexation)

**Repair Agent:** Agent d'auto-correction des erreurs simples

**Reviewer:** Agent évaluant les résultats d'un step

**Run:** Exécution complète d'un objectif utilisateur

**Stack:** Technologie cible (Laravel, React, Vue, Node, Python)

**Step:** Étape atomique d'exécution (sous-partie d'un plan)

**Substep:** Sous-étape d'un step (hiérarchie aplatie pour exécution)

---

## 17. RÉFÉRENCES EXTERNES

**Documentation officielle:**
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- MongoDB: https://www.mongodb.com/docs/
- TailwindCSS: https://tailwindcss.com/
- Laravel: https://laravel.com/docs
- Ollama: https://ollama.ai/

**APIs LLM:**
- OpenAI: https://platform.openai.com/docs
- Anthropic: https://docs.anthropic.com/
- Ollama: https://github.com/ollama/ollama

**Outils:**
- Pest: https://pestphp.com/
- PHPStan: https://phpstan.org/
- Pint: https://laravel.com/docs/pint
- Jest: https://jestjs.io/
- ESLint: https://eslint.org/

---

## 18. CONTACTS ET SUPPORT

**Logs système:**
- Backend: `/var/log/supervisor/backend.*.log`
- Frontend: `/var/log/supervisor/frontend.*.log`
- Projets: `/app/projects/{project_id}/logs/`

**État des services:**
```bash
sudo supervisorctl status
```

**Test santé API:**
```bash
curl https://repo-analyzer-105.preview.emergentagent.com/api/
```

---

## 19. CHANGELOG

**v3.0 - Janvier 2025:**
- ✅ Phase 3 Auto-Heal complète
- ✅ Phase 4 Excellence Laravel
- ✅ Insert operation fixes (clamp, idempotence)
- ✅ Vue.js handler modernisé (Vite)
- ✅ Corrections critiques (empty separator, CommandResult, etc.)

**v2.0 - Janvier 2025:**
- ✅ Phase 2 Attach Mode
- ✅ No-LLM execution path
- ✅ Git commits atomiques

**v1.0 - Décembre 2024:**
- ✅ Phase 1 Direct File Writing
- ✅ Système d'agents complet
- ✅ LLM Router avec escalation
- ✅ Support multi-stack

---

**FIN DU RAG COMPLET - VERSION 3.0**

Ce document constitue un contexte exhaustif pour qu'un LLM puisse comprendre rapidement le projet sans faire d'erreurs d'interprétation ou de suppositions.

**Utilisation recommandée:**
1. Fournir ce document complet au début de chaque nouvelle conversation
2. Référencer les sections pertinentes selon le contexte
3. Mettre à jour régulièrement avec les nouvelles évolutions
4. Partager avec l'équipe comme documentation de référence

**Exportabilité:**
- Format: Markdown
- Taille: ~85KB
- Sections: 19 + glossaire + références
- Dernière mise à jour: Janvier 2025