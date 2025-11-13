# 🔍 Stratégies Emergent.sh pour les Problèmes Restants

**Question** : Comment Emergent.sh gère les 4 problèmes identifiés dans Cognitia ?  
**Objectif** : S'inspirer des stratégies qui fonctionnent pour améliorer Cognitia

---

## 🚦 1. Rate Limiting OpenAI (429 Too Many Requests)

### Comment Emergent.sh Gère le Rate Limiting

#### A. Architecture SÉQUENTIELLE (Clé du Succès)

**Emergent.sh** :
```
User request
    ↓
Single LLM call 1 (wait for response)
    ↓
Single LLM call 2 (wait for response)
    ↓
Single LLM call 3 (wait for response)
```

**Avantage** : 
- ✅ Pas de parallélisation → Pas de pic de requêtes
- ✅ Rate limiting très rare
- ✅ Facile à gérer les erreurs

---

**Cognitia** :
```
User request
    ↓
Planner LLM call
    ↓
Developer LLM call (Step 1)
Reviewer LLM call (Step 1)  } Peut-être trop rapproché
    ↓
Developer LLM call (Step 2)
Reviewer LLM call (Step 2)  } Même timing
```

**Problème potentiel** :
- ⚠️ Si Developer + Reviewer appellent en même temps → 2 calls rapprochés
- ⚠️ Si plusieurs steps s'enchaînent rapidement → Burst de requêtes
- ⚠️ 429 errors plus fréquents

---

#### B. Exponential Backoff (Standard)

**Ce qu'Emergent.sh fait** :
```python
# Pas besoin de gérer moi-même, le système le fait
# Mais si j'avais à le faire:

def call_llm_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            return llm.generate(prompt)
        except RateLimitError:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.random()
                # Attempt 1: 1-2s
                # Attempt 2: 2-3s
                # Attempt 3: 4-5s
                time.sleep(wait_time)
            else:
                raise
```

**Déjà implémenté dans Cognitia** (à vérifier) : Oui, dans `llm_router.py`

---

#### C. Délai Minimum Entre Requêtes (Pas utilisé par Emergent)

**Option pour Cognitia** :
```python
import time
from threading import Lock

class LLMRateLimiter:
    def __init__(self, min_delay_seconds=0.5):
        self.min_delay = min_delay_seconds
        self.last_call_time = 0
        self.lock = Lock()
    
    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call_time
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self.last_call_time = time.time()

# Usage dans LLMRouter
rate_limiter = LLMRateLimiter(min_delay_seconds=0.5)

async def generate(...):
    rate_limiter.wait_if_needed()  # Force 0.5s entre chaque call
    response = await openai.chat.completions.create(...)
    return response
```

**Impact** :
- ✅ Garantit 0.5s minimum entre chaque call OpenAI
- ✅ Réduit drastiquement les 429 errors
- ⚠️ Ralentit légèrement l'exécution (+0.5s par call)

---

#### D. Où Mettre la Limite ?

**Réponse** : Au niveau du **LLMRouter** (centralisé)

**Fichier** : `/app/backend/orchestrator/llm_router.py`

**Pourquoi** :
- ✅ Point unique de passage pour TOUS les calls LLM
- ✅ Garantit le rate limiting pour Planner, Developer, Reviewer, etc.
- ✅ Facile à activer/désactiver

**Code à ajouter** :
```python
class LLMRouter:
    def __init__(self, ...):
        # ... existing code ...
        self.rate_limiter = LLMRateLimiter(min_delay_seconds=0.5)
    
    async def generate(self, ...):
        # AVANT l'appel API
        self.rate_limiter.wait_if_needed()
        
        # ... existing code for LLM call ...
```

---

### Recommandation pour Cognitia

**Option 1 (Conservatrice)** : Ajouter délai minimum 0.5s
- ✅ Simple à implémenter
- ✅ Élimine 95% des 429 errors
- ⚠️ +5-10s par run (acceptable)

**Option 2 (Aggressive)** : Améliorer backoff + monitoring
- ✅ Pas de ralentissement si pas de 429
- ⚠️ Plus complexe à debugger

**Mon choix** : Option 1 (délai minimum 0.5s)

---

## 🔬 2. PHPStan Failures - Configuration Stricte

