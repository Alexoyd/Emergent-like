# Corrections des problèmes identifiés dans les logs

## Problèmes détectés

### 1. Erreur 'await on string' (CRITIQUE)
**Localisation**: `orchestrator.tools.run_test()` ligne 452+
**Erreur**: `object str can't be used in 'await' expression`
**Cause**: Les descriptions de tests Laravel ("pest -q", etc.) dans server.py ligne 1962-1966 peuvent créer confusion
**Impact**: Tests Laravel (pest/phpstan/pint) systématiquement skippés

### 2. Patches corrompus (CRITIQUE)
**Localisation**: `orchestrator.tools.apply_patch()`
**Erreurs**: 
- `error: corrupt patch at line 37` pour resources/js/slider.js
- `error: corrupt patch at line 42` pour resources/css/slider.css
**Cause**: Génération de patches invalides par DeveloperAgent
**Impact**: Impossibilité d'appliquer les modifications de code

### 3. Désynchronisation UI/Backend (HIGH)
**Localisation**: server.py ligne 1456-1469
**Problème**: Le frontend affiche "Patch applied successfully" alors que le backend log "❌ Patch application failed"
**Cause**: L'exception lors de apply_patch n'est pas correctement propagée au frontend
**Impact**: UI incohérente, utilisateur pense que tout fonctionne

### 4. SQLite driver warning (LOW)
**Message**: `WARN could not find driver (Connection: sqlite...)`
**Impact**: Non bloquant mais pollue les logs

## Plan de correction

### Phase 1: Corriger l'erreur 'await on string'
- [ ] Vérifier que _get_test_commands retourne toujours List[List[str]]
- [ ] S'assurer qu'aucun string n'est directement awaité dans tools.py

### Phase 2: Améliorer la génération de patches
- [ ] Renforcer la validation des patches dans developer.py
- [ ] Améliorer les headers diff dans _try_repair_patch()
- [ ] Ajouter plus de cas de test pour la génération

### Phase 3: Synchroniser UI/Backend
- [ ] Propager correctement les erreurs d'application de patch
- [ ] Modifier le log "Patch applied successfully" pour vérifier le succès réel
- [ ] Ajouter validation stricte côté frontend

### Phase 4: SQLite warning (optionnel)
- [ ] Installer pdo_sqlite ou configurer une autre DB pour tests

## Files à modifier
1. `/app/backend/server.py` - Lignes 1456-1469, 1962-1980
2. `/app/backend/orchestrator/tools.py` - run_test(), smart_command_execution()
3. `/app/backend/orchestrator/agents/developer.py` - Génération patches
4. Potentiellement: Frontend pour meilleure validation
