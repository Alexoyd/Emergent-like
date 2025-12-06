# 🧪 Guide de Test - Cognitia Style Emergent

## Test Rapide : Validation du Système

### Test 1 : Import des Templates ✅

```bash
cd /app/backend
python -c "from orchestrator.templates.laravel_crud_templates import *; print('✅ All templates imported successfully')"
```

**Résultat attendu :** Message de succès sans erreur

---

### Test 2 : Vérification des Guidelines

```bash
cd /app/backend
python << 'EOF'
from orchestrator.templates.laravel_crud_templates import get_crud_guidelines_for_prompt

guidelines = get_crud_guidelines_for_prompt()
print(f"✅ Guidelines length: {len(guidelines)} chars")
print(f"✅ Contains 'CHECKLIST': {'CHECKLIST' in guidelines}")
print(f"✅ Contains '9 operations': {'9' in guidelines}")
print(f"✅ Contains 'MIGRATION': {'MIGRATION' in guidelines}")
print(f"✅ Contains 'CONTROLLER': {'CONTROLLER' in guidelines}")
print(f"✅ Contains 'VIEWS': {'VIEW' in guidelines}")
print(f"✅ Contains JSON example: {'operations' in guidelines}")
EOF
```

**Résultat attendu :** Toutes les vérifications doivent être ✅

---

### Test 3 : Génération de Template Controller

```bash
cd /app/backend
python << 'EOF'
from orchestrator.templates.laravel_crud_templates import get_controller_template

controller = get_controller_template("Game", "games")

# Vérifications
checks = {
    "index method": "public function index()" in controller,
    "create method": "public function create()" in controller,
    "store method": "public function store(" in controller,
    "show method": "public function show(" in controller,
    "edit method": "public function edit(" in controller,
    "update method": "public function update(" in controller,
    "destroy method": "public function destroy(" in controller,
    "pagination": "paginate(10)" in controller,
    "validation": "validate([" in controller,
    "flash message": "with('success'" in controller,
    "namespace": "namespace App\\Http\\Controllers" in controller,
    "use Model": "use App\\Models\\Game" in controller,
}

print("🔍 Controller Template Verification:\n")
for check, result in checks.items():
    status = "✅" if result else "❌"
    print(f"{status} {check}")

if all(checks.values()):
    print("\n✅ ALL CHECKS PASSED - Controller template is complete!")
else:
    print("\n❌ SOME CHECKS FAILED")
    failed = [k for k, v in checks.items() if not v]
    print(f"Failed checks: {failed}")
EOF
```

**Résultat attendu :** Tous les checks doivent être ✅

---

### Test 4 : Génération de Template Vue Index

```bash
cd /app/backend
python << 'EOF'
from orchestrator.templates.laravel_crud_templates import get_index_view_template

view = get_index_view_template("games", "Game")

# Vérifications
checks = {
    "extends layout": "@extends('layouts.app')" in view,
    "section content": "@section('content')" in view,
    "table": "<table" in view,
    "pagination": "->links()" in view,
    "create button": "route('games.create')" in view,
    "edit action": "route('games.edit'" in view,
    "delete form": "@method('DELETE')" in view,
    "empty state": "Aucun Game" in view or "Aucun" in view,
    "Tailwind classes": "bg-" in view and "text-" in view,
    "foreach loop": "@foreach" in view,
}

print("🔍 Index View Template Verification:\n")
for check, result in checks.items():
    status = "✅" if result else "❌"
    print(f"{status} {check}")

if all(checks.values()):
    print("\n✅ ALL CHECKS PASSED - Index view template is complete!")
else:
    print("\n❌ SOME CHECKS FAILED")
    failed = [k for k, v in checks.items() if not v]
    print(f"Failed checks: {failed}")
EOF
```

**Résultat attendu :** Tous les checks doivent être ✅

---

### Test 5 : Génération de Template Layout

