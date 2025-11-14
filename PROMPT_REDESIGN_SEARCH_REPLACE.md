# 🔥 Prompt Redesign RADICAL - search_replace Instructions

**Date**: 2025-01-XX  
**Problème**: LLM ignore instructions et invente du texte au lieu de copier  
**Solution**: Prompt **ultra-directif** avec format visuel et process étape-par-étape  
**Status**: ✅ Implémenté et déployé

---

## 🎯 Diagnostic du Problème

### Ce qui ne marchait PAS (avant)

**Prompt original** :
```
🚨 When using 'search_replace', copy the EXACT text from below!
🚨 DO NOT guess - use these exact strings!
```

**Résultat** :
- Step 4 Attempt 1: ❌ "Search text not found"
- Step 4 Attempt 2: ❌ "Search text not found"  
- Step 4 Attempt 3: ❌ "Search text not found"

**Diagnostic** :
- Le LLM LIT l'instruction
- Mais NE L'APPLIQUE PAS
- Il invente un search pattern qui n'existe pas dans le fichier
- Même avec le contenu du fichier fourni dans le prompt

---

## 💡 Pourquoi Ça Ne Marchait Pas

### Analyse Psychologique du LLM

Les LLM ont tendance à :
1. ✅ Comprendre les instructions globales
2. ❌ Mais "optimiser" ou "paraphraser" quand ils génèrent
3. ❌ Préférer créer du contenu "logique" plutôt que copier strictement
4. ❌ Ne pas faire le lien entre "file contents above" et "use in search"

**Problème fondamental** : Instructions trop **abstraites**, pas assez **procédurales**

---

## 🔧 Solution Implémentée : Approche RADICALE

### Principe : De l'Abstrait au Concret

**AVANT (abstrait)** :
> "Copy the EXACT text"

**APRÈS (procédural)** :
> "Step 1: Scroll up and find the file in 'CURRENT FILE CONTENTS' section  
> Step 2: Locate the section you want to modify  
> Step 3: Copy 5-10 lines including the section  
> Step 4: Paste EXACTLY into 'search' field  
> Step 5: Modify the copied text and put in 'replace' field"

---

## 📋 Changements Implémentés

### 1. Bloc de Contenu Révisé (Lignes 345-389)

**AVANT** :
```
📄 CURRENT FILE CONTENTS (CRITICAL - READ BEFORE search_replace!):
🚨 These are the ACTUAL current contents of important files.
🚨 When using 'search_replace', copy the EXACT text from below!

### routes/web.php
```
[contenu du fichier]
```
```

**APRÈS** :
```
================================================================================
📄 CURRENT FILE CONTENTS - MANDATORY READING
================================================================================

🚨🚨🚨 CRITICAL INSTRUCTIONS FOR search_replace OPERATIONS 🚨🚨🚨

IF YOU USE 'search_replace' WITHOUT READING THIS, YOUR OPERATION WILL FAIL!

RULES (FOLLOW EXACTLY OR OPERATION FAILS):
1. ✅ DO: Copy the EXACT text from the file contents below
2. ✅ DO: Include surrounding lines for context (5-10 lines)
3. ✅ DO: Preserve ALL whitespace, indentation, quotes exactly
4. ❌ DON'T: Invent or guess what the file contains
5. ❌ DON'T: Paraphrase or summarize the content
6. ❌ DON'T: Use partial matches or fragments

⚠️ CONSEQUENCE: If your 'search' text doesn't match EXACTLY → Operation FAILS

📖 EXAMPLE OF CORRECT search_replace:
Given file content:
```php
Route::get('/', function () {
    return view('welcome');
});
```

✅ CORRECT search_replace:
{
  "type": "search_replace",
  "path": "routes/web.php",
  "search": "Route::get('/', function () {\n    return view('welcome');\n});",
  "replace": "Route::get('/', function () {\n    return view('dashboard');\n});"
}

❌ WRONG (will FAIL):
{
  "type": "search_replace",
  "search": "return view('welcome')",  // ❌ Missing context
  "replace": "return view('dashboard')"
}

NOW READ THE ACTUAL FILE CONTENTS BELOW:
================================================================================

FILE: routes/web.php
────────────────────────────────────────────────────────────────────────────────
CONTENT (Use this EXACT text for search_replace):
```
[contenu du fichier]
```
────────────────────────────────────────────────────────────────────────────────
⚠️ To modify this file, copy lines from above EXACTLY!
```

