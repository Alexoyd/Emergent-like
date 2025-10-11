# Corrections des Patches Corrompus - Implémentation Complète

## 🎯 Objectif
Résoudre définitivement les erreurs `git apply → error: corrupt patch at line XX` en implémentant une approche en 3 axes : traçabilité, validation stricte, et génération améliorée.

---

## ✅ ACTION 1: Logging Détaillé et Artifacts

### Implémentation dans `/app/backend/orchestrator/tools.py`

#### Nouvelle fonction `_save_patch_artifact()` :
- **Localisation** : Sauvegarde dans `projects/<run_id>/artifacts/patches/<timestamp>_patch.patch`
- **Normalisation** : Conversion CRLF → LF automatique
- **SHA-256** : Calcul et stockage dans `.meta.json`
- **Métadonnées** : timestamp, run_id, size_bytes, line_count

#### Logs DEBUG ajoutés :
```python
logger.debug(f"📄 Patch artifact saved: {path} (SHA256: {hash[:16]}...)")
```

#### Dry-run avec `git apply --check` :
- Exécution avant toute application réelle
- Capture complète de stderr
- En cas d'échec → appel `_log_patch_failure_details()`

#### Fonction `_log_patch_failure_details()` :
Logs détaillés incluant :
- **Ligne/hunk incriminé** : Extraction du numéro de ligne avec contexte (±3 lignes)
- **CWD** : Chemin d'application
- **Git status** : `git status --porcelain` pour voir les modifications en cours
- **HEAD hash** : `git rev-parse --short HEAD` pour traçabilité
- **Artifact path** : Chemin complet du patch sauvegardé

---

## ✅ ACTION 2: Sanity Checks Avancés et Post-Apply Guard

### Implémentation dans `/app/backend/orchestrator/tools.py`

#### Nouvelle fonction `_advanced_patch_sanity_checks()` :

**Check 1 - Headers obligatoires** :
- Vérification présence `diff --git a/<path> b/<path>`
- Pour chaque fichier : `---` et `+++` obligatoires
- Détection quotes typographiques (" " ' ')

**Check 2 - Validation hunks** :
- Parse des headers `@@ -old_start,old_count +new_start,new_count @@`
- Comptage des lignes réelles dans chaque hunk
- Vérification cohérence compteurs (tolérance ±3 lignes)

**Check 3 - Chemins sûrs** :
- Refus des `..` (directory traversal)
- Refus des chemins absolus (`/`)
- Refus des caractères NULL (`\x00`)

**Check 4 - Line endings** :
- Détection CRLF (`\r`) et warning
- Normalisation automatique en amont

**Résultat** :
```python
{
    "valid": True/False,
    "errors": [],  # Bloquants
    "warnings": [],  # Non-bloquants
    "file_count": N,
    "line_count": M
}
```

#### Post-Apply Guard avec `_verify_patch_applied()` :
- Exécution `git status --porcelain` après application
- **Si output vide** → patch non appliqué (faux positif) → retourne `False`
- **Si output non vide** → changements détectés → retourne `True`
- Prévient les cas où git apply réussit sans rien modifier

---

## ✅ ACTION 3: Instructions LLM Renforcées

### Implémentation dans `/app/backend/orchestrator/agents/developer.py`

#### Prompt amélioré dans `_build_prompt()` :

**Nouvelles contraintes explicites** :
```
🔥 CRITICAL PATCH FORMAT REQUIREMENTS:
1. Output ONLY unified diff - NO prose, NO markdown, NO code fences
2. MANDATORY prefixes: a/ and b/ for ALL paths
3. Each file MUST have complete headers (diff --git, ---, +++)
4. Hunk headers @@ MUST match actual line counts
5. Context lines: space, additions: +, deletions: -
6. NO smart quotes, NO CRLF (LF only)
7. Maximum 3 files per patch
```

**Exemples concrets fournis** :
- Exemple nouveau fichier avec `/dev/null`
- Exemple modification avec index et hunks corrects
- Format exact attendu avec compteurs

**Si validation échoue** :
- L'erreur est passée dans `error_hint` au prochain attempt
- Le LLM peut corriger en fonction du message Git

---

## 📊 Flux Complet Amélioré