```bash
cd /app/backend
python << 'EOF'
from orchestrator.templates.laravel_crud_templates import get_layout_template

layout = get_layout_template()

# Vérifications
checks = {
    "DOCTYPE": "<!DOCTYPE html>" in layout,
    "csrf token": "csrf_token" in layout,
    "vite directive": "@vite" in layout,
    "fallback css": "asset('css/app.css')" in layout,
    "navigation": "<nav" in layout,
    "flash success": "session('success')" in layout,
    "flash error": "session('error')" in layout,
    "Tailwind classes": "bg-white" in layout and "shadow" in layout,
    "SVG icons": "<svg" in layout,
    "content section": "@yield('content')" in layout,
    "responsive": "max-w-7xl" in layout,
}

print("🔍 Layout Template Verification:\n")
for check, result in checks.items():
    status = "✅" if result else "❌"
    print(f"{status} {check}")

if all(checks.values()):
    print("\n✅ ALL CHECKS PASSED - Layout template is complete!")
else:
    print("\n❌ SOME CHECKS FAILED")
    failed = [k for k, v in checks.items() if not v]
    print(f"Failed checks: {failed}")
EOF
```

**Résultat attendu :** Tous les checks doivent être ✅

---

### Test 6 : DeveloperAgentDirect Integration

```bash
cd /app/backend
python << 'EOF'
import sys
sys.path.insert(0, '/app/backend')

from orchestrator.agents.developer_direct import DeveloperAgentDirect

# Créer une instance mock pour tester _stack_guidelines
class MockLLM:
    pass

class MockRAG:
    pass

class MockTools:
    pass

agent = DeveloperAgentDirect(
    llm_router=MockLLM(),
    rag_system=MockRAG(),
    tool_manager=MockTools(),
    max_attempts=3
)

# Tester la génération des guidelines Laravel
guidelines = agent._stack_guidelines("laravel")

print("🔍 DeveloperAgentDirect Integration Verification:\n")

checks = {
    "Guidelines not empty": len(guidelines) > 0,
    "Guidelines length > 1000": len(guidelines) > 1000,
    "Contains CRUD PROTOCOL": "CRUD" in guidelines.upper(),
    "Contains CHECKLIST": "CHECKLIST" in guidelines.upper() or "CHECK" in guidelines.upper(),
    "Contains MIGRATION": "MIGRATION" in guidelines.upper(),
    "Contains CONTROLLER": "CONTROLLER" in guidelines.upper(),
    "Contains VIEWS": "VIEW" in guidelines.upper(),
    "Contains operations example": "operations" in guidelines,
    "Contains 7 methods mention": "7" in guidelines,
}

for check, result in checks.items():
    status = "✅" if result else "❌"
    print(f"{status} {check}")

print(f"\n📊 Guidelines length: {len(guidelines)} chars")

if all(checks.values()):
    print("\n✅ ALL CHECKS PASSED - DeveloperAgentDirect integration successful!")
else:
    print("\n❌ SOME CHECKS FAILED")
    failed = [k for k, v in checks.items() if not v]
    print(f"Failed checks: {failed}")
EOF
```

**Résultat attendu :** Tous les checks doivent être ✅

---

### Test 7 : Backend API Health Check

```bash
curl -s http://localhost:8001/api/ | head -20
```

**Résultat attendu :** Réponse JSON avec status, version, et informations du système

---

## 🎯 Test End-to-End Complet

### Scénario : Créer une application Game Management

**Prérequis :**
- Backend et frontend démarrés
- Base de données MongoDB active

**Étapes :**

1. **Créer un nouveau projet Laravel via API**
```bash
curl -X POST http://localhost:8001/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Créer un système de gestion de jeux de cartes avec nom, description et nombre de cartes",
    "stack": "laravel",
    "project_mode": "create"
  }'
```

2. **Noter le run_id et project_id dans la réponse**

3. **Vérifier la génération des fichiers**
```bash
# Remplacer PROJECT_ID par l'ID réel
ls -la /app/projects/PROJECT_ID/code/app/Http/Controllers/
ls -la /app/projects/PROJECT_ID/code/app/Models/
ls -la /app/projects/PROJECT_ID/code/resources/views/
ls -la /app/projects/PROJECT_ID/code/database/migrations/
```

**Vérifications attendues :**
```
✅ GameController.php avec 7 méthodes
✅ Game.php (model)
✅ create_games_table.php (migration)
✅ resources/views/layouts/app.blade.php
✅ resources/views/games/index.blade.php
✅ resources/views/games/create.blade.php
✅ resources/views/games/edit.blade.php
✅ resources/views/games/show.blade.php
✅ routes/web.php avec Route::resource
```

4. **Vérifier le contenu du Controller**
```bash
cat /app/projects/PROJECT_ID/code/app/Http/Controllers/GameController.php
```

