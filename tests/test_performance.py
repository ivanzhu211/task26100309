"""大规模场景测试：100000 行、大量重复行、两侧合计最短编辑成本 <= 200。

实际运行 merge，用 tracemalloc 测量合并过程的峰值额外内存
（输入字节串在统计前已构造，不计入），并校验合并结果正确。
"""

from __future__ import annotations

import random
import time
import tracemalloc
import unittest

from branchforge import ConflictBlock, StableBlock, merge

LINE_COUNT = 100_000
POOL_SIZE = 60
MEMORY_LIMIT = 128 * 1024 * 1024


def build_inputs() -> tuple[bytes, bytes, bytes, list, list, list, bytes]:
    rng = random.Random(26100309)
    pool = [b"line-%03d\n" % i for i in range(POOL_SIZE)]
    base_lines = [rng.choice(pool) for _ in range(LINE_COUNT)]

    taken: list[int] = []

    def pick(count: int) -> list[int]:
        spots = []
        while len(spots) < count:
            p = rng.randrange(10, LINE_COUNT - 10)
            if all(abs(p - q) > 5 for q in taken):
                taken.append(p)
                spots.append(p)
        return spots

    # 每侧构造编辑成本 100 行：20 替换(x2) + 15 插入(x2) + 15 删除(x2)。
    def make_edits(tag: bytes, rep_spots, ins_spots, del_spots):
        edits = []
        for k, p in enumerate(rep_spots):
            edits.append((p, p + 1, [b"%s-rep-%d\n" % (tag, k)]))
        for k, p in enumerate(ins_spots):
            edits.append((p, p, [b"%s-ins-%d-a\n" % (tag, k),
                                 b"%s-ins-%d-b\n" % (tag, k)]))
        for k, p in enumerate(del_spots):
            edits.append((p, p + 2, []))
        return edits

    ours_edits = make_edits(b"ours", pick(20), pick(15), pick(15))
    theirs_edits = make_edits(b"theirs", pick(17), pick(15), pick(15))
    # 3 处与 ours 同一行的替换，制造冲突（合计编辑成本仍 <= 200）。
    collisions = []
    for k in range(3):
        p = ours_edits[k][0]
        theirs_edits.append((p, p + 1, [b"theirs-conflict-%d\n" % k]))
        collisions.append((p, ours_edits[k][2][0], b"theirs-conflict-%d\n" % k))

    def apply(lines, edits):
        out = list(lines)
        for start, end, repl in sorted(edits, reverse=True):
            out[start:end] = repl
        return out

    ours_lines = apply(base_lines, ours_edits)
    theirs_lines = apply(base_lines, theirs_edits)
    # 冲突解决为 ours 时的期望结果：ours 全部编辑 + theirs 非冲突编辑。
    colliding = {c[0] for c in collisions}
    expected = b"".join(apply(
        base_lines,
        ours_edits + [e for e in theirs_edits if e[0] not in colliding],
    ))
    collisions.sort(key=lambda item: item[0])
    return (
        b"".join(base_lines),
        b"".join(ours_lines),
        b"".join(theirs_lines),
        base_lines,
        ours_edits,
        collisions,
        expected,
    )


class LargeScaleTest(unittest.TestCase):
    def test_merge_100k_lines(self) -> None:
        base, ours, theirs, base_lines, ours_edits, collisions, expected = (
            build_inputs()
        )
        self.assertLessEqual(len(base), 10 * 1024 * 1024)

        tracemalloc.start()
        start = time.perf_counter()
        blocks = merge(base, ours, theirs)
        elapsed = time.perf_counter() - start
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        conflicts = [b for b in blocks if isinstance(b, ConflictBlock)]
        self.assertEqual(len(conflicts), 3)
        for conflict, (p, ours_line, theirs_line) in zip(conflicts, collisions):
            self.assertEqual((conflict.base_start, conflict.base_end), (p, p + 1))
            self.assertEqual(conflict.ours, ours_line)
            self.assertEqual(conflict.theirs, theirs_line)
            self.assertEqual(conflict.base, base_lines[p])

        resolved = b"".join(
            blk.data if isinstance(blk, StableBlock) else blk.ours
            for blk in blocks
        )
        self.assertEqual(resolved, expected)

        print("\nmerge 100k lines: %.2fs, peak extra memory: %.1f MiB"
              % (elapsed, peak / 1024 / 1024))
        self.assertLess(peak, MEMORY_LIMIT)
        self.assertLess(elapsed, 90)


if __name__ == "__main__":
    unittest.main()
