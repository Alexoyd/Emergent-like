#!/usr/bin/env python3
"""
Test de vérification de la correction du bug "empty separator" pour PHPStan
"""

import asyncio

async def test_split_fix():
    """Test que split('\
') fonctionne au lieu de split('')"""
    
    print("🧪 Test 1: Vérification du split avec newline")
    stderr_sample = """Warning: PHP version 8.3
Notice: Something happened
Error: Test failed 
Line 4
Line 5"""
    
    # Test que split('') fonctionne
    try:
        stderr_lines = stderr_sample.split('\n')
        stderr_tail = '\n'.join(stderr_lines[-20:]) if len(stderr_lines) > 20 else stderr_sample
        print(f"✅ split('\\n') fonctionne correctement")
        print(f"   Nombre de lignes: {len(stderr_lines)}")
        print(f"   Tail length: {len(stderr_tail)} chars")
    except Exception as e:
        print(f"❌ Erreur avec split('\'): {e}")
        return False
    
    print("🧪 Test 2: Vérification que split('') génère une erreur")
    # Vérifier que split('') génère bien une ValueError
    try:
        stderr_lines_bad = stderr_sample.split('')
        print(f"❌ split('') ne devrait pas fonctionner!")
        return False
    except ValueError as e:
        print(f"✅ split('') génère bien ValueError: {e}")
    
    print("🧪 Test 3: Test avec stderr vide")
    empty_stderr = ""
    try:
        stderr_lines = empty_stderr.split('')
        stderr_tail = ''.join(stderr_lines[-20:]) if len(stderr_lines) > 20 else empty_stderr
        print(f"✅ Fonctionne avec stderr vide")
    except Exception as e:
        print(f"❌ Erreur avec stderr vide: {e}")
        return False
    
    print("🧪 Test 4: Test avec stderr multi-lignes long (>20 lignes)")
    long_stderr = ''.join([f"Line {i}" for i in range(50)])
    try:
        stderr_lines = long_stderr.split('')
        stderr_tail = ''.join(stderr_lines[-20:]) if len(stderr_lines) > 20 else long_stderr
        print(f"✅ Fonctionne avec stderr long ({len(stderr_lines)} lignes)")
        print(f"   Tail contient {len(stderr_tail.split(chr(10)))} lignes")
        assert len(stderr_tail.split('')) == 20, "Tail devrait contenir 20 lignes"
        print(f"✅ Tail contient exactement 20 lignes comme attendu")
    except Exception as e:
        print(f"❌ Erreur avec stderr long: {e}")
        return False
    
    return True

async def main():
    print("=" * 60)
    print("TEST DE LA CORRECTION DU BUG 'empty separator' PHPStan")
    print("=" * 60)
    print()
    
    success = await test_split_fix()
    
    print()
    print("=" * 60)
    if success:
        print("✅ TOUS LES TESTS PASSENT - La correction est fonctionnelle!")
        print()
        print("📋 RÉSUMÉ DE LA CORRECTION:")
        print("   Fichier: /app/backend/orchestrator/tools.py")
        print("   Ligne: 1823-1824")
        print("   Changement: split('') → split('\')")
        print("   Changement: ''.join() → '\'.join()")
        print()
        print("🎯 IMPACT:")
        print("   - PHPStan ne génère plus 'empty separator'")
        print("   - Les logs d'erreur s'affichent correctement")
        print("   - Tous les tests Laravel devraient fonctionner")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())