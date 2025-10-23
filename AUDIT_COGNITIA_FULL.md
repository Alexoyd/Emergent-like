# 🔍 Audit Complet Cognitia - Déclaré vs Exécuté

**Date**: 2025-07-XX  
**Objectif**: Rendre le pipeline 100% fiable sur toutes les stacks (Laravel, Python, Node, React, Vue)  
**Référence**: Parité fonctionnelle avec Emergent.sh

---

## 📊 Executive Summary

### Taux de Fiabilité Actuel (par stack)
```
Laravel:    33% ❌ (installation OK, Vite crash, tests échec)
Python:     [À tester]
Node:       [À tester]
React:      [À tester]
Vue:        [À tester]
```

### Problèmes Critiques Identifiés
1. 🔴 **BLOQUANT**: `_run_command()` ne supporte pas `timeout` → crash Vite/Tailwind
2. 🔴 **BLOQUANT**: Variable `default_css` non initialisée → crash fallback CSS
3. 🟠 **IMPORTANT**: Search/replace fragile sur vite.config.js → 3 échecs
4. 🟠 **IMPORTANT**: Logs tests non exploités par auto-repair
5. 🟡 **NICE-TO-HAVE**: Pas de métriques par stack

---

## 🎯 Gap Analysis: Déclaré vs Exécuté

### 1. Contrat d'Exécution Unifié

#### **DÉCLARÉ** (Attendu)
> "Toutes les commandes passent par un exécuteur qui accepte timeout, remonte stdout/stderr complets, et écrit des logs consultables (tail + lien)."

#### **EXÉCUTÉ** (Réalité)
```python
# ❌ PROBLÈME: project_manager.py ligne 462
async def _run_command(self, command: List[str], cwd: Optional[str] = None):
    # Pas de paramètre timeout !
    process = await asyncio.create_subprocess_exec(*command, cwd=cwd, ...)
    stdout, stderr = await process.communicate()  # SANS timeout
```

**Impact**:
- `laravel_handler.py` ligne 361: `self.run_command(..., timeout=180)` → **CRASH**
- `laravel_handler.py` ligne 378: `self.run_command(..., timeout=180)` → **CRASH**

**Comparaison avec autres exécuteurs dans le repo**:
```python
# ✅ CORRECT: tools.py ligne 1532
async def _run_command_with_timeout(self, command, cwd, timeout):
    process = await asyncio.create_subprocess_exec(...)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        # Gestion propre du timeout
```

**Verdict**: ❌ **NON CONFORME** - Exécuteur principal ne supporte pas timeout

---

### 2. Robustesse Fichiers & Builds

#### **DÉCLARÉ** (Attendu)
> "Éviter les search/replace fragiles sur des fichiers clés (ex. vite.config.js). Optez pour des opérations idempotentes (create_or_update). Si l'écosystème Node/Vite tombe, la build ne bloque pas : fournissez des fallback assets (CSS minimal)."

#### **EXÉCUTÉ** (Réalité)

**A. Fallback CSS**:
```python
# ✅ PARTIELLEMENT CORRECT: laravel_handler.py lignes 409-643
async def _create_fallback_public_css(self, code_path: Path):
    resources_css = code_path / "resources" / "css" / "app.css"
    public_css_dir = code_path / "public" / "css"
    public_css_file = public_css_dir / "app.css"
    
    public_css_dir.mkdir(parents=True, exist_ok=True)
    
    if resources_css.exists():
        import shutil
        shutil.copy2(resources_css, public_css_file)
    else:
        # ❌ PROBLÈME: default_css défini ICI mais référencé potentiellement avant
        default_css = """/* Laravel Auto-Generated Fallback CSS */
        ..."""
        public_css_file.write_text(default_css)
```

**Problème potentiel**: Si exception avant le `else`, `default_css` n'est jamais défini mais pourrait être référencé.

**B. Search/Replace sur vite.config.js**:
```python
# ❌ UTILISÉ DANS VOTRE TEST: Selon logs
search_replace: Failed search/replace in vite.config.js: Search text not found in vite.config.js
```

**Analyse**: 
- Laravel 12 livre `vite.config.js` complet via `composer create-project`
- Aucun patch ne devrait être nécessaire
- Si modification requise → utiliser opération `update` complète (file_writer.py)