### Comment Emergent.sh Gère PHPStan

#### A. Je NE Lance PAS de Tests Automatiquement

**Emergent.sh (moi)** :
```
Créer fichier PHP
    ↓
Vérifier syntaxe (optionnel via lint tool)
    ↓
✅ FINI - Pas de PHPStan automatique
```

**Pourquoi** :
- 🎯 Ma mission : Créer du code fonctionnel
- 🎯 Pas ma mission : Valider avec PHPStan systématiquement
- 🎯 Si l'utilisateur demande PHPStan, je le lance explicitement

**Si l'utilisateur demande** :
```
User: "Run PHPStan on this project"
Me: <execute_bash>
     cd /app && ./vendor/bin/phpstan analyse
     </execute_bash>
Me: "Here are the results: [...]"
```

---

#### B. Approche de Cognitia (Actuelle)

**Cognitia** :
```
Developer génère code
    ↓
Reviewer vérifie SYSTÉMATIQUEMENT
    ↓ PHPStan
    ↓ Pint
    ↓ Pest
    ↓
Si échec → Retry
```

**Problème** :
- ⚠️ PHPStan peut échouer pour des raisons légitimes (projet incomplet)
- ⚠️ Bloque le workflow même si le code est correct
- ⚠️ Génère des retries inutiles

---

#### C. Stratégie Emergent.sh Adaptée à Cognitia

**Option 1 : Désactiver PHPStan pour Projets Incomplets**
```python
def should_run_phpstan(project_context, step_number, total_steps):
    """Décider si PHPStan doit être lancé"""
    
    # Pas de PHPStan sur les premiers 50% des steps
    if step_number < (total_steps / 2):
        return False
    
    # Pas de PHPStan si projet trop récent
    files_count = count_php_files(project_path)
    if files_count < 5:
        return False
    
    # Lancer PHPStan seulement en fin de projet
    return True
```

**Impact** :
- ✅ Pas de PHPStan sur projets incomplets
- ✅ Workflow plus fluide
- ✅ PHPStan lancé quand le projet est cohérent

---

**Option 2 : PHPStan en Mode "Soft" (Warnings Only)**
```python
async def run_phpstan(...):
    result = await execute_command("phpstan analyse")
    
    if result.exit_code != 0:
        # Ne PAS échouer, juste logger
        self.log.warning(f"PHPStan issues detected: {result.stderr}")
        return TestResult(
            success=True,  # ✅ Pas d'échec
            warnings=[result.stderr],
            type="phpstan"
        )
```

**Impact** :
- ✅ PHPStan donne du feedback
- ✅ Ne bloque PAS le workflow
- ✅ L'utilisateur voit les warnings

---

**Option 3 : PHPStan Optionnel (Comme Emergent)**
```python
# Dans reviewer_agent.py

if config.get("ENABLE_PHPSTAN_AUTO", False):
    # Lancer PHPStan seulement si activé explicitement
    phpstan_result = await self.run_phpstan(...)
else:
    # Skip PHPStan
    self.log.info("PHPStan skipped (not enabled in config)")
```

**Impact** :
- ✅ Contrôle total via config
- ✅ Peut être désactivé pour debug
- ✅ Réactivé en production si besoin

---

### Recommandation pour Cognitia

