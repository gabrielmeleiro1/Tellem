"""
Text Cleaner Module
===================
LLM-based text normalization for improved TTS output.
Uses MLX-LM for efficient local inference on Apple Silicon.
"""

import gc
import re
from dataclasses import dataclass
from typing import Optional

# MLX imports - lazy loaded
try:
    import mlx.core as mx
    from mlx_lm import load, generate
    MLX_LM_AVAILABLE = True
except ImportError:
    MLX_LM_AVAILABLE = False

from .memory import VRAMManager, clear_vram


@dataclass
class CleanerConfig:
    """Configuration for text cleaner."""
    model_name: str = "mlx-community/Llama-3.2-3B-Instruct-4bit"
    max_tokens: int = 2048
    temperature: float = 0.1
    batch_size: int = 1


# Prompt template for text normalization
CLEANER_PROMPT_TEMPLATE = """You are a text preprocessing assistant for a text-to-speech system.

Your task is to normalize the following text so it sounds natural when spoken aloud.

Rules:
1. Expand abbreviations (e.g., "Dr." → "Doctor", "Mr." → "Mister", "etc." → "et cetera")
2. Convert numbers to words (e.g., "42" → "forty-two", "1984" → "nineteen eighty-four")
3. Expand acronyms if common (e.g., "NASA" → "NASA" [keep as is], "ASAP" → "as soon as possible")
4. Fix formatting issues (remove excessive whitespace, fix punctuation)
5. Keep the text meaning exactly the same
6. Do NOT add any commentary or explanations
7. Return ONLY the cleaned text, nothing else

Text to clean:
---
{text}
---

Cleaned text:"""