**Changements** :
- ✅ Séparateurs visuels (`===`, `───`)
- ✅ Instructions en liste numérotée (DO/DON'T)
- ✅ Exemple CONCRET (bon vs mauvais)
- ✅ Conséquences claires
- ✅ Augmentation max_chars : 800 → 5000 (plus de contexte)

---

### 2. Section search_replace Réécrite (Lignes 478-527)

**AVANT** :
```
• search_replace: Find and replace exact text (RECOMMENDED for routes/web.php)
  🚨 CRITICAL: You MUST know the EXACT current content before using search_replace!
  ⚠️ If unsure of file content, use RAG context or read file structure from plan
  ✅ Match whitespace, line breaks, and indentation EXACTLY
```

**APRÈS** :
```
• search_replace: Find and replace exact text
  
  🚨🚨🚨 ABSOLUTE REQUIREMENTS FOR search_replace 🚨🚨🚨
  
  IF FILE CONTENT IS PROVIDED ABOVE:
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. YOU MUST COPY THE EXACT TEXT FROM 'CURRENT FILE CONTENTS' SECTION ABOVE
  2. DO NOT INVENT OR GUESS THE CONTENT
  3. COPY AT LEAST 5-10 LINES OF CONTEXT FOR UNIQUE MATCH
  4. PRESERVE ALL WHITESPACE, INDENTATION, QUOTES EXACTLY AS SHOWN
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  
  ❌ OPERATION WILL FAIL IF:
  • Your 'search' text doesn't match the file EXACTLY (character-by-character)
  • You use partial text without enough context
  • You guess what the file contains instead of reading above
  
  ✅ STEP-BY-STEP PROCESS:
  Step 1: Scroll up and find the file in 'CURRENT FILE CONTENTS' section
  Step 2: Locate the section you want to modify
  Step 3: Copy 5-10 lines including the section (for unique match)
  Step 4: Paste EXACTLY into 'search' field
  Step 5: Modify the copied text and put in 'replace' field
  
  📖 CONCRETE EXAMPLE:
  Given file content above shows:
  ```
  Route::get('/', function () {
      return view('welcome');
  });
  ```
  
  ✅ CORRECT (copies exact text):
  "search": "Route::get('/', function () {\n    return view('welcome');\n});"
  
  ❌ WRONG (guessed/abbreviated):
  "search": "return view('welcome')"  // Too short, not unique
  "search": "Route::get('/')"          // Incomplete
```

**Changements** :
- ✅ Process en 5 étapes concrètes
- ✅ Liste des causes d'échec
- ✅ Exemple comparatif (bon vs mauvais)
- ✅ Format visuel imposant (━━━, 🚨🚨🚨)
- ✅ Instructions "IF/THEN" claires

---

## 🎓 Principes Appliqués

### 1. Format Visuel Imposant

**Pourquoi** : Attire l'attention du LLM vers les sections critiques

**Comment** :
- Lignes de séparation (`===`, `━━━`)
- Emojis répétés (`🚨🚨🚨`)
- ALL CAPS pour termes clés
- Espacement généreux

---

### 2. Instructions Procédurales (pas abstraites)

**Pourquoi** : Le LLM suit mieux des "steps" que des principes abstraits

**Comment** :
- "Step 1, Step 2, Step 3..." au lieu de "You should..."
- Verbes d'action : "Scroll up", "Copy", "Paste", "Modify"
- Séquence temporelle claire

---

### 3. Exemples Contrastés (DO vs DON'T)

**Pourquoi** : L'apprentissage par contraste est plus efficace

**Comment** :
- ✅ CORRECT : Montrer l'exemple exact attendu
- ❌ WRONG : Montrer exactement ce qu'il NE faut PAS faire
- Annotation : Expliquer POURQUOI c'est faux

---

### 4. Conséquences Explicites

**Pourquoi** : Le LLM doit comprendre l'impact de ses choix

**Comment** :
- "If X → Operation FAILS"
- "Will FAIL if..."
- "⚠️ CONSEQUENCE:"

---

### 5. Contexte Élargi (5KB au lieu de 2KB)

**Pourquoi** : Plus de contenu = LLM voit mieux le contexte

**Comment** :
- `max_chars = 5000` (était 2000)
- Pour tous les fichiers (pas juste routes/)

---

## 📊 Impact Attendu

### Avant (Test avec ancien prompt)

**Step 4 - Attempt 1** :
```
Generated: {"type": "search_replace", "search": "return view('welcome')"}
❌ Failed: Search text not found
```

**Step 4 - Attempt 2** :
```
Generated: {"type": "search_replace", "search": "Route::get('/')"}
❌ Failed: Search text not found
```

**Step 4 - Attempt 3** :
```
Generated: {"type": "search_replace", "search": "function ()"}
❌ Failed: Search text not found
```

**Résultat** : Step échoué après 3 tentatives

---

### Après (Test avec nouveau prompt - attendu)

**Step 4 - Attempt 1** :
```
LLM reads:
  "Step 1: Scroll up and find the file..."
  "Step 2: Locate the section..."
  
LLM sees file content:
  Route::get('/', function () {
      return view('welcome');
  });

LLM copies EXACTLY:
  "search": "Route::get('/', function () {\n    return view('welcome');\n});"
  
✅ Success: Text found and replaced
```

**Résultat** : Step réussit en 1 tentative

---

## 🧪 Tests de Validation

### Test 1: Projet Laravel Dashboard

**Objectif** : Vérifier que Step 4 (modification routes) réussit

**Commande** :
```bash
curl -X POST http://localhost:8001/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Créer un dashboard Laravel avec routes",
    "stack": "laravel"
  }'
```

**Logs à surveiller** :
```bash
tail -f /var/log/supervisor/backend.*.log | grep -E "search_replace|Search text not found|Step 4"
```

**Critères de succès** :
- ✅ Step 4 Attempt 1 : search_replace réussit
- ✅ Pas d'erreur "Search text not found"
- ✅ Step 4 completed successfully

---

### Test 2: Vérification Manuelle du JSON Généré

**Dans les logs**, chercher :
```
Saved developer agent output conversation
```

**Vérifier** :
- Le JSON généré contient-il du texte copié du prompt ?
- Le "search" field contient-il au moins 5-10 lignes ?
- Le "search" field correspond-il au contenu fourni ?

---

## 🔮 Si Ça Ne Marche Toujours Pas

### Étape Suivante : Validation Côté Code

Si le LLM ignore ENCORE les instructions, on peut ajouter une validation côté code :

```python
def validate_search_replace(operation, file_contents):
    """
    Force le LLM à utiliser le contenu fourni
    """
    search_text = operation.get("search", "")
    file_path = operation.get("path", "")
    
    # Si on a fourni le contenu du fichier
    if file_path in file_contents:
        file_content = file_contents[file_path]
        
        # Vérifier si le search text apparaît dans le fichier
        if search_text not in file_content:
            # Auto-correction : trouver le texte similaire
            # Ou : rejeter l'opération et demander retry
            raise ValueError(
                f"search_replace failed validation: "
                f"search text not found in {file_path}. "
                f"LLM must copy EXACT text from file contents provided."
            )
```

**Avantage** : Catch l'erreur AVANT d'essayer l'opération

---

## 📚 Documentation des Changements

### Fichiers Modifiés

1. **`/app/backend/orchestrator/agents/developer_direct.py`**
   - Lignes 345-389 : Bloc file_contents_block réécrit
   - Lignes 478-527 : Section search_replace réécrite
   - `max_chars` augmenté : 2000 → 5000

### Fichiers Créés

2. **`/app/PROMPT_REDESIGN_SEARCH_REPLACE.md`** (ce document)
   - Analyse du problème
   - Solution détaillée
   - Tests de validation

---

## 🎯 Conclusion

### Ce qui a été fait

1. ✅ **Format visuel imposant** avec séparateurs et emojis
2. ✅ **Instructions procédurales** (Step 1, 2, 3, 4, 5)
3. ✅ **Exemples concrets** (bon vs mauvais)
4. ✅ **Conséquences explicites** (Will FAIL if...)
5. ✅ **Contexte élargi** (5KB au lieu de 2KB)

### Philosophie

> **"Le LLM ne suit pas les principes abstraits,  
> mais il suit des instructions procédurales concrètes avec exemples visuels"**

### Prochaine Étape

**TEST END-TO-END** avec le même projet Laravel qui échouait avant

**Si échec persiste** : 
- Ajouter validation côté code
- Forcer le retry avec prompt encore plus explicite
- Considérer fallback vers 'update' au lieu de 'search_replace'

---

**Auteur**: AI Engineer - Prompt Engineering Phase 3  
**Inspiré par**: Principes de pédagogie appliqués aux LLM  
**Status**: ✅ Déployé (backend pid 5878)  
**Prêt pour**: Test end-to-end avec projet Laravel
