"""diff 的独立参考判定测试。

参考实现是 O(N*M) 的 LCS 动态规划（仅用于小输入），与被测的 Myers
实现完全独立；对每个随机用例验证：
1. diff 的编辑成本（删除行数+插入行数）等于参考最短成本；
2. 重放编辑序列后逐字节等于 target；
3. 相邻编辑之间至少隔一条保留行（连续改动已合并）。
用例使用极小的行字母表以制造大量重复行。
"""

import random
import unittest

from branchforge import diff
from branchforge.diff import split_lines


def replay(base: bytes, edits) -> bytes:
    lines = split_lines(base)
    out, cur = [], 0
    for e in edits:
        assert cur <= e.start <= e.end <= len(lines)
        out.extend(lines[cur:e.start])
        out.append(e.replacement)
        cur = e.end
    out.extend(lines[cur:])
    return b"".join(out)


def reference_min_cost(a, b) -> int:
    """删除+插入的最短成本 = n + m - 2*|LCS|。"""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if a[i] == b[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    return n + m - 2 * dp[0][0]


def edit_cost(edits) -> int:
    return sum(e.end - e.start + len(split_lines(e.replacement)) for e in edits)


class TestDiffAgainstReference(unittest.TestCase):
    def check(self, base: bytes, target: bytes) -> None:
        edits = diff(base, target)
        self.assertEqual(replay(base, edits), target)
        self.assertEqual(
            edit_cost(edits),
            reference_min_cost(split_lines(base), split_lines(target)),
            f"非最短: base={base!r} target={target!r} edits={edits!r}",
        )
        for e1, e2 in zip(edits, edits[1:]):
            self.assertLess(e1.end, e2.start, "相邻编辑之间必须有保留行")

    def test_random_small_with_duplicate_lines(self):
        rng = random.Random(20261003)
        alphabet = [b"a\n", b"b\n", b"\n", b"c\n"]
        for _ in range(3000):
            base = b"".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))
            target = b"".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))
            self.check(base, target)

    def test_random_small_no_trailing_lf(self):
        rng = random.Random(7)
        alphabet = [b"x\n", b"x\n", b"y\n", b"tail"]
        for _ in range(2000):
            base = b"".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8)))
            target = b"".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8)))
            self.check(base, target)

    def test_edge_cases(self):
        self.check(b"", b"")
        self.check(b"", b"a\nb")
        self.check(b"a\nb", b"")
        self.check(b"a\n", b"a\n")
        self.check(b"no-newline", b"no-newline")
        self.check(b"no-newline", b"no-newline\n")
        self.check(b"\n\n\n", b"\n")

    def test_deterministic(self):
        base = b"a\nb\na\nb\na\n"
        target = b"b\na\nb\na\nb\n"
        first = diff(base, target)
        for _ in range(5):
            self.assertEqual(diff(base, target), first)

    def test_adjacent_changes_merged(self):
        # 两处改动之间没有保留行，必须合成一项
        edits = diff(b"a\nb\nc\n", b"x\ny\nc\n")
        self.assertEqual(len(edits), 1)
        self.assertEqual((edits[0].start, edits[0].end), (0, 2))
        self.assertEqual(edits[0].replacement, b"x\ny\n")


if __name__ == "__main__":
    unittest.main()
