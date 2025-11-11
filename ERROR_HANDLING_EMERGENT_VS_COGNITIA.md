# 🔍 GESTION D'ERREURS: Emergent.sh vs Cognitia

**Erreur détectée**: `'LaravelHandler' object has no attribute 'tool_manager'`  
**Cause**: Code ajouté en Phase 2 sans vérifier la structure existante

---

## 🎭 COMMENT EMERGENT.SH GÈRE CES ERREURS

### 1️⃣ Architecture Tool-Based = Errors Visibles Immédiatement

**Emergent.sh (MOI)**:
```python
# Je fais les opérations UNE PAR UNE
<mcp_create_file>
  <path>/app/routes/web.php</path>
  ...
</mcp_create_file>

# Résultat immédiat
✅ File created successfully

# Opération suivante
<mcp_view_file>
  <path>/app/routes/web.php</path>
</mcp_view_file>

# Si erreur (ex: file not found)
❌ Error: File does not exist

# JE VOIS L'ERREUR IMMÉDIATEMENT
# → Je corrige ou j'adapte mon approche
```

**Avantages**:
- ✅ Feedback immédiat après chaque action
- ✅ Je peux adapter ma stratégie en temps réel
- ✅ Erreurs isolées (une opération n'affecte pas les autres)
- ✅ Pas de "cascade failures"

**Désavantages**:
- ⚠️ Plus lent (séquentiel)
- ⚠️ Plus de calls API

---

### 2️⃣ Setup Automatique = Je Ne Le Fais Pas

**Emergent.sh (MOI)**:
```python
# Je ne fais PAS de "setup automatique PHPStan"
# Pourquoi?
# 1. Je n'ai pas accès à la structure interne du système
# 2. Je travaille avec des tools, pas avec des objets Python
# 3. Si PHPStan est requis, je le configure MANUELLEMENT

# Exemple: Si l'utilisateur dit "setup PHPStan"
<mcp_create_file>
  <path>/app/phpstan.neon</path>
  <file_text>parameters:
    level: 0
    paths:
        - app
</file_text>
</mcp_create_file>

<mcp_execute_bash>
  <command>cd /app && composer require --dev phpstan/phpstan</command>
</mcp_execute_bash>

# Pas de "auto-setup caché" qui peut échouer silencieusement
```

**Principe**: **Explicit > Implicit**
- Je fais SEULEMENT ce qui est demandé
- Pas de magie cachée
- Si quelque chose est nécessaire, je le fais explicitement

---

### 3️⃣ Error Handling = Non-Bloquant par Design

**Emergent.sh (MOI)**:
```python
# Si une opération échoue, je ne bloque PAS tout

# Exemple:
<mcp_create_file>
  <path>/app/Controller.php</path>
  ...
</mcp_create_file>
✅ Success

<mcp_lint_php>  # Tentative de lint
  <path>/app/Controller.php</path>
</mcp_lint_php>
❌ Warning: Pint not found

# JE CONTINUE quand même!
# Je ne bloque pas tout le run pour un lint qui échoue

<mcp_create_file>  # Opération suivante
  <path>/app/routes/web.php</path>
  ...
</mcp_create_file>
✅ Success
```

**Principe**: **Fail Gracefully**
- Les erreurs "nice-to-have" (lint, format) ne bloquent pas
- Les erreurs "must-have" (file creation) bloquent et je retry

---

### 4️⃣ Try-Catch Systematique

**Emergent.sh**:
```python
# Dans mon système prompt, j'ai des instructions:
"If a tool call fails, log the error and continue with alternative approach"

# Exemple mental process:
1. Try: Create file with Pint formatting
2. If Pint fails: Create file without formatting
3. Log: "Note: File created but not formatted (Pint unavailable)"
4. Continue to next operation

# Je ne laisse JAMAIS un échec bloquer tout le workflow
```

---

## 🔧 LE PROBLÈME DANS COGNITIA

### Code Problématique (Ajouté en Phase 2)

**Fichier**: `/app/backend/orchestrator/stacks/laravel_handler.py`

```python
# Ligne ~385 (ajouté par moi)
# 🔥 FIX CRITIQUE: Setup PHPStan with baseline immediately after installation
if self.tool_manager:  # ❌ PROBLÈME ICI
    if self.logger:
        self.logger.info("🔧 Setting up PHPStan with permissive config and baseline...")
    try:
        await self.tool_manager._setup_phpstan_for_laravel(str(code_path))
    except Exception as e:
        if self.logger:
            self.logger.warning(f"⚠️ PHPStan setup failed (non-blocking): {e}")
```

**Pourquoi ça échoue**:
```python
# LaravelHandler n'a PAS d'attribut tool_manager
# La condition if self.tool_manager: échoue AVANT le try-catch
# Donc l'exception n'est même pas catchée

# C'est une erreur de ma part - j'ai supposé que tool_manager existait
```

---

## ✅ CORRECTION IMMÉDIATE

### Option 1: Rendre Totalement Non-Bloquant (RECOMMANDÉ)

```python
# Remplacer par:
try:
    # Vérifier si tool_manager existe ET est disponible
    if hasattr(self, 'tool_manager') and self.tool_manager:
        if self.logger:
            self.logger.info("🔧 Setting up PHPStan with permissive config and baseline...")
        await self.tool_manager._setup_phpstan_for_laravel(str(code_path))
except AttributeError:
    # tool_manager n'existe pas, skip silencieusement
    if self.logger:
        self.logger.debug("tool_manager not available, skipping PHPStan auto-setup")
except Exception as e:
    # Autres erreurs, log mais continue
    if self.logger:
        self.logger.warning(f"⚠️ PHPStan setup failed (non-blocking): {e}")
```

**Principe Emergent**: **Degrade Gracefully**
- Si tool_manager existe → Setup PHPStan
- Si tool_manager n'existe pas → Skip, continue
- Si setup échoue → Log warning, continue
- **JAMAIS bloquer la création du projet**

---

### Option 2: Retirer Complètement (SAFE)

```python
# Simplement retirer les lignes ajoutées
# Le PHPStan setup existait AVANT dans le code original
# Donc ça marchait déjà sans mon ajout

# Retour à l'état original = safe
```

---

## 🎯 PHILOSOPHIE EMERGENT vs COGNITIA

### Emergent.sh (MOI)

**Principe**: "Better done than perfect"

| Aspect | Approche |
|--------|----------|
| **Setup automatique** | ❌ Non, tout explicite |
| **Error handling** | ✅ Try-catch sur TOUT |
| **Fail behavior** | Continue, log warning |
| **User feedback** | Immédiat après chaque action |
| **Rollback** | Facile (une action à la fois) |

**Résultat**: 
- Moins de features "magiques"
- Plus robuste face aux erreurs
- User voit exactement ce qui se passe

---

### Cognitia (Architecture Actuelle)

**Principe**: "Smart automation with safety nets"

| Aspect | Approche Avant | Devrait Être |
|--------|----------------|--------------|
| **Setup automatique** | ✅ Beaucoup | ✅ Beaucoup (c'est bien!) |
| **Error handling** | ⚠️ Parfois manquant | ✅ Toujours présent |
| **Fail behavior** | ❌ Bloque tout | ✅ Continue avec log |
| **User feedback** | Batch final | ✅ Opération par opération |
| **Rollback** | Complexe | ✅ Améliorer |

**Résultat**: 
- Plus de features "magiques" (bien!)
- MAIS doit être plus robuste face aux erreurs
- User doit voir les warnings sans que ça bloque

---

## 📋 BEST PRACTICES POUR COGNITIA

### Règle #1: Tout Code Doit Avoir Try-Catch

```python
# ❌ MAUVAIS
if self.tool_manager:
    await self.tool_manager.do_something()

# ✅ BON
try:
    if hasattr(self, 'tool_manager') and self.tool_manager:
        await self.tool_manager.do_something()
except Exception as e:
    logger.warning(f"Optional feature failed: {e}")
    # Continue sans bloquer
```

---

### Règle #2: Distinguer Critical vs Optional

```python
# CRITICAL: Must succeed or abort
try:
    project = await create_laravel_project()
    if not project:
        raise Exception("Project creation failed")
except Exception as e:
    logger.error(f"❌ CRITICAL: {e}")
    raise  # Bloquer ici est OK

# OPTIONAL: Nice-to-have
try:
    await setup_phpstan()
except Exception as e:
    logger.warning(f"⚠️ OPTIONAL failed: {e}")
    pass  # Continue sans bloquer
```

---

### Règle #3: Log Everything

```python
# Emergent principle: User should see what's happening

logger.info("🔧 Attempting PHPStan setup...")
try:
    result = await setup_phpstan()
    logger.info("✅ PHPStan setup successful")
except Exception as e:
    logger.warning(f"⚠️ PHPStan setup failed (non-blocking): {e}")
    logger.info("ℹ️ Continuing without PHPStan - you can set it up manually later")
```

---

### Règle #4: Hasattr > Direct Access

```python
# ❌ MAUVAIS (assume l'attribut existe)
if self.tool_manager:
    ...

# ✅ BON (vérifie d'abord)
if hasattr(self, 'tool_manager') and self.tool_manager:
    ...

# ✅ ENCORE MIEUX (avec getattr default)
tool_manager = getattr(self, 'tool_manager', None)
if tool_manager:
    ...
```

---

## 🚀 CORRECTION À APPLIQUER MAINTENANT

Je vais appliquer la correction Option 1 (non-bloquant avec hasattr).

**Fichiers à modifier**:
- `/app/backend/orchestrator/stacks/laravel_handler.py` (ligne ~385)

**Changement**:
```python
# AVANT (bugué)
if self.tool_manager:
    ...

# APRÈS (robuste)
try:
    if hasattr(self, 'tool_manager') and self.tool_manager:
        ...
except Exception as e:
    logger.debug(f"PHPStan auto-setup skipped: {e}")
```

---

## 💡 LEÇONS APPRISES

### Pour Cognitia

1. **Toujours hasattr() avant accès attribut**
2. **Try-catch sur TOUT code "nice-to-have"**
3. **Log warnings au lieu de raise pour optional features**
4. **Tester dans environnement réel avant deploy**

### Pourquoi Emergent Évite Ces Erreurs

1. **Pas de state interne** (je travaille avec tools, pas objets)
2. **Feedback immédiat** (je vois erreur tout de suite)
3. **Architecture simple** (pas de setup caché)
4. **Explicit > Implicit** (je fais ce qui est demandé, rien de plus)

---

## ✅ CONCLUSION

**L'erreur actuelle**: AttributeError sur tool_manager  
**Comment Emergent évite ça**: Pas de setup automatique caché, tout explicite  
**Comment corriger**: hasattr() + try-catch avec log warning  

**Principe clé**: **Graceful Degradation**
- Feature disponible → l'utiliser
- Feature indisponible → skip avec log
- **JAMAIS bloquer pour une feature optionnelle**

Je corrige ça immédiatement!
