"""merge 的合并语义测试：精确断言普通块与冲突块原文。"""

import unittest

from branchforge import Conflict, merge


class TestMergeSemantics(unittest.TestCase):
    def test_bridging_edits_form_single_region(self):
        # ours 的两个编辑 [1,2)、[3,4) 被 theirs 的一个编辑 [1,4) 串成同一区域
        base = b"0\n1\n2\n3\n4\n5\n"
        ours = b"0\nO1\n2\nO3\n4\n5\n"
        theirs = b"0\nT\n4\n5\n"
        blocks = merge(base, ours, theirs)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0], b"0\n")
        self.assertEqual(blocks[2], b"4\n5\n")
        conflict = blocks[1]
        self.assertIsInstance(conflict, Conflict)
        # 区域恰好是 [1,4)，不扩大也不拆散
        self.assertEqual((conflict.base_start, conflict.base_end), (1, 4))
        self.assertEqual(conflict.base, b"1\n2\n3\n")
        # 未被编辑覆盖的基线行 2 保留在 ours 的区域原文中
        self.assertEqual(conflict.ours, b"O1\n2\nO3\n")
        self.assertEqual(conflict.theirs, b"T\n")

    def test_same_position_insertions_conflict(self):
        base = b"a\nb\n"
        blocks = merge(base, b"a\nX\nb\n", b"a\nY\nb\n")
        self.assertEqual(blocks[0], b"a\n")
        self.assertEqual(blocks[2], b"b\n")
        conflict = blocks[1]
        self.assertIsInstance(conflict, Conflict)
        self.assertEqual((conflict.base_start, conflict.base_end), (1, 1))
        self.assertEqual(conflict.base, b"")
        self.assertEqual(conflict.ours, b"X\n")
        self.assertEqual(conflict.theirs, b"Y\n")

    def test_same_position_identical_insertions_kept_once(self):
        blocks = merge(b"a\nb\n", b"a\nX\nb\n", b"a\nX\nb\n")
        self.assertEqual(blocks, [b"a\n", b"X\n", b"b\n"])

    def test_insertions_at_deletion_interval_ends_no_conflict(self):
        # ours 删除区间 [1,3)；theirs 在区间两端（位置 1 和 3）插入：首尾相接不相碰
        base = b"a\nb\nc\nd\n"
        ours = b"a\nd\n"
        theirs = b"a\nL\nb\nc\nR\nd\n"
        blocks = merge(base, ours, theirs)
        # 边界插入：位置 1 的插入在删除之前，位置 3 的插入在删除之后
        self.assertEqual(blocks, [b"a\n", b"L\n", b"R\n", b"d\n"])

    def test_no_trailing_lf_preserved(self):
        base = b"a\nb"
        ours = b"a\nB"
        theirs = b"a\nb\nc\n"
        blocks = merge(base, ours, theirs)
        self.assertEqual(blocks[0], b"a\n")
        self.assertEqual(len(blocks), 2)
        conflict = blocks[1]
        self.assertIsInstance(conflict, Conflict)
        self.assertEqual(conflict.base, b"b")
        self.assertEqual(conflict.ours, b"B")
        self.assertEqual(conflict.theirs, b"b\nc\n")

    def test_no_trailing_lf_adopted_one_side(self):
        blocks = merge(b"a\nlast", b"a\nlast", b"a\nlast\n")
        self.assertEqual(blocks, [b"a\n", b"last\n"])

    def test_insertion_strictly_inside_edit_collides(self):
        # theirs 在 ours 的替换区间 [1,3) 内部（位置 2）插入 -> 相碰
        base = b"a\nb\nc\nd\n"
        ours = b"a\nX\nd\n"
        theirs = b"a\nb\nT\nc\nd\n"
        blocks = merge(base, ours, theirs)
        self.assertEqual(blocks[0], b"a\n")
        self.assertEqual(blocks[2], b"d\n")
        conflict = blocks[1]
        self.assertIsInstance(conflict, Conflict)
        self.assertEqual((conflict.base_start, conflict.base_end), (1, 3))
        self.assertEqual(conflict.base, b"b\nc\n")
        self.assertEqual(conflict.ours, b"X\n")
        self.assertEqual(conflict.theirs, b"b\nT\nc\n")

    def test_disjoint_changes_both_kept(self):
        base = b"1\n2\n3\n4\n5\n"
        blocks = merge(base, b"ONE\n2\n3\n4\n5\n", b"1\n2\n3\n4\nFIVE\n")
        self.assertEqual(blocks, [b"ONE\n", b"2\n3\n4\n", b"FIVE\n"])

    def test_identical_change_kept_once(self):
        blocks = merge(b"a\nb\n", b"a\nZ\n", b"a\nZ\n")
        self.assertEqual(blocks, [b"a\n", b"Z\n"])

    def test_one_side_unchanged(self):
        base = b"a\nb\n"
        self.assertEqual(merge(base, b"a\nX\nb\n", base), [b"a\n", b"X\n", b"b\n"])
        self.assertEqual(merge(base, base, b"X\n"), [b"X\n"])

    def test_empty_base(self):
        blocks = merge(b"", b"o\n", b"t\n")
        self.assertEqual(len(blocks), 1)
        conflict = blocks[0]
        self.assertIsInstance(conflict, Conflict)
        self.assertEqual((conflict.base_start, conflict.base_end), (0, 0))
        self.assertEqual(conflict.base, b"")
        self.assertEqual(conflict.ours, b"o\n")
        self.assertEqual(conflict.theirs, b"t\n")

    def test_conflict_markers_are_plain_content(self):
        base = b"a\n"
        ours = b"<<<<<<< ours\n"
        theirs = b">>>>>>> theirs\n"
        blocks = merge(base, ours, theirs)
        self.assertEqual(len(blocks), 1)
        self.assertIsInstance(blocks[0], Conflict)
        self.assertEqual(blocks[0].ours, b"<<<<<<< ours\n")
        self.assertEqual(blocks[0].theirs, b">>>>>>> theirs\n")

    def test_transitive_chain_not_split(self):
        # ours 的编辑 [0,2)、[3,5) 与 theirs 的编辑 [1,4) 传递相碰，
        # 闭包为同一区域 [0,5)，不得拆散也不得扩大
        base = b"0\n1\n2\n3\n4\n5\n"
        ours = b"A\nB\n2\nC\nD\n5\n"
        theirs = b"0\nT\n4\n5\n"
        blocks = merge(base, ours, theirs)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[1], b"5\n")
        conflict = blocks[0]
        self.assertEqual((conflict.base_start, conflict.base_end), (0, 5))
        self.assertEqual(conflict.base, b"0\n1\n2\n3\n4\n")
        self.assertEqual(conflict.ours, b"A\nB\n2\nC\nD\n")
        self.assertEqual(conflict.theirs, b"0\nT\n4\n")


if __name__ == "__main__":
    unittest.main()