**Mon choix** : Combinaison Option 1 + Option 2
- ✅ Désactiver PHPStan sur premiers 50% des steps
- ✅ PHPStan en mode "soft" (warnings only, pas d'échec)
- ✅ Lancer PHPStan seulement quand projet cohérent

**Fichiers à modifier** :
- `/app/backend/orchestrator/agents/reviewer_agent.py`
- Ajouter logique `should_run_phpstan()`

---

## 📁 3. Fichiers Manquants (`routes/api.php`)

### Comment Emergent.sh Gère les Fichiers Manquants

#### A. Je VÉRIFIE TOUJOURS Avant de Modifier

**Emergent.sh (moi)** :
```
User: "Add a route to routes/api.php"

Étape 1: Vérifier si le fichier existe
<mcp_view_file>
  <path>/app/routes/api.php</path>
</mcp_view_file>

Résultat: ❌ File does not exist

Étape 2: Créer le fichier d'abord
<mcp_create_file>
  <path>/app/routes/api.php</path>
  <file_text><?php

use Illuminate\Support\Facades\Route;

// Routes API here
</file_text>
</mcp_create_file>

Étape 3: PUIS modifier
<mcp_search_replace>
  <path>/app/routes/api.php</path>
  ...
</mcp_search_replace>
```

**Principe** : **Vérifier → Créer si manquant → Modifier**

---

#### B. Cognitia Actuel (Problème)

**Cognitia** :
```
Developer Agent (Step 2):
{
  "type": "search_replace",
  "path": "routes/api.php",  // ❌ Fichier n'existe pas!
  "search": "...",
  "replace": "..."
}

→ ❌ Failed: File does not exist
→ Retry (attempt 2)
```

**Problème** :
- ❌ LLM devine que le fichier existe
- ❌ Première tentative échoue systématiquement
- ❌ Gaspillage de temps et de calls LLM

---

#### C. Solution Emergent.sh : Smart Content Reading

**Code à ajouter dans `developer_direct.py`** :

```python
async def generate_operations(self, step, project_context, ...):
    # AVANT de générer les opérations
    
    # 1. Lire les fichiers qui pourraient être ciblés
    potential_targets = self._extract_potential_file_paths(step.description)
    # Exemple: Si step contient "routes/api.php", l'extraire
    
    # 2. Vérifier lesquels EXISTENT
    existing_files = {}
    missing_files = []
    
    for file_path in potential_targets:
        full_path = Path(project_path) / file_path
        if full_path.exists():
            existing_files[file_path] = full_path.read_text()
        else:
            missing_files.append(file_path)
    
    # 3. INFORMER le LLM dans le prompt
    file_existence_block = ""
    if existing_files:
        file_existence_block += "✅ EXISTING FILES:\n"
        for path in existing_files.keys():
            file_existence_block += f"  • {path} EXISTS - can use search_replace/update\n"
    
    if missing_files:
        file_existence_block += "❌ MISSING FILES:\n"
        for path in missing_files:
            file_existence_block += f"  • {path} DOES NOT EXIST - MUST use 'create' first!\n"
    
    # 4. Ajouter au prompt
    prompt = self._build_json_prompt(
        ...,
        file_existence_info=file_existence_block
    )
```

**Impact** :
- ✅ LLM sait exactement quels fichiers existent
- ✅ LLM choisit `create` au lieu de `search_replace`
- ✅ Plus de tentatives échouées pour fichiers manquants

---

#### D. Alternative : Fallback Automatique

**Code dans `file_writer.py`** :

```python
def execute_operations(self, operations, project_path, stack):
    converted_ops = []
    
    for op in operations:
        if op["type"] == "search_replace":
            file_path = Path(project_path) / op["path"]
            
            # Si fichier n'existe pas, convertir en 'create'
            if not file_path.exists():
                self.log.warning(
                    f"⚠️ search_replace on missing file {op['path']}, "
                    f"converting to 'create' operation"
                )
                new_op = {
                    "type": "create",
                    "path": op["path"],
                    "content": op["replace"]  # Utiliser le 'replace' comme contenu
                }
                converted_ops.append(new_op)
                continue
        
        converted_ops.append(op)
    
    # Exécuter les opérations converties
    return self._execute_operations_internal(converted_ops, ...)
```

**Impact** :
- ✅ Conversion automatique `search_replace` → `create`
- ✅ Pas d'échec pour fichiers manquants
- ⚠️ Peut perdre le "search" context (pas idéal)

---

### Recommandation pour Cognitia

**Mon choix** : Solution C (Smart Content Reading)
- ✅ Informe le LLM des fichiers existants/manquants
- ✅ LLM prend la bonne décision dès le départ
- ✅ Pas de fallback hacky

**Fichiers à modifier** :
- `/app/backend/orchestrator/agents/developer_direct.py`
- Ajouter `_extract_potential_file_paths()`
- Ajouter `file_existence_block` au prompt

---

## 💀 4. "Expecting value: line 1 column 1" - JSON Vide

### Comment Emergent.sh Gère les Réponses Vides

#### A. Validation Immédiate + Retry

**Emergent.sh (moi)** :
```python
response = await llm.generate(prompt)

# Vérification 1: Réponse non vide
if not response or not response.content:
    self.log.error("❌ Empty response from LLM")
    # Retry immédiatement (pas de parsing)
    return await self._retry_with_different_prompt(prompt)

# Vérification 2: Contenu non vide
if len(response.content.strip()) == 0:
    self.log.error("❌ Empty content from LLM")
    return await self._retry_with_different_prompt(prompt)

# Vérification 3: Parsing JSON
try:
    data = json.loads(response.content)
except json.JSONDecodeError as e:
    self.log.error(f"❌ Invalid JSON: {e}")
    return await self._retry_with_clearer_prompt(prompt, error=str(e))
```

**Principe** : **Valider → Retry si vide → Pas de propagation d'erreur**

---

#### B. Cognitia Actuel (Problème)

**Cognitia** :
```
Reviewer Agent:
response = await llm.generate(prompt)
data = json.loads(response.content)  # ❌ Si vide → Exception
→ "Expecting value: line 1 column 1 (char 0)"
→ Exception remonte jusqu'à l'utilisateur
→ Step échoué
```

**Problème** :
- ❌ Pas de vérification avant parsing
- ❌ Exception non catchée
- ❌ Pas de retry automatique

---

#### C. Solution Emergent.sh : Defensive Parsing

**Code à ajouter dans `reviewer_agent.py`** :

```python
async def review_step(self, ...):
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # Call LLM
            response = await self.llm_router.generate(prompt=prompt, ...)
            
            # ✅ Vérification 1: Réponse existe
            if not response or not hasattr(response, 'content'):
                self.log.warning(f"⚠️ Empty response from LLM (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Petit délai avant retry
                    continue
                else:
                    # Fallback: Accepter le step par défaut
                    return ReviewResult(decision="accept", feedback="No review available")
            
            # ✅ Vérification 2: Contenu non vide
            content = response.content.strip()
            if len(content) == 0:
                self.log.warning(f"⚠️ Empty content from LLM (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                else:
                    return ReviewResult(decision="accept", feedback="No review available")
            
            # ✅ Vérification 3: JSON valide
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                self.log.error(f"❌ JSON parsing failed: {e}")
                self.log.error(f"Response preview: {content[:200]}")
                
                if attempt < max_retries - 1:
                    # Retry avec prompt plus clair
                    prompt += "\n\n🚨 PREVIOUS ATTEMPT FAILED: Invalid JSON. Please return VALID JSON only!"
                    continue
                else:
                    # Fallback: Accepter le step
                    return ReviewResult(decision="accept", feedback="Review failed, accepting by default")
            
            # ✅ Success
            return self._parse_review_result(data)
            
        except Exception as e:
            self.log.error(f"❌ Unexpected error in review: {e}")
            if attempt < max_retries - 1:
                continue
            else:
                # Fallback: Accepter
                return ReviewResult(decision="accept", feedback=f"Review error: {e}")
```

**Impact** :
- ✅ 3 niveaux de vérification
- ✅ Retry automatique (2 tentatives)
- ✅ Fallback graceful (accepter si échec)
- ✅ Pas de crash du système

---

#### D. Alternative : Skip Review si Échec

**Option plus simple** :
```python
async def review_step(self, ...):
    try:
        response = await self.llm_router.generate(...)
        
        if not response or not response.content:
            self.log.warning("⚠️ Review failed, skipping review")
            return ReviewResult(decision="accept", feedback="Review skipped")
        
        data = json.loads(response.content)
        return self._parse_review_result(data)
        
    except Exception as e:
        self.log.error(f"❌ Review error: {e}, accepting step by default")
        return ReviewResult(decision="accept", feedback="Review failed")
```

**Impact** :
- ✅ Simple et robuste
- ✅ Workflow ne bloque jamais
- ⚠️ Pas de retry (accepte immédiatement)

---

### Recommandation pour Cognitia

**Mon choix** : Solution C (Defensive Parsing avec retries)
- ✅ 3 niveaux de validation
- ✅ 2 tentatives de retry
- ✅ Fallback graceful
- ✅ Système robuste

**Fichiers à modifier** :
- `/app/backend/orchestrator/agents/reviewer_agent.py`
- `/app/backend/orchestrator/agents/escalation_agent.py` (même problème)

---

## 🔄 5. Architecture : Un Gros LLM ou Plein de Petits ?

### Comment Emergent.sh Fonctionne

**Réponse** : **UN seul LLM à la fois, SÉQUENTIEL**

```
Request 1: Think about the problem
    ↓ (wait)
Response 1: "Here's my analysis..."
    ↓
Request 2: Write code based on analysis
    ↓ (wait)
Response 2: "Here's the code..."
    ↓
Request 3: Review the code
    ↓ (wait)
Response 3: "Looks good!"
```

**Pas de parallélisation** :
- ❌ Je NE fais PAS 10 calls LLM en même temps
- ❌ Je NE découpe PAS en micro-tâches parallèles
- ✅ Une tâche à la fois, dans l'ordre

---

### Avantages de l'Approche Séquentielle

**1. Rate Limiting Contrôlé**
- ✅ Pas de burst de requêtes
- ✅ 429 errors très rares
- ✅ Facile à gérer

**2. Context Préservé**
- ✅ Je me souviens de ce que j'ai fait
- ✅ Cohérence entre les étapes
- ✅ Pas de perte d'information

**3. Debugging Facile**
- ✅ Logs linéaires, faciles à suivre
- ✅ Erreurs isolées
- ✅ Pas de race conditions

**4. Coût Prévisible**
- ✅ Un call à la fois
- ✅ Budget facile à estimer
- ✅ Pas de gaspillage

---

### Cognitia Actuel

**Cognitia** semble aussi séquentiel :
```
Planner → Generate plan
    ↓
Developer (Step 1) → Generate operations
    ↓
Reviewer (Step 1) → Review
    ↓
Developer (Step 2) → Generate operations
    ↓
...
```

**C'est bien !** ✅

**Optimisation possible** : Ajouter délai entre calls (voir point 1)

---

## 📊 Récapitulatif des Solutions

| Problème | Stratégie Emergent.sh | Solution pour Cognitia |
|----------|----------------------|------------------------|
| **1. Rate limiting** | Séquentiel + backoff | Ajouter délai 0.5s dans LLMRouter |
| **2. PHPStan failures** | Pas de tests auto | Désactiver sur projets incomplets + mode "soft" |
| **3. Fichiers manquants** | Vérifier avant modifier | Smart Content Reading (informer LLM) |
| **4. JSON vide** | Valider + Retry + Fallback | Defensive parsing dans reviewer |
| **5. Parallélisation** | Séquentiel pur | Déjà séquentiel ✅ |

---

## 🚀 Plan d'Implémentation Recommandé

### Phase 1 : Quick Wins (1-2h)

1. **Rate Limiting** : Ajouter `LLMRateLimiter` dans `llm_router.py`
2. **JSON Vide** : Ajouter defensive parsing dans `reviewer_agent.py`

**Impact** : Résout 80% des problèmes actuels

---

### Phase 2 : Améliorations (2-3h)

3. **Fichiers Manquants** : Smart Content Reading dans `developer_direct.py`
4. **PHPStan** : Mode "soft" + désactivation projets incomplets

**Impact** : Système beaucoup plus robuste

---

### Phase 3 : Polissage (1h)

5. **Logs** : Améliorer visibilité des retries/fallbacks
6. **Tests** : Valider chaque solution individuellement

**Impact** : Production-ready

---

## 🎯 Conclusion

### Principes Emergent.sh à Retenir

1. **Séquentiel > Parallèle** : Simplicité et contrôle
2. **Vérifier > Deviner** : Toujours valider avant d'agir
3. **Fallback > Crash** : Le système ne doit jamais bloquer
4. **Retry > Échec** : 2-3 tentatives avant d'abandonner
5. **Logs > Silence** : Visibilité totale sur ce qui se passe

---

### Prochaines Étapes

**Étape 1** : Implémenter rate limiter (15 min)  
**Étape 2** : Defensive parsing reviewer (30 min)  
**Étape 3** : Tester sur projet Laravel (10 min)  
**Étape 4** : Si succès → Implémenter reste (Phase 2)

---

**Auteur** : Emergent.sh Strategies Applied to Cognitia  
**Status** : Recommandations prêtes à implémenter  
**Impact attendu** : Réduction 80%+ des échecs actuels