**Verdict**: 🟠 **PARTIELLEMENT CONFORME** - Fallback CSS existe mais buggy, search/replace encore utilisé

---

### 3. Baselines & Sentinelles

#### **DÉCLARÉ** (Attendu)
> "Au bootstrap d'un squelette, linters/analyse statique au niveau minimal (ou baseline) non-bloquants ; générer un test sentinelle si la suite est vide."

#### **EXÉCUTÉ** (Réalité)

**A. PHPStan Baseline**:
```python
# ✅ IMPLÉMENTÉ: tools.py lignes 724-733 (test_result.md)
async def _setup_phpstan_for_laravel(self, code_path: Path):
    # Install PHPStan
    # Create phpstan.neon level 0
    # Generate baseline
```

**B. Test Sentinelle**:
```python
# ❌ NON IMPLÉMENTÉ: Aucune génération automatique de test sentinelle
# Si vendor/bin/pest lancé sur projet vide → échec
```

**Comparaison avec best practice**:
```php
// Test sentinelle attendu dans tests/Unit/ExampleTest.php
<?php
test('example', function () {
    expect(true)->toBeTrue();
});
```

**Verdict**: 🟠 **PARTIELLEMENT CONFORME** - PHPStan baseline OK, test sentinelle manquant

---

### 4. Auto-Heal

#### **DÉCLARÉ** (Attendu)
> "En cas d'échec, ouvrir autofix/*, proposer un patch (direct-write), relancer Health/Lint/Tests/Build ; jamais d'auto-merge."

#### **EXÉCUTÉ** (Réalité)
```python
# ✅ IMPLÉMENTÉ: auto_heal.py (PHASE 3)
class AutoHealManager:
    async def create_autofix_branch(self, project_id, operations):
        # Crée branch autofix/YYYYMMDD-HHMMSS
        # Applique operations JSON
        # Commit atomique
        # Lance HealthPipelineRunner
```

**A. Exploitation des Logs**:
```python
# ❌ PROBLÈME: tools.py
if test_type in self.known_simple_issues:
    # Auto-repair LLM désactivé pour "simple fixable issue"
    pass
```

**Logs disponibles mais non exploités**:
- `logs/pest_errors.log`
- `logs/phpstan_errors.log`

**Verdict**: 🟠 **PARTIELLEMENT CONFORME** - Auto-heal existe mais n'exploite pas les logs

---

### 5. Observabilité & Artefacts

#### **DÉCLARÉ** (Attendu)
> "Exposer les artefacts clés (ex. public/build/manifest.json, dist/, Docker image) et les logs complets par étape dans l'UI. Ajouter un tableau de bord simple de métriques par stack."

#### **EXÉCUTÉ** (Réalité)

**A. Artefacts**:
```python
# ✅ IMPLÉMENTÉ: server.py /api/projects/{id}/branches/{branch}/artifacts
# Retourne: diff, commits, files_changed, health_logs
```

**B. Logs par étape**:
```python
# ✅ IMPLÉMENTÉ: tools.py _write_complete_log()
# Écrit dans /logs/*.log avec rotation 5MB
# Affiche tail (20 lignes) + pointeur vers fichier
```

**C. Métriques par stack**:
```python
# ❌ NON IMPLÉMENTÉ: Aucun endpoint /api/admin/metrics
# Pas de tracking success_rate, avg_duration, common_errors par stack
```

**Verdict**: 🟠 **PARTIELLEMENT CONFORME** - Artefacts OK, logs OK, métriques manquantes

---

### 6. Idempotence & Re-runs

#### **DÉCLARÉ** (Attendu)
> "Relancer un run ne doit pas dégrader l'état ; commits déterministes par step et ré-indexation RAG après modifications."

#### **EXÉCUTÉ** (Réalité)
```python
# ✅ IMPLÉMENTÉ: server.py _commit_step_changes()
# Format: feat(run:<run_id>): step <n> – <titre>
# Commits déterministes

# ✅ IMPLÉMENTÉ: server.py execute-operations
# RAG re-indexing après modifications en mode direct
```

**Verdict**: ✅ **CONFORME**

---

## 🔧 Corrections Nécessaires (Priorisées)

### 🔴 CRITIQUE (Bloquant) - À CORRIGER IMMÉDIATEMENT

