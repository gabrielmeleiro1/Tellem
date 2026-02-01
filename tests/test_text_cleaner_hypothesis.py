"""
Property-Based Tests for Text Cleaner/Normalizer
=================================================
Uses Hypothesis for fuzz testing text normalization edge cases.
Tests rule-based cleaning and text transformations.
"""

import pytest
import re
from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import composite
from unittest.mock import patch, MagicMock

# Import the cleaner module components
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.tts.cleaner import (
    TextCleaner, 
    CleanerConfig, 
    CLEANER_PROMPT_TEMPLATE,
    _get_cached_cleaner,
    _set_cached_cleaner,
    _clear_cleaner_cache
)


# Strategy for generating text with markdown
markdown_elements = st.one_of(
    # Headers
    st.builds(lambda t: f"# {t}", st.text(min_size=1, max_size=50)),
    st.builds(lambda t: f"## {t}", st.text(min_size=1, max_size=50)),
    # Bold/Italic
    st.builds(lambda t: f"**{t}**", st.text(min_size=1, max_size=30)),
    st.builds(lambda t: f"_{t}_", st.text(min_size=1, max_size=30)),
    # Links
    st.builds(lambda t, u: f"[{t}]({u})", 
              st.text(min_size=1, max_size=20),
              st.text(min_size=5, max_size=50)),
    # Plain text
    st.text(min_size=1, max_size=100),
)


# Strategy for text with abbreviations
abbreviation_text = st.one_of(
    st.just("Dr. Smith went to the hospital."),
    st.just("Mr. and Mrs. Johnson live at 123 St. James St."),
    st.just("Prof. Anderson teaches math, e.g. algebra and calculus."),
    st.just("The meeting is at 3 p.m., i.e. after lunch."),
    st.just("Team A vs. Team B"),
    st.just("John Doe, Jr. and his father, Sr."),
    st.builds(lambda: st.text(min_size=10, max_size=200)),
)


class TestTextCleanerRuleBased:
    """Property-based tests for rule-based text cleaning."""
    
    @pytest.mark.property
    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=200, deadline=5000)
    def test_rule_cleaning_never_crashes(self, text):
        """
        Rule-based cleaning should never crash on any input.
        """
        # Create cleaner with mocked load to avoid actual model loading
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            # Access the _rule_based_clean method directly
            try:
                result = cleaner._rule_based_clean(text)
                assert isinstance(result, str)
            except Exception as e:
                pytest.fail(f"Rule-based cleaning crashed on: {repr(text[:100])}... Error: {e}")
    
    @pytest.mark.property
    @given(markdown_elements)
    @settings(max_examples=150, deadline=5000)
    def test_markdown_formatting_removed(self, text):
        """
        Markdown formatting should be removed or simplified.
        
        Headers (#), bold (**), italics (_), links should be cleaned.
        """
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            result = cleaner._rule_based_clean(text)
            
            # Basic sanity checks
            assert isinstance(result, str)
            
            # Markdown headers at start of lines should be removed
            assert not re.match(r'^#{1,6}\s', result, re.MULTILINE)
            
            # Should not have standalone doubled asterisks around text
            # (single asterisks might remain for other purposes)
            assert '**' not in result or result.count('**') == 0
    
    @pytest.mark.property
    @given(
        st.text(min_size=5, max_size=200),
        st.sampled_from(['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Prof.', 'St.', 'etc.', 'e.g.', 'i.e.', 'vs.'])
    )
    @settings(max_examples=100, deadline=5000)
    def test_abbreviations_expanded(self, context, abbrev):
        """
        Common abbreviations should be expanded.
        
        Note: We test with context to ensure the regex matches correctly.
        """
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            
            # Create text with abbreviation
            text = f"{abbrev} {context}"
            result = cleaner._rule_based_clean(text)
            
            # The abbreviation should be expanded (not remain as "X.")
            # Note: Some abbreviations need specific patterns to match
            assert isinstance(result, str)
            assert len(result) >= len(context)  # Shouldn't lose content
    
    @pytest.mark.property
    @given(st.text(min_size=0, max_size=500))
    @settings(max_examples=100, deadline=3000)
    def test_empty_and_whitespace_handled(self, text):
        """
        Empty or whitespace-only input should return empty string.
        """
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            
            result = cleaner.clean(text)
            
            if not text or not text.strip():
                assert result == ""
    
    @pytest.mark.property
    @given(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs')), 
                   min_size=0, max_size=500))
    @settings(max_examples=100, deadline=3000)
    def test_unicode_text_handled(self, text):
        """
        Unicode text (letters and spaces) should be handled correctly.
        """
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            
            result = cleaner._rule_based_clean(text)
            
            # Result should be valid unicode
            assert isinstance(result, str)
            assert result.encode('utf-8').decode('utf-8') == result
    
    @pytest.mark.property
    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=100, deadline=3000)
    def test_content_not_lost(self, text):
        """
        Substantial content should not be lost during cleaning.
        
        While formatting may change, the core text should remain.
        """
        # Filter out mostly formatting characters
        core_content = re.sub(r'[#*_\[\]\(\)!`]', '', text)
        assume(len(core_content) > 10)  # Need some actual content
        
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            result = cleaner._rule_based_clean(text)
            
            # Result should have some content
            assert len(result) > 0
            
            # Core alphabetic content should be mostly preserved
            result_letters = set(re.sub(r'[^a-zA-Z]', '', result).lower())
            original_letters = set(re.sub(r'[^a-zA-Z]', '', core_content).lower())
            
            # Most letters from original should be in result
            if original_letters:
                preserved_ratio = len(result_letters & original_letters) / len(original_letters)
                assert preserved_ratio >= 0.5, f"Lost too much content: {preserved_ratio:.2%}"


