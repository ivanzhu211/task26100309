"""merge 的语义测试：精确断言普通块序列与冲突块三侧原文。"""

from __future__ import annotations

import unittest

from branchforge import ConflictBlock, StableBlock, merge


def lines(*texts: bytes) -> bytes:
    return b"".join(texts)


BASE10 = lines(*[b"l%d\n" % i for i in range(10)])


class MergeSemanticsTest(unittest.TestCase):
    def test_chained_edits_form_single_region(self) -> None:
        # ours 的两处独立编辑被 theirs 的一处大编辑串成同一冲突区域。
        ours = lines(b"l0\n", b"l1\n", b"O2\n", b"l3\n", b"l4\n",
                     b"l5\n", b"l6\n", b"O7\n", b"l8\n", b"l9\n")
        theirs = lines(b"l0\n", b"T\n", b"l9\n")
        blocks = merge(BASE10, ours, theirs)
        self.assertEqual(
            blocks,
            [
                StableBlock(b"l0\n"),
                ConflictBlock(
                    1,
                    9,
                    lines(b"l1\n", b"l2\n", b"l3\n", b"l4\n",
                          b"l5\n", b"l6\n", b"l7\n", b"l8\n"),
                    lines(b"l1\n", b"O2\n", b"l3\n", b"l4\n",
                          b"l5\n", b"l6\n", b"O7\n", b"l8\n"),
                    b"T\n",
                ),
                StableBlock(b"l9\n"),
            ],
        )

    def test_same_position_insertions(self) -> None:
        base = b"1\n2\n"
        # 同位置不同内容：空基线区间冲突。
        self.assertEqual(
            merge(base, b"1\nX\n2\n", b"1\nY\n2\n"),
            [
                StableBlock(b"1\n"),
                ConflictBlock(1, 1, b"", b"X\n", b"Y\n"),
                StableBlock(b"2\n"),
            ],
        )
        # 同位置相同内容：只保留一次，无冲突。
        self.assertEqual(
            merge(base, b"1\nX\n2\n", b"1\nX\n2\n"),
            [StableBlock(b"1\nX\n2\n")],
        )

    def test_insertions_at_deletion_boundaries(self) -> None:
        # ours 删除 [2,4)；theirs 在区间两端插入：不相碰，全部采纳。
        base = lines(b"l0\n", b"l1\n", b"l2\n", b"l3\n", b"l4\n")
        ours = lines(b"l0\n", b"l1\n", b"l4\n")
        theirs = lines(b"l0\n", b"l1\n", b"pre\n", b"l2\n", b"l3\n",
                       b"post\n", b"l4\n")
        self.assertEqual(
            merge(base, ours, theirs),
            [StableBlock(b"l0\nl1\npre\npost\nl4\n")],
        )

    def test_last_line_without_lf(self) -> None:
        base = b"a\nb"
        # 一侧修改末行，另一侧不变：结果末行仍无 LF。
        self.assertEqual(merge(base, b"a\nB", base), [StableBlock(b"a\nB")])
        # 末行冲突：三侧原文都保留无 LF 状态。
        self.assertEqual(
            merge(base, b"a\nB", b"a\nC"),
            [StableBlock(b"a\n"), ConflictBlock(1, 2, b"b", b"B", b"C")],
        )
        # 一侧改末行、另一侧在末尾追加：冲突原文保留各自末行状态。
        self.assertEqual(
            merge(base, b"a\nB", b"a\nb\nc\n"),
            [
                StableBlock(b"a\n"),
                ConflictBlock(1, 2, b"b", b"B", b"b\nc\n"),
            ],
        )

    def test_conflict_marker_text_is_plain_content(self) -> None:
        base = b"<<<<<<< ours\n=======\n>>>>>>> theirs\nkeep\n"
        blocks = merge(base, base.replace(b"keep", b"ours1"),
                       base.replace(b"keep", b"theirs1"))
        self.assertEqual(
            blocks,
            [
                StableBlock(b"<<<<<<< ours\n=======\n>>>>>>> theirs\n"),
                ConflictBlock(3, 4, b"keep\n", b"ours1\n", b"theirs1\n"),
            ],
        )

    def test_different_edits_same_result(self) -> None:
        # 两侧编辑区间不同但重放结果一致：只保留一次，无冲突。
        base = b"1\n2\n3\n"
        self.assertEqual(
            merge(base, b"1\nX\n3\n", b"1\nX\n3\n"),
            [StableBlock(b"1\nX\n3\n")],
        )
        # ours 改一行，theirs 改两行但净效果相同。
        self.assertEqual(
            merge(b"1\n2\n3\n4\n", b"1\nX\n3\n4\n", b"1\nX\n3\n4\n"),
            [StableBlock(b"1\nX\n3\n4\n")],
        )

    def test_non_overlapping_edits_all_kept(self) -> None:
        # 两侧修改同一文件的不同位置：两侧变更都必须出现。
        blocks = merge(BASE10, BASE10.replace(b"l1\n", b"A\n"),
                       BASE10.replace(b"l8\n", b"B\n"))
        self.assertEqual(
            blocks,
            [StableBlock(BASE10.replace(b"l1\n", b"A\n").replace(b"l8\n", b"B\n"))],
        )

    def test_touching_intervals_do_not_collide(self) -> None:
        # ours 改 [1,2)，theirs 改 [2,3)：首尾相接，不相碰。
        self.assertEqual(
            merge(b"1\n2\n3\n", b"1\nA\n3\n", b"1\n2\nB\n"),
            [StableBlock(b"1\nA\nB\n")],
        )


if __name__ == "__main__":
    unittest.main()