#### **C1. Fix `_run_command()` Timeout Support**
**Fichier**: `/app/backend/orchestrator/project_manager.py`  
**Ligne**: 462  
**Problème**: Pas de paramètre `timeout`, cause crashes Vite/Tailwind  
**Solution**:
```python
async def _run_command(self, command: List[str], cwd: Optional[str] = None, timeout: int = 300):
    """Run shell command with timeout support"""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise Exception(f"Command timed out after {timeout}s: {' '.join(command)}")
        
        return type('CommandResult', (), {
            'returncode': process.returncode,
            'stdout': stdout.decode('utf-8', errors='ignore'),
            'stderr': stderr.decode('utf-8', errors='ignore')
        })()
        
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        raise
```

**Impact**: Débloque Vite/Tailwind pour Laravel, React, Vue  
**Estimation**: 30 minutes

---

#### **C2. Fix `default_css` Variable Non Initialisée**
**Fichier**: `/app/backend/orchestrator/stacks/laravel_handler.py`  
**Ligne**: 409-643  
**Problème**: `default_css` défini dans `else` mais peut être référencé avant  
**Solution**:
```python
async def _create_fallback_public_css(self, code_path: Path) -> None:
    try:
        resources_css = code_path / "resources" / "css" / "app.css"
        public_css_dir = code_path / "public" / "css"
        public_css_file = public_css_dir / "app.css"
        
        public_css_dir.mkdir(parents=True, exist_ok=True)
        
        # ✅ FIX: Définir default_css EN AMONT
        default_css = """/* Laravel Auto-Generated Fallback CSS */
/* This file provides basic styling when @vite() directive is not used */
... (208 lignes de CSS)
"""
        
        if resources_css.exists():
            import shutil
            try:
                shutil.copy2(resources_css, public_css_file)
                if self.logger:
                    self.logger.info(f"✅ Copied {resources_css} → {public_css_file}")
            except Exception as copy_error:
                # Fallback si copie échoue
                if self.logger:
                    self.logger.warning(f"⚠️ Copy failed, using default CSS: {copy_error}")
                public_css_file.write_text(default_css)
        else:
            public_css_file.write_text(default_css)
            if self.logger:
                self.logger.info(f"✅ Created fallback CSS at {public_css_file}")
    
    except Exception as e:
        if self.logger:
            self.logger.warning(f"⚠️ Could not create fallback CSS: {e}")
        # Non-bloquant
```

**Impact**: Fallback CSS toujours disponible, même en cas d'erreur  
**Estimation**: 15 minutes

---

#### **C3. Éliminer Search/Replace Fragile sur vite.config.js**
**Fichier**: Stratégie globale  
**Problème**: Patches search/replace échouent si motif introuvable  
**Solution**:

**Option A (recommandée)**: Ne PAS toucher vite.config.js
```python
# Laravel 12 livre vite.config.js complet via composer create-project
# Aucune modification nécessaire dans 99% des cas
```

**Option B (si modification requise)**: Utiliser opération `update` complète
```python
# Dans developer_direct.py ou auto-heal
operations = [
    {
        "type": "update",
        "path": "vite.config.js",
        "content": """import { defineConfig } from 'vite';
import laravel from 'laravel-vite-plugin';

export default defineConfig({
    plugins: [
        laravel({
            input: ['resources/css/app.css', 'resources/js/app.js'],
            refresh: true,
        }),
    ],
});
"""
    }
]
```

**Option C (si patch absolument nécessaire)**: Create-or-update idempotent
```python
# Vérifier existence avant patch
vite_config = code_path / "vite.config.js"
if not vite_config.exists():
    # Créer fichier complet
    vite_config.write_text(VITE_CONFIG_TEMPLATE)
else:
    # Ne PAS patcher, Laravel 12 le livre complet
    pass
```

**Impact**: Zéro échec sur vite.config.js  
**Estimation**: 1 heure

---

### 🟠 IMPORTANT (Performance) - À CORRIGER ENSUITE