class TextCleaner:
    """
    LLM-based text cleaner for TTS preprocessing.
    
    Uses a small language model to normalize text before TTS:
    - Expands abbreviations
    - Converts numbers to words
    - Fixes formatting issues
    """
    
    def __init__(self, config: Optional[CleanerConfig] = None):
        """
        Initialize the text cleaner.
        
        Args:
            config: Cleaner configuration (uses defaults if None)
        """
        if not MLX_LM_AVAILABLE:
            raise ImportError(
                "mlx-lm not installed. Install with: pip install mlx-lm"
            )
        
        self.config = config or CleanerConfig()
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._manager = VRAMManager()
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._loaded
    
    def load(self) -> None:
        """Load the LLM model into memory."""
        if self._loaded:
            return
        
        # Ensure no other model is loaded
        self._manager.ensure_can_load("text-cleaner")
        
        print(f"Loading text cleaner: {self.config.model_name}")
        self._model, self._tokenizer = load(self.config.model_name)
        self._loaded = True
        
        # Register with VRAM manager
        self._manager.register_model("text-cleaner", self.unload)
        print("Text cleaner loaded")
    
    def clean(self, text: str) -> str:
        """
        Clean and normalize text for TTS.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text ready for TTS
        """
        if not text.strip():
            return ""
        
        if not self._loaded:
            self.load()
        
        # Apply rule-based cleaning first (fast, no LLM needed)
        text = self._rule_based_clean(text)
        
        # For short texts, rule-based may be sufficient
        if len(text) < 50 and not self._needs_llm_cleaning(text):
            return text
        
        # Use LLM for more complex cleaning
        prompt = CLEANER_PROMPT_TEMPLATE.format(text=text)
        
        try:
            response = generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=self.config.max_tokens,
                temp=self.config.temperature,
                verbose=False
            )
            
            # Extract just the cleaned text (remove any extra commentary)
            cleaned = self._extract_result(response)
            return cleaned if cleaned else text
            
        except Exception as e:
            print(f"LLM cleaning failed: {e}, using rule-based fallback")
            return text
    
    def _rule_based_clean(self, text: str) -> str:
        """Apply rule-based text cleaning (fast, always runs)."""
        # 1. Remove Markdown Headers (at start of line)
        # Matches #, ##, ### etc followed by space
        text = re.sub(r'(?m)^#{1,6}\s+', '', text)
        
        # 2. Remove Bold/Italic markers (*, **, _, __)
        # We want to keep the text inside, just remove markers
        # Removing all instances of * and _ might be too aggressive if used for other things,
        # but in normal prose they are usually formatting.
        text = re.sub(r'[\*_]{1,3}([^\*_]+)[\*_]{1,3}', r'\1', text)
        
        # 3. Handle Links: [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # 4. Handle Images: ![alt](url) -> remove entirely or keep alt text?
        # Usually alt text is descriptive. Let's keep alt text: ![alt] -> alt
        text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
        
        # 5. Remove Code formatting backticks
        text = re.sub(r'`', '', text)
        
        # Common abbreviations
        abbreviations = {
            r'\bDr\.\s': 'Doctor ',
            r'\bMr\.\s': 'Mister ',
            r'\bMrs\.\s': 'Missus ',
            r'\bMs\.\s': 'Miss ',
            r'\bProf\.\s': 'Professor ',
            r'\bSt\.\s': 'Saint ',
            r'\betc\.': 'et cetera',
            r'\be\.g\.': 'for example',
            r'\bi\.e\.': 'that is',
            r'\bvs\.': 'versus',
            r'\bJr\.': 'Junior',
            r'\bSr\.': 'Senior',
        }
        
        for pattern, replacement in abbreviations.items():
            text = re.sub(pattern, replacement, text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Fix common punctuation issues
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        text = re.sub(r'([,.!?;:])([A-Za-z])', r'\1 \2', text)
        
        return text.strip()
    
    def _needs_llm_cleaning(self, text: str) -> bool:
        """Check if text needs LLM-based cleaning."""
        # Check for numbers that should be spoken
        if re.search(r'\b\d+\b', text):
            return True
        # Check for remaining abbreviations
        if re.search(r'\b[A-Z]{2,}\b', text):  # Acronyms
            return True
        return False
    
    def _extract_result(self, response: str) -> str:
        """Extract cleaned text from LLM response."""
        # Remove any leading/trailing whitespace
        result = response.strip()
        
        # If response contains explanation markers, try to extract just the text
        if '\n\n' in result:
            # Take the first substantial paragraph
            parts = result.split('\n\n')
            for part in parts:
                if len(part.strip()) > 20:
                    result = part.strip()
                    break
        
        return result
    
    def unload(self) -> None:
        """Unload the model and free memory."""
        if not self._loaded:
            return
        
        self._model = None
        self._tokenizer = None
        self._loaded = False
        
        # Clear memory
        clear_vram()
        print("Text cleaner unloaded, memory freed")
    
    def __enter__(self):
        """Context manager entry."""
        self.load()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.unload()
        return False


def test_rule_based_cleaning() -> bool:
    """Test rule-based cleaning without loading LLM."""
    print("\nTesting rule-based text cleaning...")
    
    cleaner = TextCleaner.__new__(TextCleaner)
    cleaner.config = CleanerConfig()
    cleaner._loaded = False
    
    test_cases = [
        ("Dr. Smith went to St. Louis.", "Doctor Smith went to Saint Louis."),
        ("e.g. this is an example", "for example this is an example"),
        ("Too   many    spaces", "Too many spaces"),
        ("Hello,world", "Hello, world"),
    ]
    
    passed = 0
    for input_text, expected in test_cases:
        result = cleaner._rule_based_clean(input_text)
        if result == expected:
            print(f"✓ '{input_text}' → '{result}'")
            passed += 1
        else:
            print(f"✗ '{input_text}' → '{result}' (expected: '{expected}')")
    
    print(f"\nPassed {passed}/{len(test_cases)} tests")
    return passed == len(test_cases)


def test_full_cleaning() -> bool:
    """Test full LLM-based cleaning (requires model download)."""
    print("\nTesting full text cleaning with LLM...")
    
    try:
        with TextCleaner() as cleaner:
            test_text = "Dr. Smith bought 42 apples on Jan. 1st, 2024."
            result = cleaner.clean(test_text)
            print(f"Input:  {test_text}")
            print(f"Output: {result}")
            return True
    except Exception as e:
        print(f"Full cleaning test failed: {e}")
        return False


if __name__ == "__main__":
    test_rule_based_cleaning()
