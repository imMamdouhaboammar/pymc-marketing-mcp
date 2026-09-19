import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from scaffold_lesson import (
    get_next_lesson_number,
    format_lesson_number,
    update_lessons_index,
    update_state_toon_count,
    scaffold_lesson,
)


class TestScaffoldLesson(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        self.failure_lessons = self.root / "Failure-lessons"
        self.failure_lessons.mkdir()

        # Create dummy existing lessons
        (self.failure_lessons / "01-first.md").write_text("# Lesson 1")
        (self.failure_lessons / "64-last.md").write_text("# Lesson 64")

        # Create dummy lessons-index.md
        self.index_file = self.failure_lessons / "lessons-index.md"
        self.index_file.write_text(
            "| Lesson | Failure Class | Prevention Rule | Document |\n"
            "|---|---|---|---|\n"
            "| Lesson 64 | Decision Contracts / Validation | Rule 64 | [64-last.md](./64-last.md) |\n"
        )

        # Create dummy state.toon
        self.state_toon = self.root / "state.toon"
        self.state_toon.write_text("failure_lessons_count: 64\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_next_lesson_number(self):
        self.assertEqual(get_next_lesson_number(self.failure_lessons), 65)

    def test_format_lesson_number(self):
        self.assertEqual(format_lesson_number(5), "05")
        self.assertEqual(format_lesson_number(65), "65")

    def test_scaffold_lesson_execution(self):
        target_file, next_num = scaffold_lesson(
            repo_root=self.root,
            slug="mcmc-memory-leak",
            title="MCMC Memory Leak in Large Posterior Traces",
            failure_class="Memory / Trace Serialization",
            rule="Always stream NetCDF posterior traces in chunks",
            status="Resolved",
        )

        self.assertEqual(next_num, 65)
        self.assertTrue(target_file.exists())
        self.assertEqual(target_file.name, "65-mcmc-memory-leak.md")

        # Verify content of lesson
        content = target_file.read_text()
        self.assertIn("# Lesson 65: MCMC Memory Leak in Large Posterior Traces", content)
        self.assertIn("> **Always stream NetCDF posterior traces in chunks**", content)

        # Verify lessons-index updated
        index_content = self.index_file.read_text()
        self.assertIn("65-mcmc-memory-leak.md", index_content)
        self.assertIn("Lesson 65", index_content)

        # Verify state.toon updated
        toon_content = self.state_toon.read_text()
        self.assertIn("failure_lessons_count: 65", toon_content)


if __name__ == "__main__":
    unittest.main()
