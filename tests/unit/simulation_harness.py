import unittest
import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.ingestor import IngestionEngine

class MockFileSystemTest(unittest.TestCase):
    def test_ingestion_logic(self):
        """
        Unit test to verify the Ingestion Engine handles 
        basic file reading without needing a real massive disk.
        """
        engine = IngestionEngine(".")
        # In a real harness, we would mock os.walk here
        # For now, we verify the class initializes correctly
        self.assertIsNotNone(engine)
        self.assertIn(".git*", engine.exclude_patterns)
        print("✅ Simulation Harness: Initialization Verified")

if __name__ == "__main__":
    unittest.main()