#### **C4. Activer Auto-Repair LLM avec Exploitation Logs**
**Fichier**: `/app/backend/orchestrator/tools.py`  
**Ligne**: ~1850 (smart_command_execution)  
**Problème**: Auto-repair LLM désactivé pour tests, logs non exploités  
**Solution**:
```python
async def smart_command_execution(self, ...):
    # ... (code existant)
    
    # ✅ NOUVEAU: Activer auto-repair avec lecture logs
    if test_type in ['pest', 'phpstan'] and attempt < max_attempts:
        log_file = code_path / "logs" / f"{test_type}_errors.log"
        
        if log_file.exists() and os.path.getsize(log_file) > 0:
            if self.logger:
                self.logger.info(f"🔧 Reading {test_type} error log for auto-repair...")
            
            try:
                error_content = log_file.read_text(encoding='utf-8')
                
                # Extraire les erreurs pertinentes
                relevant_errors = self._extract_relevant_errors(error_content, test_type)
                
                if relevant_errors:
                    if self.logger:
                        self.logger.info(f"🧠 Passing {len(relevant_errors)} errors to LLM for repair...")
                    
                    # Générer fix via LLM
                    repair_operations = await self._generate_repair_operations(
                        test_type=test_type,
                        errors=relevant_errors,
                        code_path=code_path
                    )
                    
                    if repair_operations:
                        # Appliquer operations via file_writer
                        await self._apply_repair_operations(repair_operations, code_path)
                        
                        # Relancer tests
                        continue  # Retry loop
            
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"⚠️ Auto-repair failed: {e}")
```

**Méthodes à ajouter**:
```python
def _extract_relevant_errors(self, log_content: str, test_type: str) -> List[str]:
    """Extraire les erreurs pertinentes du log"""
    if test_type == 'pest':
        # Parser Pest output: FAILED tests, syntax errors
        pass
    elif test_type == 'phpstan':
        # Parser PHPStan output: Parameter type mismatch, undefined variable
        pass
    return errors

async def _generate_repair_operations(self, test_type, errors, code_path) -> List[Dict]:
    """Générer operations JSON via LLM pour corriger erreurs"""
    prompt = f"""
You are an expert {test_type} error fixer.

Errors found:
{errors}

Generate JSON operations to fix these errors:
[
    {{"type": "update", "path": "app/Models/User.php", "content": "..."}},
    ...
]
"""
    # Appel LLM via llm_router
    response = await self.llm_router.generate(prompt, ...)
    return parse_json_operations(response)

async def _apply_repair_operations(self, operations, code_path):
    """Appliquer operations via file_writer"""
    from .file_writer import execute_operations
    result = await execute_operations(operations, code_path, self.project_id)
    return result
```

**Impact**: Auto-correction automatique Pest/PHPStan  
**Estimation**: 3 heures

---

#### **C5. Générer Test Sentinelle Si Suite Vide**
**Fichier**: `/app/backend/orchestrator/stacks/laravel_handler.py`  
**Ligne**: Ajouter dans `create_project_skeleton()` après installation deps  
**Problème**: Pest échoue si aucun test défini  
**Solution**:
```python
async def _ensure_test_sentinelle(self, code_path: Path) -> None:
    """
    🧪 Générer test sentinelle si la suite est vide
    """
    tests_unit_dir = code_path / "tests" / "Unit"
    example_test = tests_unit_dir / "ExampleTest.php"
    
    # Vérifier si des tests existent déjà
    existing_tests = list(tests_unit_dir.glob("*.php")) if tests_unit_dir.exists() else []
    
    if not existing_tests or not example_test.exists():
        if self.logger:
            self.logger.info("🧪 Generating test sentinelle (no tests found)...")
        
        tests_unit_dir.mkdir(parents=True, exist_ok=True)
        
        sentinelle_content = """<?php

test('example sentinelle test', function () {
    // This is a baseline test to ensure the test suite runs
    expect(true)->toBeTrue();
});

test('application returns successful response', function () {
    $response = $this->get('/');
    $response->assertStatus(200);
});
"""
        
        example_test.write_text(sentinelle_content)
        
        if self.logger:
            self.logger.info(f"✅ Test sentinelle created at {example_test}")

# Appeler dans create_project_skeleton() après _install_dev_dependencies_intelligent()
await self._ensure_test_sentinelle(code_path)
```

**Impact**: Pest passe toujours (au moins tests sentinelles verts)  
**Estimation**: 30 minutes

---

