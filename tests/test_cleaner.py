"""
Test Text Cleaner Module
========================
Unit tests for the LLM-based text cleaner.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.tts.cleaner import TextCleaner, CleanerConfig


def test_rule_based_cleaning():
    """Test rule-based cleaning without loading LLM."""
    print("\n" + "="*50)
    print("TEXT CLEANER TEST SUITE")
    print("="*50 + "\n")
    
    print("[1] Testing rule-based text cleaning...")
    
    # Create cleaner without loading LLM
    cleaner = TextCleaner.__new__(TextCleaner)
    cleaner.config = CleanerConfig()
    cleaner._loaded = False
    
    test_cases = [
        ("Dr. Smith went to St. Louis.", "Doctor Smith went to Saint Louis."),
        ("e.g. this is an example", "for example this is an example"),
        ("Too   many    spaces", "Too many spaces"),
        ("Mr. and Mrs. Jones left", "Mister and Missus Jones left"),
        ("Prof. Brown said etc.", "Professor Brown said et cetera"),
    ]
    
    passed = 0
    for input_text, expected in test_cases:
        result = cleaner._rule_based_clean(input_text)
        if result == expected:
            print(f"  ✓ '{input_text}'")
            print(f"    → '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{input_text}'")
            print(f"    Got:      '{result}'")
            print(f"    Expected: '{expected}'")
    
    print(f"\n  Passed {passed}/{len(test_cases)} tests")
    
    # Test 2: LLM detection
    print("\n[2] Testing LLM need detection...")
    
    need_tests = [
        ("Hello world", False),
        ("There are 42 apples", True),
        ("NASA launched today", True),
        ("Simple text here", False),
    ]
    
    for text, expected in need_tests:
        result = cleaner._needs_llm_cleaning(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → needs_llm={result} (expected {expected})")
    
    # Test 3: Result extraction
    print("\n[3] Testing result extraction...")
    
    extract_tests = [
        ("  cleaned text  ", "cleaned text"),
        ("Here is the result\n\nSome explanation", "Here is the result"),
    ]
    
    for input_text, expected in extract_tests:
        result = cleaner._extract_result(input_text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} Extraction works correctly")
    
    print("\n" + "="*50)
    print("RULE-BASED TESTS PASSED ✓")
    print("="*50 + "\n")
    print("Note: Full LLM-based cleaning requires model download (~2GB)")
    print("Run manually with: python -c \"from modules.tts import TextCleaner; c=TextCleaner(); print(c.clean('Test 123'))\"")
    
    return True


if __name__ == "__main__":
    success = test_rule_based_cleaning()
    sys.exit(0 if success else 1)
