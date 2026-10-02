"""diff 的独立参考判定测试。

参考实现：行级编辑距离 DP（删除/插入代价 1，替换 = 删 + 插 = 2），
与 branchforge 的 Myers 实现完全独立。对每个用例验证：
1. diff 的编辑代价（删除行数 + 插入行数）等于参考最短路代价；
2. 重放编辑序列后逐字节等于 target；
3. 编辑项两两之间至少隔着一条保留行（连续改动已合并）；
4. 结果确定（重复调用完全一致）。
"""

from __future__ import annotations

import random
import unittest

from branchforge.diff import Edit, diff
from branchforge.lines import split_lines


def reference_distance(a: list[bytes], b: list[bytes]) -> int:
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 2
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[len(b)]


def replay(base: bytes, edits: list[Edit]) -> bytes:
    lines = split_lines(base)
    out: list[bytes] = []
    pos = 0
    for edit in edits:
        out.extend(lines[pos : edit.start])
        out.append(edit.replacement)
        pos = edit.end
    out.extend(lines[pos:])
    return b"".join(out)


def edit_cost(edits: list[Edit]) -> int:
    return sum(
        (edit.end - edit.start) + len(split_lines(edit.replacement))
        for edit in edits
    )


class DiffReferenceTest(unittest.TestCase):
    def check(self, base: bytes, target: bytes) -> None:
        edits = diff(base, target)
        self.assertEqual(replay(base, edits), target, (base, target, edits))
        self.assertEqual(
            edit_cost(edits),
            reference_distance(split_lines(base), split_lines(target)),
            (base, target, edits),
        )
        for first, second in zip(edits, edits[1:]):
            self.assertLess(
                first.end, second.start, ("编辑项之间必须有保留行", edits)
            )
        self.assertEqual(edits, diff(base, target), "结果必须确定")

    def test_handpicked(self) -> None:
        cases = [
            (b"", b""),
            (b"", b"a\n"),
            (b"a\n", b""),
            (b"a\n", b"a\n"),
            (b"a\nb\nc\n", b"a\nx\nc\n"),
            (b"a\nb\nc\n", b"x\ny\nz\n"),
            (b"x\n", b"x"),
            (b"x", b"x\ny"),
            (b"a\nb\n", b"a\nb"),
            (b"1\n2\n3\n4\n5\n", b"1\n3\n4\n5\n6\n"),
            (b"a\r\nb\r\n", b"a\r\nc\r\n"),
        ]
        for base, target in cases:
            with self.subTest(base=base, target=target):
                self.check(base, target)

    def test_random_with_repeated_lines(self) -> None:
        # 小字母表制造大量重复行；末行随机去掉 LF。
        rng = random.Random(20261003)
        pool = [b"a\n", b"b\n", b"c\n", b"\n", b"dd\n"]
        for _ in range(2000):
            a_lines = [rng.choice(pool) for _ in range(rng.randrange(0, 9))]
            if a_lines and rng.random() < 0.3:
                a_lines[-1] = a_lines[-1].rstrip(b"\n")
            b_lines = list(a_lines)
            for _ in range(rng.randrange(0, 5)):
                op = rng.randrange(3)
                if op == 0 and b_lines:
                    del b_lines[rng.randrange(len(b_lines))]
                elif op == 1:
                    b_lines.insert(rng.randrange(len(b_lines) + 1), rng.choice(pool))
                elif b_lines:
                    b_lines[rng.randrange(len(b_lines))] = rng.choice(pool)
            if b_lines and rng.random() < 0.3:
                b_lines[-1] = b_lines[-1].rstrip(b"\n")
            self.check(b"".join(a_lines), b"".join(b_lines))

    def test_random_independent_pairs(self) -> None:
        # base 与 target 独立随机，覆盖无公共子序列的情形。
        rng = random.Random(775)
        pool = [b"x\n", b"y\n", b"z\n"]
        for _ in range(800):
            a_lines = [rng.choice(pool) for _ in range(rng.randrange(0, 8))]
            b_lines = [rng.choice(pool) for _ in range(rng.randrange(0, 8))]
            self.check(b"".join(a_lines), b"".join(b_lines))


if __name__ == "__main__":
    unittest.main()
