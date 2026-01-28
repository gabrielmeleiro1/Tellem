"""
Test Database Module
====================
Unit tests for SQLite database operations.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.storage.database import Database, Book, Chapter, ProcessingJob


def test_database():
    """Run all database tests."""
    
    # Create a temporary database for testing
    test_dir = PROJECT_ROOT / "tests" / "data"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_db = test_dir / "test_audiobooks.db"
    
    # Clean up any previous test database
    if test_db.exists():
        os.remove(test_db)
    
    print("\n" + "="*50)
    print("DATABASE TEST SUITE")
    print("="*50 + "\n")
    
    # Test 1: Database initialization
    print("[1] Testing database initialization...")
    try:
        db = Database(test_db)
        assert test_db.exists(), "Database file should be created"
        print(f"✓ Database initialized: {test_db}")
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return False
    
    # Test 2: Create book
    print("\n[2] Testing create_book()...")
    try:
        book_id = db.create_book(
            title="Test Audiobook",
            source_path="/path/to/test.pdf",
            source_type="pdf",
            author="Test Author",
            total_chapters=5
        )
        assert book_id is not None, "Book ID should not be None"
        assert book_id > 0, "Book ID should be positive"
        print(f"✓ Created book with ID: {book_id}")
    except Exception as e:
        print(f"✗ Failed to create book: {e}")
        return False
    
    # Test 3: Get book
    print("\n[3] Testing get_book()...")
    try:
        book = db.get_book(book_id)
        assert book is not None, "Book should be found"
        assert isinstance(book, Book), "Should return Book instance"
        assert book.title == "Test Audiobook", "Title should match"
        assert book.author == "Test Author", "Author should match"
        assert book.source_type == "pdf", "Source type should match"
        assert book.total_chapters == 5, "Total chapters should match"
        print(f"✓ Retrieved book: {book.title} by {book.author}")
    except Exception as e:
        print(f"✗ Failed to get book: {e}")
        return False
    
    # Test 4: Get non-existent book
    print("\n[4] Testing get_book() with invalid ID...")
    try:
        missing_book = db.get_book(9999)
        assert missing_book is None, "Should return None for missing book"
        print(f"✓ Correctly returned None for non-existent book")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False
    
    # Test 5: Create chapters
    print("\n[5] Testing create_chapter()...")
    try:
        chapter_ids = []
        for i in range(1, 4):
            ch_id = db.create_chapter(
                book_id=book_id,
                chapter_number=i,
                title=f"Chapter {i}",
                start_time_ms=i * 60000,
                duration_ms=300000,
                mp3_path=f"/audio/chapter_{i}.mp3"
            )
            chapter_ids.append(ch_id)
        print(f"✓ Created {len(chapter_ids)} chapters")
    except Exception as e:
        print(f"✗ Failed to create chapters: {e}")
        return False
    
    # Test 6: Get chapters
    print("\n[6] Testing get_chapters()...")
    try:
        chapters = db.get_chapters(book_id)
        assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"
        for ch in chapters:
            assert isinstance(ch, Chapter), "Should return Chapter instance"
            print(f"  - {ch.title}: {ch.duration_ms}ms")
        print(f"✓ Retrieved {len(chapters)} chapters")
    except Exception as e:
        print(f"✗ Failed to get chapters: {e}")
        return False
    
    # Test 7: Create processing job
    print("\n[7] Testing create_job()...")
    try:
        job_id = db.create_job(book_id)
        assert job_id is not None, "Job ID should not be None"
        assert job_id > 0, "Job ID should be positive"
        print(f"✓ Created job with ID: {job_id}")
    except Exception as e:
        print(f"✗ Failed to create job: {e}")
        return False
    
    # Test 8: Update progress
    print("\n[8] Testing update_progress()...")
    try:
        db.update_progress(job_id, 0.25, "Parsing PDF")
        db.update_progress(job_id, 0.50, "Text-to-Speech")
        db.update_progress(job_id, 0.75, "Generating Audio")
        print(f"✓ Updated progress multiple times")
    except Exception as e:
        print(f"✗ Failed to update progress: {e}")
        return False
    
    # Test 9: Complete job
    print("\n[9] Testing complete_job()...")
    try:
        db.complete_job(job_id)
        history = db.get_processing_history(1)
        assert len(history) > 0, "History should not be empty"
        assert history[0]["status"] == "completed", "Status should be completed"
        assert history[0]["progress"] == 1.0, "Progress should be 1.0"
        print(f"✓ Job marked as completed")
    except Exception as e:
        print(f"✗ Failed to complete job: {e}")
        return False
    
    # Test 10: Create and fail a job
    print("\n[10] Testing fail_job()...")
    try:
        book_id_2 = db.create_book(
            title="Failing Book",
            source_path="/path/to/fail.epub",
            source_type="epub"
        )
        job_id_2 = db.create_job(book_id_2)
        db.update_progress(job_id_2, 0.3, "Processing")
        db.fail_job(job_id_2, "Test error message")
        
        history = db.get_processing_history(10)
        failed = [h for h in history if h["status"] == "failed"]
        assert len(failed) > 0, "Should have failed job"
        assert failed[0]["error_message"] == "Test error message"
        print(f"✓ Job marked as failed with error message")
    except Exception as e:
        print(f"✗ Failed to fail job: {e}")
        return False
    
    # Test 11: Processing history
    print("\n[11] Testing get_processing_history()...")
    try:
        history = db.get_processing_history(50)
        assert len(history) >= 2, "Should have at least 2 jobs"
        print(f"✓ Retrieved {len(history)} jobs from history")
        for job in history:
            print(f"  - {job['title']}: {job['status']} ({job['progress']*100:.0f}%)")
    except Exception as e:
        print(f"✗ Failed to get history: {e}")
        return False
    
    # Cleanup
    print("\n" + "="*50)
    print("ALL TESTS PASSED ✓")
    print("="*50 + "\n")
    
    return True


if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