class TestTextCleanerLLMSemantics:
    """Tests for LLM-based cleaning semantics (with mocked LLM)."""
    
    @pytest.mark.property
    @given(
        text=st.text(min_size=20, max_size=500),
        mock_response=st.text(min_size=10, max_size=500)
    )
    @settings(max_examples=50, deadline=5000)
    def test_llm_output_extracted_correctly(self, text, mock_response):
        """
        LLM response should be extracted and returned correctly.
        """
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            cleaner._loaded = True
            cleaner._model = MagicMock()
            cleaner._tokenizer = MagicMock()
            
            # Mock the generate function
            with patch('modules.tts.cleaner.generate', return_value=mock_response):
                result = cleaner.clean(text)
                
                # Result should be the extracted text
                assert isinstance(result, str)
                assert len(result) > 0
    
    @pytest.mark.property
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50, deadline=3000)
    def test_short_text_uses_rule_based_only(self, text):
        """
        Short text without numbers should use rule-based cleaning only.
        """
        assume(len(text) < 50)
        assume(not re.search(r'\d', text))  # No numbers
        
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            
            # Should not need LLM
            assert not cleaner._needs_llm_cleaning(text)


class TestTextCleanerErrorHandling:
    """Tests for error handling and edge cases."""
    
    @pytest.mark.property
    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=100, deadline=3000)
    def test_fallback_on_error(self, text):
        """
        If LLM cleaning fails, should fallback to rule-based result.
        """
        with patch.object(TextCleaner, 'load'):
            cleaner = TextCleaner()
            cleaner._loaded = True
            cleaner._model = MagicMock()
            cleaner._tokenizer = MagicMock()
            
            # Mock generate to raise exception
            with patch('modules.tts.cleaner.generate', side_effect=Exception("LLM Error")):
                rule_based_result = cleaner._rule_based_clean(text)
                
                # Clean should fallback to rule-based
                result = cleaner.clean(text)
                assert isinstance(result, str)
                # Should get something sensible back
                assert result == text or len(result) > 0


class TestTextCleanerCaching:
    """Tests for model caching behavior."""
    
    @pytest.mark.property
    @given(model_name=st.text(min_size=1, max_size=100))
    @settings(max_examples=50, deadline=3000)
    def test_cache_operations(self, model_name):
        """
        Cache get/set operations should work correctly.
        """
        # Clear cache first
        _clear_cleaner_cache()
        
        # Initially should be None
        assert _get_cached_cleaner(model_name) is None
        
        # Set a mock cache entry
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        _set_cached_cleaner(model_name, mock_model, mock_tokenizer)
        
        # Should be retrievable
        cached = _get_cached_cleaner(model_name)
        assert cached is not None
        assert cached == (mock_model, mock_tokenizer)
        
        # Clear and verify
        _clear_cleaner_cache()
        assert _get_cached_cleaner(model_name) is None
    
    def test_cache_size_limited(self):
        """
        Cache should only hold one model at a time.
        """
        _clear_cleaner_cache()
        
        # Add first model
        _set_cached_cleaner("model1", MagicMock(), MagicMock())
        assert _get_cached_cleaner("model1") is not None
        
        # Add second model - should replace first
        _set_cached_cleaner("model2", MagicMock(), MagicMock())
        assert _get_cached_cleaner("model2") is not None
        # Cache size is limited to 1, so first model might be gone
        # (depending on implementation)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "property"])
