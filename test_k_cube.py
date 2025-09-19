# test_k_cube.py

import unittest
import shutil
import subprocess
from pathlib import Path

# --- 测试配置 ---
TEST_DIR = Path("./temp_test_vault").resolve()
KV_COMMAND = "kv"  # 确保 kv 命令在系统 PATH 中


class KCubeIntegrationTest(unittest.TestCase):

    def setUp(self):
        """在每个测试用例开始前运行：创建一个干净的测试环境。"""
        self.clean_up()
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        # 在测试目录中运行 kv init
        result = self._run_kv_command("init")
        self.assertEqual(result.returncode, 0, "初始化失败")

    def tearDown(self):
        """在每个测试用例结束后运行：清理测试环境。"""
        self.clean_up()

    def clean_up(self):
        """辅助函数：删除测试目录。"""
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)

    def _run_kv_command(self, *args):
        """辅助函数：在测试目录中执行 kv 命令。"""
        return subprocess.run(
            [KV_COMMAND, *args],
            cwd=TEST_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

    def _create_file(self, path, content=""):
        """辅助函数：在测试目录中创建文件。"""
        full_path = TEST_DIR / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')

    def _delete_file(self, path):
        """辅助函数：在测试目录中删除文件。"""
        (TEST_DIR / path).unlink()

    def test_01_init_and_initial_status(self):
        """测试1：初始化和初始状态。"""
        # Act
        result = self._run_kv_command("status")
        # Assert
        self.assertEqual(result.returncode, 0)
        self.assertIn("工作区很干净", result.stdout)

    def test_02_add_and_commit_single_file(self):
        """测试2：添加并提交单个新文件。"""
        # Arrange
        self._create_file("note1.md", "This is note 1.")

        # Act (add)
        result_add = self._run_kv_command("add", "note1.md")
        result_status_staged = self._run_kv_command("status")

        # Assert (add)
        self.assertEqual(result_add.returncode, 0)
        self.assertIn("new file:   note1.md", result_status_staged.stdout)

        # Act (commit)
        result_commit = self._run_kv_command("commit", "-m", "Add note 1")
        result_status_clean = self._run_kv_command("status")
        result_log = self._run_kv_command("log")

        # Assert (commit)
        self.assertEqual(result_commit.returncode, 0)
        self.assertIn("工作区很干净", result_status_clean.stdout)
        self.assertIn("Add note 1", result_log.stdout)

    def test_03_modify_and_delete_flow(self):
        """测试3：修改和删除文件的完整流程。"""
        # Arrange
        self._create_file("file_to_modify.md", "Version 1")
        self._create_file("file_to_delete.md", "This will be deleted")
        self._run_kv_command("add", ".")
        self._run_kv_command("commit", "-m", "Initial commit for test 3")

        # Act (modify and delete)
        self._create_file("file_to_modify.md", "Version 2")
        self._delete_file("file_to_delete.md")
        result_status_unstaged = self._run_kv_command("status")

        # Assert (unstaged changes)
        self.assertIn("modified:   file_to_modify.md",
                      result_status_unstaged.stdout)
        self.assertIn("deleted:    file_to_delete.md",
                      result_status_unstaged.stdout)

        # Act (add changes)
        self._run_kv_command("add", "file_to_modify.md", "file_to_delete.md")
        result_status_staged = self._run_kv_command("status")

        # Assert (staged changes)
        self.assertIn("modified:   file_to_modify.md",
                      result_status_staged.stdout)
        self.assertIn("deleted:    file_to_delete.md",
                      result_status_staged.stdout)

        # Act (commit changes)
        self._run_kv_command("commit", "-m", "Update and delete files")
        result_status_final = self._run_kv_command("status")

        # Assert (final state)
        self.assertIn("工作区很干净", result_status_final.stdout)
        self.assertFalse((TEST_DIR / "file_to_delete.md").exists())

    def test_04_reset_and_restore(self):
        """测试4：测试 reset 和 restore 功能。"""
        # Arrange
        self._create_file("a.md", "content a")
        self._run_kv_command("add", "a.md")
        self._run_kv_command("commit", "-m", "Commit A")
        commit_a_hash = self._run_kv_command(
            "log").stdout.splitlines()[2].split()[-1]

        self._create_file("a.md", "content a modified")
        self._create_file("b.md", "content b")
        self._run_kv_command("add", "a.md", "b.md")
        result_status_staged = self._run_kv_command("status")

        # Assert (staged correctly)
        self.assertIn("modified:   a.md", result_status_staged.stdout)
        self.assertIn("new file:   b.md", result_status_staged.stdout)

        # Act (reset single file)
        self._run_kv_command("reset", "a.md")
        result_status_reset_a = self._run_kv_command("status")

        # Assert (reset single file)
        self.assertNotIn("modified:   a.md", result_status_reset_a.stdout)
        self.assertIn("modified:   a.md",
                      result_status_reset_a.stdout.split("未暂存的变更")[1])
        # b.md should still be staged
        self.assertIn("new file:   b.md", result_status_reset_a.stdout)

        # Act (reset all)
        self._run_kv_command("reset")
        result_status_reset_all = self._run_kv_command("status")

        # Assert (reset all)
        self.assertNotIn("待提交的变更", result_status_reset_all.stdout)

        # Act (restore file)
        self._run_kv_command("restore", commit_a_hash[:8], "a.md")

        # Assert (restore file)
        content_after_restore = (TEST_DIR / "a.md").read_text(encoding='utf-8')
        self.assertEqual(content_after_restore, "content a")


if __name__ == '__main__':
    unittest.main()
