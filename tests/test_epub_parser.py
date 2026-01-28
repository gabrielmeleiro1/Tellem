"""
Test EPUB Parser Module
=======================
Unit tests for the EPUB parser using a generated sample EPUB.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.ingestion.epub_parser import EPUBParser, Document, Chapter


def create_sample_epub(output_path: Path) -> None:
    """
    Create a simple sample EPUB for testing.
    
    Uses ebooklib to generate a multi-chapter EPUB.
    """
    from ebooklib import epub
    
    book = epub.EpubBook()
    
    # Set metadata
    book.set_identifier("test-audiobook-123")
    book.set_title("Sample Audiobook EPUB")
    book.set_language("en")
    book.add_author("Test Author")
    book.add_metadata("DC", "publisher", "Test Publisher")
    
    # Create chapters
    chapters = []
    
    # Chapter 1
    ch1 = epub.EpubHtml(title="Chapter 1: The Beginning", file_name="ch1.xhtml", lang="en")
    ch1.content = """
    <html>
    <head><title>Chapter 1</title></head>
    <body>
        <h1>Chapter 1: The Beginning</h1>
        <p>This is the first chapter of our sample EPUB audiobook.
        It contains several paragraphs of text that will be parsed and 
        converted to clean text format suitable for TTS.</p>
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.
        Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
    </body>
    </html>
    """
    chapters.append(ch1)
    
    # Chapter 2
    ch2 = epub.EpubHtml(title="Chapter 2: The Middle", file_name="ch2.xhtml", lang="en")
    ch2.content = """
    <html>
    <head><title>Chapter 2</title></head>
    <body>
        <h1>Chapter 2: The Middle</h1>
        <p>This is the second chapter with more content.
        We are testing the parser's ability to extract text from 
        multiple chapters correctly.</p>
        <p>Ut enim ad minim veniam, quis nostrud exercitation
        ullamco laboris nisi ut aliquip ex ea commodo consequat.</p>
    </body>
    </html>
    """
    chapters.append(ch2)
    
    # Chapter 3
    ch3 = epub.EpubHtml(title="Chapter 3: The End", file_name="ch3.xhtml", lang="en")
    ch3.content = """
    <html>
    <head><title>Chapter 3</title></head>
    <body>
        <h1>Chapter 3: The End</h1>
        <p>This is the final chapter of our test document.
        It concludes the sample EPUB with a proper ending.</p>
        <p>Duis aute irure dolor in reprehenderit in voluptate
        velit esse cillum dolore eu fugiat nulla pariatur.</p>
    </body>
    </html>
    """
    chapters.append(ch3)
    
    # Add chapters to book
    for ch in chapters:
        book.add_item(ch)
    
    # Create table of contents
    book.toc = tuple(chapters)
    
    # Add navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Create spine
    book.spine = ["nav"] + chapters
    
    # Write EPUB
    epub.write_epub(str(output_path), book)
    print(f"✓ Created sample EPUB: {output_path}")


def test_epub_parser():
    """Run all EPUB parser tests."""
    
    # Setup - create sample EPUB
    test_dir = PROJECT_ROOT / "tests" / "samples"
    test_dir.mkdir(parents=True, exist_ok=True)
    sample_epub = test_dir / "sample.epub"
    
    print("\n" + "="*50)
    print("EPUB PARSER TEST SUITE")
    print("="*50 + "\n")
    
    # Create sample EPUB
    print("[1] Creating sample EPUB...")
    create_sample_epub(sample_epub)
    
    # Test 1: File validation
    print("\n[2] Testing file validation...")
    try:
        parser = EPUBParser(sample_epub)
        print("✓ EPUBParser initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize parser: {e}")
        return False
    
    # Test 2: Invalid file handling
    print("\n[3] Testing invalid file handling...")
    try:
        EPUBParser("/nonexistent/file.epub")
        print("✗ Should have raised FileNotFoundError")
        return False
    except FileNotFoundError:
        print("✓ FileNotFoundError raised correctly")
    
    # Test 3: Parse document
    print("\n[4] Testing document parsing...")
    try:
        doc = parser.parse()
        assert isinstance(doc, Document), "parse() should return Document"
        print(f"✓ Parsed document successfully")
        print(f"  - Title: {doc.title}")
        print(f"  - Author: {doc.author}")
        print(f"  - Language: {doc.language}")
        print(f"  - Publisher: {doc.publisher}")
        print(f"  - Chapters: {len(doc.chapters)}")
    except Exception as e:
        print(f"✗ Failed to parse document: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Metadata extraction
    print("\n[5] Testing metadata extraction...")
    try:
        metadata = parser.get_metadata()
        assert metadata.get("title") == "Sample Audiobook EPUB", f"Title mismatch: {metadata.get('title')}"
        assert metadata.get("author") == "Test Author", f"Author mismatch: {metadata.get('author')}"
        print(f"✓ Metadata extracted correctly")
        for key, value in metadata.items():
            print(f"  - {key}: {value}")
    except Exception as e:
        print(f"✗ Metadata extraction failed: {e}")
        return False
    
    # Test 5: Chapter extraction
    print("\n[6] Testing chapter extraction...")
    try:
        chapters = parser.extract_chapters()
        assert len(chapters) >= 3, f"Expected at least 3 chapters, got {len(chapters)}"
        print(f"✓ Extracted {len(chapters)} chapters")
        for ch in chapters[:5]:  # Show first 5
            content_preview = ch.content[:50].replace("\n", " ")
            print(f"  - Chapter {ch.number}: {ch.title}")
            print(f"    Content preview: {content_preview}...")
    except Exception as e:
        print(f"✗ Chapter extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 6: Content cleaning
    print("\n[7] Testing content cleaning...")
    try:
        first_chapter = chapters[0]
        assert "<html>" not in first_chapter.content, "HTML tags should be stripped"
        assert "<p>" not in first_chapter.content, "HTML tags should be stripped"
        assert len(first_chapter.content) > 50, "Content should not be empty"
        print(f"✓ Content properly cleaned (no HTML tags)")
        print(f"  - Content length: {len(first_chapter.content)} chars")
    except Exception as e:
        print(f"✗ Content cleaning failed: {e}")
        return False
    
    # Test 7: HTML content preserved
    print("\n[8] Testing HTML content preservation...")
    try:
        first_chapter = chapters[0]
        assert len(first_chapter.html_content) > 0, "HTML content should be preserved"
        assert "<html>" in first_chapter.html_content or "<h1>" in first_chapter.html_content
        print(f"✓ Original HTML content preserved")
        print(f"  - HTML length: {len(first_chapter.html_content)} chars")
    except Exception as e:
        print(f"✗ HTML preservation failed: {e}")
        return False
    
    # Cleanup
    print("\n" + "="*50)
    print("ALL TESTS PASSED ✓")
    print("="*50 + "\n")
    
    return True


if __name__ == "__main__":
    success = test_epub_parser()
    sys.exit(0 if success else 1)