### 🟡 NICE-TO-HAVE (Monitoring) - À FAIRE PLUS TARD

#### **C6. Tableau de Bord Métriques par Stack**
**Fichier**: Nouveau `/app/backend/orchestrator/metrics.py`  
**Problème**: Pas de visibilité sur taux succès/échec par stack  
**Solution**:
```python
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import statistics

@dataclass
class StackMetrics:
    stack: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_duration_seconds: float
    median_duration_seconds: float
    p95_duration_seconds: float
    common_errors: Dict[str, int]  # error_type: count
    last_24h_success_rate: float
    last_7d_success_rate: float
    
    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100

class MetricsCollector:
    """Collecte et agrège les métriques par stack"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_stack_metrics(self, stack: str, days: int = 30) -> StackMetrics:
        """Récupérer métriques pour un stack sur N derniers jours"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Requête MongoDB
        runs = await self.db.runs.find({
            "stack": stack,
            "created_at": {"$gte": cutoff_date}
        }).to_list(length=None)
        
        if not runs:
            return StackMetrics(
                stack=stack,
                total_runs=0,
                successful_runs=0,
                failed_runs=0,
                avg_duration_seconds=0.0,
                median_duration_seconds=0.0,
                p95_duration_seconds=0.0,
                common_errors={},
                last_24h_success_rate=0.0,
                last_7d_success_rate=0.0
            )
        
        # Calculs
        total_runs = len(runs)
        successful_runs = sum(1 for r in runs if r.get("status") == "completed")
        failed_runs = total_runs - successful_runs
        
        durations = [r.get("duration", 0) for r in runs if r.get("duration")]
        avg_duration = statistics.mean(durations) if durations else 0.0
        median_duration = statistics.median(durations) if durations else 0.0
        
        sorted_durations = sorted(durations)
        p95_index = int(len(sorted_durations) * 0.95)
        p95_duration = sorted_durations[p95_index] if sorted_durations else 0.0
        
        # Erreurs communes
        error_counts = {}
        for run in runs:
            if run.get("status") == "failed" and run.get("error"):
                error_type = run["error"].split(":")[0]  # Premier mot de l'erreur
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        # Top 5 erreurs
        common_errors = dict(sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        
        # Taux succès dernières 24h
        last_24h = datetime.utcnow() - timedelta(hours=24)
        runs_24h = [r for r in runs if r.get("created_at") >= last_24h]
        success_24h = sum(1 for r in runs_24h if r.get("status") == "completed")
        rate_24h = (success_24h / len(runs_24h) * 100) if runs_24h else 0.0
        
        # Taux succès derniers 7 jours
        last_7d = datetime.utcnow() - timedelta(days=7)
        runs_7d = [r for r in runs if r.get("created_at") >= last_7d]
        success_7d = sum(1 for r in runs_7d if r.get("status") == "completed")
        rate_7d = (success_7d / len(runs_7d) * 100) if runs_7d else 0.0
        
        return StackMetrics(
            stack=stack,
            total_runs=total_runs,
            successful_runs=successful_runs,
            failed_runs=failed_runs,
            avg_duration_seconds=avg_duration,
            median_duration_seconds=median_duration,
            p95_duration_seconds=p95_duration,
            common_errors=common_errors,
            last_24h_success_rate=rate_24h,
            last_7d_success_rate=rate_7d
        )
    
    async def log_run_result(
        self, 
        run_id: str, 
        stack: str, 
        status: str, 
        duration: float, 
        error: Optional[str] = None
    ):
        """Enregistrer résultat de run pour métriques futures"""
        await self.db.runs.update_one(
            {"_id": run_id},
            {"$set": {
                "status": status,
                "duration": duration,
                "error": error,
                "completed_at": datetime.utcnow()
            }}
        )
```

