"""
Test PDF Parser Module
======================
Unit tests for the PDF parser using a generated sample PDF.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.ingestion.pdf_parser import PDFParser, Document, Chapter


def create_sample_pdf(output_path: Path) -> None:
    """
    Create a simple sample PDF for testing.
    
    Uses PyMuPDF (fitz) to generate a multi-page PDF with chapters.
    """
    import fitz  # PyMuPDF
    
    doc = fitz.open()
    
    # Set metadata
    doc.set_metadata({
        "title": "Sample Audiobook Test",
        "author": "Test Author",
        "subject": "PDF Parser Test"
    })
    
    # Chapter 1
    page1 = doc.new_page()
    text1 = """Chapter 1: The Beginning

This is the first chapter of our sample audiobook.
It contains several paragraphs of text that will be
parsed and converted to markdown format.

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."""
    page1.insert_text((72, 72), text1, fontsize=12)
    
    # Chapter 2  
    page2 = doc.new_page()
    text2 = """Chapter 2: The Middle

This is the second chapter with more content.
We are testing the parser's ability to extract text
from multiple pages correctly.

Ut enim ad minim veniam, quis nostrud exercitation
ullamco laboris nisi ut aliquip ex ea commodo consequat."""
    page2.insert_text((72, 72), text2, fontsize=12)
    
    # Chapter 3
    page3 = doc.new_page()
    text3 = """Chapter 3: The End

This is the final chapter of our test document.
It concludes the sample PDF with a proper ending.

Duis aute irure dolor in reprehenderit in voluptate
velit esse cillum dolore eu fugiat nulla pariatur."""
    page3.insert_text((72, 72), text3, fontsize=12)
    
    # Add a table of contents
    toc = [
        [1, "Chapter 1: The Beginning", 1],
        [1, "Chapter 2: The Middle", 2],
        [1, "Chapter 3: The End", 3]
    ]
    doc.set_toc(toc)
    
    doc.save(output_path)
    doc.close()
    print(f"✓ Created sample PDF: {output_path}")


def test_pdf_parser():
    """Run all PDF parser tests."""
    
    # Setup - create sample PDF
    test_dir = PROJECT_ROOT / "tests" / "samples"
    test_dir.mkdir(parents=True, exist_ok=True)
    sample_pdf = test_dir / "sample.pdf"
    
    print("\n" + "="*50)
    print("PDF PARSER TEST SUITE")
    print("="*50 + "\n")
    
    # Create sample PDF
    print("[1] Creating sample PDF...")
    create_sample_pdf(sample_pdf)
    
    # Test 1: File validation
    print("\n[2] Testing file validation...")
    try:
        parser = PDFParser(sample_pdf)
        print("✓ PDFParser initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize parser: {e}")
        return False
    
    # Test 2: Invalid file handling
    print("\n[3] Testing invalid file handling...")
    try:
        PDFParser("/nonexistent/file.pdf")
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
        print(f"  - Pages: {doc.total_pages}")
        print(f"  - Chapters: {len(doc.chapters)}")
        print(f"  - Markdown length: {len(doc.raw_markdown)} chars")
    except Exception as e:
        print(f"✗ Failed to parse document: {e}")
        return False
    
    # Test 4: TOC extraction
    print("\n[5] Testing TOC extraction...")
    try:
        toc = parser.extract_toc()
        assert len(toc) == 3, f"Expected 3 TOC entries, got {len(toc)}"
        print(f"✓ Extracted {len(toc)} TOC entries")
        for level, title, page in toc:
            print(f"  - [{level}] {title} (p.{page})")
    except Exception as e:
        print(f"✗ Failed to extract TOC: {e}")
        return False
    
    # Test 5: Chapter extraction
    print("\n[6] Testing chapter extraction...")
    try:
        assert len(doc.chapters) == 3, f"Expected 3 chapters, got {len(doc.chapters)}"
        print(f"✓ Extracted {len(doc.chapters)} chapters")
        for ch in doc.chapters:
            print(f"  - Chapter {ch.number}: {ch.title} (p.{ch.start_page}-{ch.end_page})")
    except Exception as e:
        print(f"✗ Chapter extraction failed: {e}")
        return False
    
    # Test 6: Page count
    print("\n[7] Testing page count...")
    try:
        page_count = parser.get_page_count()
        assert page_count == 3, f"Expected 3 pages, got {page_count}"
        print(f"✓ Page count: {page_count}")
    except Exception as e:
        print(f"✗ Page count failed: {e}")
        return False
    
    # Test 7: Markdown content
    print("\n[8] Testing markdown content...")
    try:
        markdown = parser.get_markdown()
        assert len(markdown) > 0, "Markdown should not be empty"
        assert "Chapter" in markdown, "Markdown should contain 'Chapter'"
        print(f"✓ Markdown content looks good ({len(markdown)} chars)")
        print("  Preview (first 200 chars):")
        print(f"  {markdown[:200]}...")
    except Exception as e:
        print(f"✗ Markdown test failed: {e}")
        return False
    
    # Cleanup
    print("\n" + "="*50)
    print("ALL TESTS PASSED ✓")
    print("="*50 + "\n")
    
    return True


if __name__ == "__main__":
    success = test_pdf_parser()
    sys.exit(0 if success else 1)