**Doit contenir :**
- `public function index()`
- `public function create()`
- `public function store(Request $request)`
- `public function show(Game $game)`
- `public function edit(Game $game)`
- `public function update(Request $request, Game $game)`
- `public function destroy(Game $game)`
- `->paginate(10)`
- `->with('success'`

5. **Vérifier le layout**
```bash
cat /app/projects/PROJECT_ID/code/resources/views/layouts/app.blade.php
```

**Doit contenir :**
- Tailwind CSS classes
- Flash messages
- Navigation
- SVG icons
- Responsive design

---

## 📊 Critères de Réussite

### ✅ Tests Unitaires (Modules)
- [ ] Import templates sans erreur
- [ ] Guidelines > 8000 chars
- [ ] Controller template avec 7 méthodes
- [ ] Vues avec Tailwind CSS
- [ ] Layout avec flash messages
- [ ] Integration DeveloperAgentDirect

### ✅ Tests d'Intégration
- [ ] Backend démarre sans erreur
- [ ] API accessible
- [ ] Templates importables depuis developer_direct.py
- [ ] Guidelines chargées correctement

### ✅ Test End-to-End
- [ ] Création projet Laravel via API
- [ ] 9 fichiers générés automatiquement
- [ ] Controller avec 7 méthodes complètes
- [ ] Vues avec design moderne
- [ ] Routes fonctionnelles
- [ ] Application accessible

---

## 🐛 Dépannage

### Erreur : "Module templates not found"
```bash
# Vérifier que le module existe
ls -la /app/backend/orchestrator/templates/

# Vérifier le contenu
cat /app/backend/orchestrator/templates/__init__.py

# Redémarrer le backend
sudo supervisorctl restart backend
```

### Erreur : "Guidelines empty"
```bash
# Vérifier l'import
cd /app/backend
python -c "from orchestrator.templates.laravel_crud_templates import get_crud_guidelines_for_prompt; print(len(get_crud_guidelines_for_prompt()))"

# Devrait afficher un nombre > 8000
```

### Backend ne démarre pas
```bash
# Vérifier les logs
tail -n 50 /var/log/supervisor/backend.err.log

# Redémarrer proprement
sudo supervisorctl stop backend
sleep 2
sudo supervisorctl start backend
sudo supervisorctl status backend
```

---

## 📝 Checklist Finale

Avant de considérer le système validé, vérifier :

- [ ] ✅ Tous les tests unitaires passent
- [ ] ✅ Backend démarre sans erreur
- [ ] ✅ Templates importables
- [ ] ✅ Guidelines > 8000 chars
- [ ] ✅ Controller template complet (7 méthodes)
- [ ] ✅ Vues template avec Tailwind
- [ ] ✅ Layout avec flash messages
- [ ] ✅ Test end-to-end réussi (9 fichiers générés)

**Si toutes les cases sont cochées : 🎉 SYSTÈME VALIDÉ !**

---

## 🚀 Utilisation en Production

### Commande Rapide de Test

```bash
# Exécuter tous les tests d'un coup
cd /app && bash << 'TESTSCRIPT'
echo "🧪 COGNITIA EMERGENT STYLE - TESTS COMPLETS"
echo "==========================================="
echo ""

echo "Test 1: Import Templates"
cd /app/backend && python -c "from orchestrator.templates.laravel_crud_templates import *; print('✅ Templates imported')" || echo "❌ FAILED"
echo ""

echo "Test 2: Guidelines Length"
cd /app/backend && python -c "from orchestrator.templates.laravel_crud_templates import get_crud_guidelines_for_prompt; g=get_crud_guidelines_for_prompt(); print(f'✅ Guidelines: {len(g)} chars') if len(g) > 8000 else print('❌ FAILED')" || echo "❌ FAILED"
echo ""

echo "Test 3: Controller Template"
cd /app/backend && python -c "from orchestrator.templates.laravel_crud_templates import get_controller_template; c=get_controller_template('Game','games'); print('✅ Controller complete') if all(m in c for m in ['index','create','store','show','edit','update','destroy']) else print('❌ FAILED')" || echo "❌ FAILED"
echo ""

echo "Test 4: Backend Status"
curl -s http://localhost:8001/api/ > /dev/null && echo "✅ Backend accessible" || echo "❌ Backend down"
echo ""

echo "==========================================="
echo "🎯 Tests terminés!"
TESTSCRIPT
```

**Résultat attendu :** Tous les tests doivent afficher ✅

---

**Date :** $(date +%Y-%m-%d)  
**Version :** 1.0