**Endpoint server.py**:
```python
from orchestrator.metrics import MetricsCollector

@app.get("/api/admin/metrics")
async def get_metrics(days: int = 30):
    """Tableau de bord métriques par stack"""
    metrics_collector = MetricsCollector(db)
    all_stacks = ["laravel", "react", "vue", "node", "python"]
    
    results = {}
    for stack in all_stacks:
        metrics = await metrics_collector.get_stack_metrics(stack, days)
        results[stack] = asdict(metrics)
    
    # Agrégation globale
    total_runs = sum(m["total_runs"] for m in results.values())
    total_success = sum(m["successful_runs"] for m in results.values())
    global_success_rate = (total_success / total_runs * 100) if total_runs > 0 else 0.0
    
    return {
        "by_stack": results,
        "global": {
            "total_runs": total_runs,
            "total_success": total_success,
            "global_success_rate": global_success_rate
        }
    }

@app.get("/api/admin/metrics/{stack}")
async def get_stack_metrics_detail(stack: str, days: int = 30):
    """Métriques détaillées pour un stack spécifique"""
    metrics_collector = MetricsCollector(db)
    metrics = await metrics_collector.get_stack_metrics(stack, days)
    return asdict(metrics)
```

**Impact**: Visibilité complète sur fiabilité par stack  
**Estimation**: 3 heures

---

## 📋 Plan d'Exécution (Phases)

### **PHASE 1: Corrections Critiques** (2-3 heures)
- [ ] C1. Fix `_run_command()` timeout (30 min)
- [ ] C2. Fix `default_css` variable (15 min)
- [ ] C3. Éliminer search/replace vite.config.js (1h)
- [ ] Tests unitaires pour chaque fix (30 min)
- [ ] Backend restart + validation API (15 min)

### **PHASE 2: Auto-Repair Intelligent** (3-4 heures)
- [ ] C4. Activer auto-repair LLM (3h)
- [ ] C5. Générer test sentinelle (30 min)
- [ ] Tests unitaires auto-repair (30 min)

### **PHASE 3: Tests E2E par Stack** (6-8 heures)
- [ ] Laravel: Create project complet + attach mode + auto-heal (2h)
- [ ] Python/FastAPI: Create + attach + auto-heal (1.5h)
- [ ] Node/Express: Create + attach + auto-heal (1.5h)
- [ ] React: Create + attach + auto-heal (1.5h)
- [ ] Vue: Create + attach + auto-heal (1.5h)

### **PHASE 4: Observabilité** (3-4 heures)
- [ ] C6. Métriques par stack (3h)
- [ ] Dashboard frontend simple (1h)

### **PHASE 5: Documentation & Validation** (2-3 heures)
- [ ] Rapport final avec métriques
- [ ] Documentation troubleshooting par stack
- [ ] Démonstration DoD atteints

**TOTAL ESTIMÉ**: 16-22 heures

---

## 🎯 Definition of Done (DoD) - Validation Cross-Stack

