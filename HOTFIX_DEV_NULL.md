# 🔥 HOTFIX: /dev/null Rejection Bug

## Problème Identifié
Le sanity check ajouté dans `tools.py` rejetait **incorrectement** `/dev/null` comme un "chemin absolu non autorisé".

### Logs d'erreur observés :
```
❌ Patch sanity checks failed: ['Absolute path not allowed: /dev/null']
📄 Failed patch saved to: .../artifacts/patches/20251011_165348_patch.patch
```

## Pourquoi `/dev/null` est spécial ?

Dans Git, `/dev/null` est un **chemin réservé** utilisé pour :

1. **Nouveaux fichiers** (création) :
```diff
diff --git a/resources/views/home.blade.php b/resources/views/home.blade.php
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/resources/views/home.blade.php
@@ -0,0 +1,10 @@
+<html>...
```

2. **Fichiers supprimés** (deletion) :
```diff
diff --git a/old-file.txt b/old-file.txt
deleted file mode 100644
index abc1234..0000000
--- a/old-file.txt
+++ /dev/null
@@ -1,5 +0,0 @@
-deleted content
```

**⚠️ Rejeter `/dev/null` empêche la création/suppression de fichiers !**

## Correction Appliquée

**Fichier** : `/app/backend/orchestrator/tools.py`  
**Fonction** : `_advanced_patch_sanity_checks()`  
**Ligne** : ~447

### Avant (BUGGY) :
```python
if line.startswith('+++') or line.startswith('---'):
    path_part = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) > 1 else ""
    # Remove a/ or b/ prefix
    if path_part.startswith('a/') or path_part.startswith('b/'):
        path_part = path_part[2:]
    
    if '..' in path_part:
        errors.append(f"Dangerous path with '..': {path_part}")
    if path_part.startswith('/'):  # ❌ BUG: Rejette aussi /dev/null !
        errors.append(f"Absolute path not allowed: {path_part}")
```

### Après (CORRIGÉ) :
```python
if line.startswith('+++') or line.startswith('---'):
    path_part = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) > 1 else ""
    
    # ✅ /dev/null is a special case for new/deleted files - ALLOWED
    if path_part == '/dev/null':
        continue
    
    # Remove a/ or b/ prefix
    if path_part.startswith('a/') or path_part.startswith('b/'):
        path_part = path_part[2:]
    
    if '..' in path_part:
        errors.append(f"Dangerous path with '..': {path_part}")
    if path_part.startswith('/'):
        errors.append(f"Absolute path not allowed: {path_part}")
```

## Impact

### Avant le hotfix :
- ❌ Tous les patches créant de nouveaux fichiers étaient rejetés
- ❌ Tous les patches supprimant des fichiers étaient rejetés
- ❌ Logs affichaient "Absolute path not allowed: /dev/null"
- ❌ Frontend : "Patch application failed - patch may be corrupted or invalid"

### Après le hotfix :
- ✅ Nouveaux fichiers : autorisés
- ✅ Suppressions : autorisées
- ✅ Modifications : autorisées (déjà OK)
- ✅ Chemins dangereux (`..`, `/etc/passwd`, etc.) : toujours rejetés

## Test de Validation

Pour vérifier que le hotfix fonctionne :

1. **Lancer un nouveau run Laravel** avec création de fichiers
2. **Vérifier dans les logs** :
   - ✅ Plus d'erreur "Absolute path not allowed: /dev/null"
   - ✅ "Patch sanity checks passed"
   - ✅ "Patch applied successfully and verified"

3. **Si patch sauvegardé** (artifacts/patches/) :
   - Vérifier présence de `--- /dev/null` ou `+++ /dev/null`
   - Confirmer que le fichier est valide selon Git

## Autres Cas Spéciaux Git

Pour référence, voici d'autres patterns Git valides à **NE PAS** rejeter :

- ✅ `/dev/null` (nouveaux/supprimés)
- ✅ `a/path/to/file` et `b/path/to/file` (préfixes Git)
- ✅ `index 0000000..abc1234` (hash pour nouveaux fichiers)
- ✅ `index abc1234..0000000` (hash pour fichiers supprimés)

À **toujours rejeter** :
- ❌ `../../../etc/passwd` (directory traversal)
- ❌ `/etc/passwd` (chemin absolu réel)
- ❌ `\x00` (NULL byte)

## Status

- ✅ Hotfix appliqué
- ✅ Compilation validée
- ⏳ En attente de test utilisateur

---

**Date** : 2025-01-11  
**Version** : Hotfix 1.0  
**Criticité** : 🔥 HIGH (bloquait toutes les créations de fichiers)