```
1. DeveloperAgent génère patch (instructions strictes) ✅
   ↓
2. _save_patch_artifact() → artifacts/patches/ ✅
   ↓
3. _advanced_patch_sanity_checks() ✅
   ├─ Erreurs détectées → return False (patch rejeté)
   └─ Validation OK → continue
   ↓
4. git apply --check --index --unsafe-paths ✅
   ├─ Échec → _log_patch_failure_details() + return False
   └─ Succès → continue
   ↓
5. git apply --verbose (application réelle) ✅
   ├─ Échec → Tentative 3-way merge
   └─ Succès → continue
   ↓
6. _verify_patch_applied() (post-apply guard) ✅
   ├─ Aucun changement détecté → return False
   └─ Changements confirmés → return True
```

---

## 🔧 Fichiers Modifiés

### 1. `/app/backend/orchestrator/tools.py`
- **Signature** : `apply_patch(patch_text, project_path, run_id=None)`
- **Nouvelles fonctions** :
  - `_save_patch_artifact()` (40 lignes)
  - `_advanced_patch_sanity_checks()` (150 lignes)
  - `_verify_patch_applied()` (25 lignes)
  - `_log_patch_failure_details()` (60 lignes)
- **Total ajouté** : ~275 lignes

### 2. `/app/backend/orchestrator/agents/developer.py`
- **Fonction modifiée** : `_build_prompt()`
- **Changement** : Instructions LLM renforcées (+30 lignes)

### 3. `/app/backend/server.py`
- **Fonction modifiée** : Boucle d'exécution iterative (ligne ~1458)
- **Changement** : Passage du `run_id` à `apply_patch()`

---

## 🧪 Tests Recommandés

### Test 1 - Vérifier sauvegarde artifacts :
```bash
ls -lh /path/to/projects/<run_id>/artifacts/patches/
# Devrait contenir : <timestamp>_patch.patch et <timestamp>_patch.meta.json
```

### Test 2 - Vérifier logs détaillés :
- Lancer un projet Laravel avec patches
- Chercher dans les logs backend :
  - `📄 Patch artifact saved`
  - `🔍 PATCH APPLICATION FAILURE DETAILS` (si échec)
  - `📍 Problematic line XX`

### Test 3 - Vérifier sanity checks :
- Intentionnellement créer un patch invalide (sans headers)
- Vérifier que sanity checks le rejettent avant git apply

### Test 4 - Vérifier post-apply guard :
- Patch qui passe git apply mais ne modifie rien
- Vérifier que `_verify_patch_applied()` le détecte

---

## 📈 Résultats Attendus

### Avant corrections :
```
❌ Patch application failed: error: corrupt patch at line 36
❌ 3-way merge also failed: error: corrupt patch at line 36
```

### Après corrections :
```
✅ Patch sanity checks passed (file_count=2, warnings=0)
✅ git apply --check succeeded
✅ Patch applied successfully and verified
📄 Patch artifact saved: /path/to/.../20251011_154530_patch.patch
```

### Si échec persiste :
```
❌ Patch sanity checks failed: ['Missing --- header for file a/...'  ]
📄 Full patch saved at: /path/to/.../20251011_154530_patch.patch
🔍 PATCH APPLICATION FAILURE DETAILS
📍 Problematic line 36:
    34: +++ b/resources/views/carousel.blade.php
    35: @@ -0,0 +1,10 @@
>>> 36: +<div class="carousel">
    37: +    <button>Previous</button>
```

→ Permet investigation immédiate avec patch sauvegardé

---

## 🎯 Prochaines Étapes

1. **Tester avec un nouveau run Laravel** pour vérifier que les patches sont bien générés et appliqués
2. **Consulter les artifacts** en cas d'échec pour analyse manuelle
3. **Si patches toujours corrompus** : Ajuster le prompt LLM avec exemples plus spécifiques au type de fichier (blade, js, css)
4. **Monitoring** : Suivre le taux de succès des patches sur 10+ runs

---

## 📞 Points de Contact

- **Artifacts directory** : `projects/<run_id>/artifacts/patches/`
- **Logs backend** : Chercher `🔍 PATCH APPLICATION FAILURE DETAILS`
- **Métadonnées** : Fichiers `.meta.json` contiennent SHA-256 et infos

---

**Date** : 2025-01-11  
**Version** : 1.0  
**Status** : ✅ Implémenté, en attente de tests