### Laravel ✅ (Target: 94%)
- [ ] Create project: composer install, Vite build, tests sentinelles verts
- [ ] Health check: endpoint `/` répond 200, manifest.json existe
- [ ] Lint: Pint passe, PHPStan baseliné (level 0)
- [ ] Tests: Pest passe (tests sentinelles)
- [ ] Build: public/build/* existe OU public/css/app.css (fallback)
- [ ] Logs: Complets dans logs/*.log avec tail visible
- [ ] Auto-heal: 1 correction démontrée (ex: fix routes/web.php)

### Python/FastAPI ✅ (Target: 92%)
- [ ] Create project: pip install, server.py démarre
- [ ] Health check: endpoint `/health` répond 200
- [ ] Lint: Ruff passe ou baseliné
- [ ] Tests: Pytest passe (test sentinelle)
- [ ] Build: N/A (Python runtime)
- [ ] Packaging: requirements.txt complet
- [ ] Auto-heal: 1 correction démontrée

### Node/Express ✅ (Target: 90%)
- [ ] Create project: npm install, server.js démarre
- [ ] Health check: endpoint `/` répond 200
- [ ] Lint: ESLint passe ou baseliné
- [ ] Tests: Jest/Mocha passe (test sentinelle)
- [ ] Build: dist/* existe (si TypeScript)
- [ ] Auto-heal: 1 correction démontrée

### React ✅ (Target: 95%)
- [ ] Create project: npm install, vite build
- [ ] Health check: index.html accessible, manifest.json existe
- [ ] Lint: ESLint passe
- [ ] Tests: Vitest passe (test sentinelle)
- [ ] Build: dist/* existe
- [ ] Auto-heal: 1 correction démontrée (ex: fix import error)

### Vue ✅ (Target: 95%)
- [ ] Create project: npm install, vite build
- [ ] Health check: index.html accessible, manifest.json existe
- [ ] Lint: ESLint passe
- [ ] Tests: Vitest passe (test sentinelle)
- [ ] Build: dist/* existe
- [ ] Auto-heal: 1 correction démontrée

### Métriques Globales ✅
- [ ] Taux succès global ≥ 90% sur 50+ runs
- [ ] Durée moyenne par stack < 10 min
- [ ] Aucun crash bloquant (tous gérés gracefully)
- [ ] Dashboard métriques opérationnel

---

## 🔬 Tests de Validation

### Test 1: Laravel Complete Flow
```bash
# API call
curl -X POST http://localhost:8001/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Create Laravel 12 blog with posts CRUD",
    "stack": "laravel"
  }'

# Attendre completion (max 15 min)
# Vérifier:
✅ Status: completed
✅ Files: composer.json, artisan, public/build/manifest.json OU public/css/app.css
✅ Tests: vendor/bin/pest passe (tests sentinelles verts)
✅ Lint: vendor/bin/pint passe
✅ Health: php artisan serve → http://localhost:8000/ répond 200
✅ Logs: /logs/pest.log, /logs/phpstan.log existent et consultables
✅ Commit: feat(run:<run_id>): step 1 – Setup Laravel project
```

### Test 2: Attach Mode + Auto-Heal
```bash
# Créer projet Laravel manuellement
cd /tmp
composer create-project laravel/laravel test-attach
cd test-attach
git init && git add -A && git commit -m "Initial"

# Introduire erreur
echo "<?php
Route::get('/', function () {});" > routes/web.php

# Attacher + auto-heal
curl -X POST http://localhost:8001/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Fix broken route",
    "project_mode": "attach",
    "project_path": "/tmp/test-attach"
  }'

# Auto-heal devrait créer autofix/* avec correction
# Vérifier:
✅ Branch autofix/YYYYMMDD-HHMMSS créée
✅ routes/web.php corrigé (return view('welcome'))
✅ Health pipeline passe
✅ Status: ready-to-merge
✅ Artifacts: diff, commits, health_results visibles
```

### Test 3: Stress Test (10 Runs Parallèles)
```bash
# Lancer 10 créations Laravel en parallèle
for i in {1..10}; do
  curl -X POST http://localhost:8001/api/runs \
    -H "Content-Type: application/json" \
    -d "{"goal": "Create Laravel project $i", "stack": "laravel"}" &
done
wait

# Vérifier métriques
curl http://localhost:8001/api/admin/metrics

# Attendu:
✅ Laravel success_rate ≥ 90% (9/10 minimum)
✅ Aucun crash serveur
✅ Logs complets pour chaque run
✅ Durée moyenne < 10 min
```

---

## 📈 Métriques de Succès Attendues

### Avant Corrections (État Actuel)
```
Laravel:    33% ❌ (2/6 étapes)
Python:     [Non testé]
Node:       [Non testé]
React:      [Non testé]
Vue:        [Non testé]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Global:     33% (estimation)
```

### Après Corrections (Objectif)
```
Laravel:    94% ✅ (8.5/9 étapes)
Python:     92% ✅ (8/9 étapes)
Node:       90% ✅ (7.5/9 étapes)
React:      95% ✅ (8.5/9 étapes)
Vue:        95% ✅ (8.5/9 étapes)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Global:     93% ✅ (+60 points)
```

### Gains Attendus
- **+60 points** de taux de succès global
- **Zéro crash bloquant** (timeout, variable undefined)
- **Auto-repair actif** (Pest/PHPStan auto-corrigés)
- **Fallbacks gracieux** (CSS, build, tests)
- **Observabilité complète** (logs, artefacts, métriques)

---

## 🚀 Prochaines Actions Immédiates

1. ✅ **Valider ce rapport d'audit avec vous**
2. 🔧 **Lancer PHASE 1 (Corrections Critiques)** → 2-3h
3. 🧪 **Tester Laravel flow complet** → 1h
4. 🔄 **Itérer sur Python/Node/React/Vue** → 6-8h
5. 📊 **Implémenter métriques** → 3h
6. 📄 **Rapport final + démonstration** → 2h

**Êtes-vous aligné avec ce plan ? Puis-je commencer PHASE 1 immédiatement ?**
