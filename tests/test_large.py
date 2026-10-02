"""大规模场景测试：100000 行、短差异、大量重复行，实际运行并测量内存。

数据可复现（固定随机种子）。两侧相对 base 的合计最短编辑成本不超过 200 行。
用 tracemalloc 测量 merge 期间的峰值额外内存（输入字节串在开始测量前构造），
要求低于 128 MiB；同时校验合并结果的结构正确性。
"""

import random
import time
import tracemalloc
import unittest

from branchforge import Conflict, merge
from branchforge.diff import split_lines

N_LINES = 100_000
MEM_LIMIT = 128 * 1024 * 1024


def build_inputs():
    rng = random.Random(26100309)
    # 大量重复行：约一半行来自小池子，其余为唯一行
    pool = [b"dup\n", b"common\n", b"\n", b"\t\n"]
    lines = []
    for i in range(N_LINES):
        if rng.random() < 0.5:
            lines.append(rng.choice(pool))
        else:
            lines.append(b"line %d\n" % i)
    base = b"".join(lines)

    # ours：约 55 行改动（替换 40 行、删除 10 行、插入 5 行）
    ours_lines = list(lines)
    idxs = sorted(rng.sample(range(1, N_LINES - 1), 65))
    for i in idxs[:40]:
        ours_lines[i] = b"ours %d\n" % i
    for i in idxs[40:50]:
        ours_lines[i] = b""
    for i in idxs[50:55]:
        ours_lines[i] = ours_lines[i] + b"ours-insert\n"
    ours = b"".join(ours_lines)

    # theirs：约 55 行改动，其中 3 处与 ours 碰同一行以制造冲突
    theirs_lines = list(lines)
    jdxs = sorted(rng.sample(range(1, N_LINES - 1), 62))
    for i in jdxs[:40]:
        theirs_lines[i] = b"theirs %d\n" % i
    for i in jdxs[40:50]:
        theirs_lines[i] = b""
    for i in jdxs[50:55]:
        theirs_lines[i] = theirs_lines[i] + b"theirs-insert\n"
    for i in idxs[30:33]:
        theirs_lines[i] = b"theirs-conflict %d\n" % i
    theirs = b"".join(theirs_lines)
    return base, ours, theirs


class TestLargeScale(unittest.TestCase):
    def test_100k_lines_merge_memory_and_correctness(self):
        base, ours, theirs = build_inputs()
        self.assertLessEqual(len(base), 10 * 1024 * 1024)

        tracemalloc.start()
        started = time.monotonic()
        blocks = merge(base, ours, theirs)
        elapsed = time.monotonic() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertLess(
            peak,
            MEM_LIMIT,
            f"峰值额外内存 {peak / 1024 / 1024:.1f} MiB 超过 128 MiB",
        )
        print(
            f"\n100k 行合并: {elapsed:.2f}s, 峰值额外内存 {peak / 1024 / 1024:.1f} MiB"
        )

        # 结构校验：普通块与冲突块按序拼回后，冲突区域外的内容与两侧一致
        conflicts = [b for b in blocks if isinstance(b, Conflict)]
        self.assertEqual(len(conflicts), 3)
        plain = b"".join(b for b in blocks if not isinstance(b, Conflict))
        # 未相碰的变更必须都在结果中：抽查两侧的独有修改
        self.assertIn(b"ours-insert\n", plain)
        self.assertIn(b"theirs-insert\n", plain)
        for conflict in conflicts:
            self.assertIn(b"ours ", conflict.ours)
            self.assertIn(b"theirs-conflict ", conflict.theirs)
            # 冲突块的 base 原文与基线行区间一致
            base_lines = split_lines(base)
            self.assertEqual(
                conflict.base,
                b"".join(base_lines[conflict.base_start : conflict.base_end]),
            )


if __name__ == "__main__":
    unittest.main()
