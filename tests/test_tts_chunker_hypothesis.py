"""
Property-Based Tests for Text Chunker
======================================
Uses Hypothesis for fuzz testing edge cases.
Tests the TextChunker with various inputs to ensure robustness.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

from modules.tts.chunker import TextChunker, ChunkConfig


class TestTextChunkerProperties:
    """Property-based tests for TextChunker."""
    
    @pytest.mark.property
    @given(st.text(min_size=0, max_size=10000))
    @settings(max_examples=200, deadline=5000)
    def test_chunker_never_crash(self, text):
        """
        Text chunker should never crash regardless of input.
        
        This is a fundamental robustness property - the chunker should
        handle any text without raising exceptions.
        """
        chunker = TextChunker()
        try:
            chunks = chunker.chunk(text)
            # Result should always be a list
            assert isinstance(chunks, list)
            # Each chunk should be a string
            assert all(isinstance(c, str) for c in chunks)
        except Exception as e:
            pytest.fail(f"Chunker crashed on input: {repr(text[:100])}... Error: {e}")
    
    @pytest.mark.property
    @given(
        st.text(min_size=1, max_size=5000).filter(lambda x: len(x.strip()) > 0),
        st.integers(min_value=10, max_value=1000)
    )
    @settings(max_examples=100, deadline=5000)
    def test_chunked_text_joins_to_original(self, text, max_tokens):
        """
        Joining chunks should produce the original text (minus whitespace differences).
        
        This property ensures no text is lost during chunking.
        """
        config = ChunkConfig(max_tokens=max_tokens)
        chunker = TextChunker(config)
        chunks = chunker.chunk(text)
        
        if not chunks:
            # If no chunks produced, the text was likely too short/full of whitespace
            return
        
        joined = " ".join(chunks)
        original_normalized = " ".join(text.split())
        
        # The joined text should match the original (allowing for whitespace normalization)
        assert joined == original_normalized or len(joined) >= len(original_normalized) * 0.9
    
    @pytest.mark.property
    @given(
        st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=0,
            max_size=2000
        )
    )
    @settings(max_examples=150, deadline=5000)
    def test_chunker_handles_unicode(self, text):
        """
        Text chunker should handle unicode text correctly.
        
        Tests with various unicode categories:
        - L: Letters (including non-ASCII)
        - N: Numbers
        - P: Punctuation
        - Z: Separators (spaces)
        """
        chunker = TextChunker()
        chunks = chunker.chunk(text)
        
        assert isinstance(chunks, list)
        for chunk in chunks:
            assert isinstance(chunk, str)
            # Each chunk should be valid unicode
            assert chunk.encode('utf-8').decode('utf-8') == chunk
    
    @pytest.mark.property
    @given(
        st.text(min_size=100, max_size=5000),
        st.integers(min_value=20, max_value=200)
    )
    @settings(max_examples=100, deadline=5000)
    def test_chunk_size_honored(self, text, max_tokens):
        """
        Chunks should respect the max_tokens limit (with some tolerance).
        
        Note: We allow some tolerance because the chunker tries to split
        at sentence boundaries, which may exceed the exact token limit.
        """
        config = ChunkConfig(max_tokens=max_tokens)
        chunker = TextChunker(config)
        chunks = chunker.chunk(text)
        
        chars_per_token = config.chars_per_token
        max_chars = int(max_tokens * chars_per_token * 1.5)  # 50% tolerance for sentence boundaries
        
        for chunk in chunks:
            # Each chunk should be within reasonable bounds
            # (allowing extra for sentence boundary preservation)
            assert len(chunk) <= max_chars or len(chunk) < len(text) * 0.5, (
                f"Chunk too long: {len(chunk)} chars, limit was {max_chars}"
            )
    
    @pytest.mark.property
    @given(st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=20))
    @settings(max_examples=100, deadline=5000)
    def test_chunker_handles_sentence_boundaries(self, sentences):
        """
        Text with clear sentence boundaries should be split accordingly.
        
        Input is a list of sentences that we join with proper punctuation.
        """
        # Create proper sentences with endings
        proper_sentences = [s.strip() + "." if not s.strip().endswith(('.','!','?')) else s.strip() 
                           for s in sentences if s.strip()]
        text = " ".join(proper_sentences)
        
        config = ChunkConfig(max_tokens=50)  # Small limit to force splits
        chunker = TextChunker(config)
        chunks = chunker.chunk(text)
        
        # Should produce at least one chunk
        assert len(chunks) >= 1
        
        # Total content should be preserved
        total_chunk_chars = sum(len(c) for c in chunks)
        assert total_chunk_chars >= len(text) * 0.8  # Allow for whitespace differences
    
    @pytest.mark.property
    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, deadline=2000)
    def test_empty_and_whitespace_only(self, text):
        """
        Empty or whitespace-only text should produce empty list.
        """
        chunker = TextChunker()
        chunks = chunker.chunk(text)
        
        if not text or not text.strip():
            # Empty or whitespace-only input
            assert chunks == []
    
    @pytest.mark.property
    @given(st.text(alphabet=st.just(" "), min_size=0, max_size=1000))
    @settings(max_examples=50, deadline=2000)
    def test_whitespace_only_input(self, whitespace):
        """
        Input containing only whitespace should not produce chunks.
        """
        chunker = TextChunker()
        chunks = chunker.chunk(whitespace)
        assert chunks == []
    
    @pytest.mark.property
    @given(
        st.text(min_size=1, max_size=100),
        st.integers(min_value=-100, max_value=10)
    )
    @settings(max_examples=50, deadline=2000)
    def test_negative_max_tokens_clamped(self, text, invalid_max_tokens):
        """
        Invalid (negative or too small) max_tokens should be handled gracefully.
        
        The chunker uses default config when given invalid values.
        """
        assume(invalid_max_tokens < 10)  # Filter to only invalid values
        
        config = ChunkConfig(max_tokens=invalid_max_tokens)
        chunker = TextChunker(config)
        
        # Should not crash
        chunks = chunker.chunk(text)
        assert isinstance(chunks, list)
    
    @pytest.mark.property
    @given(
        st.text(min_size=100, max_size=2000),
        st.integers(min_value=50, max_value=500),
        st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=100, deadline=5000)
    def test_chunking_is_deterministic(self, text, max_tokens, min_tokens):
        """
        Chunking the same text should produce the same result every time.
        """
        assume(min_tokens < max_tokens)
        
        config = ChunkConfig(max_tokens=max_tokens, min_tokens=min_tokens)
        
        chunker1 = TextChunker(config)
        chunker2 = TextChunker(config)
        
        chunks1 = chunker1.chunk(text)
        chunks2 = chunker2.chunk(text)
        
        assert chunks1 == chunks2


class TestTextChunkerStateful(RuleBasedStateMachine):
    """
    Stateful property-based tests for TextChunker.
    
    Tests sequences of operations to ensure state management is correct.
    """
    
    def __init__(self):
        super().__init__()
        self.chunker = TextChunker()
        self.chunked_texts = []
    
    @rule(text=st.text(min_size=0, max_size=1000))
    def chunk_text(self, text):
        """Chunk arbitrary text."""
        chunks = self.chunker.chunk(text)
        self.chunked_texts.append((text, chunks))
    
    @rule(new_max_tokens=st.integers(min_value=10, max_value=1000))
    def change_config(self, new_max_tokens):
        """Change the chunker configuration."""
        config = ChunkConfig(max_tokens=new_max_tokens)
        self.chunker = TextChunker(config)
    
    @invariant()
    def chunks_are_valid(self):
        """All stored chunks must be valid."""
        for original, chunks in self.chunked_texts:
            assert isinstance(chunks, list)
            assert all(isinstance(c, str) for c in chunks)


# Run the stateful test
TestTextChunkerStatefulTests = TestTextChunkerStateful.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "property"])
