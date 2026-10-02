"""逐行 diff：返回把 base 变成 target 的最短编辑序列。

算法：Myers O((N+M)*D) 贪心搜索的线性空间（分治中点蛇）变体，
额外内存 O(N+M)，不生成与 N*M 同阶的状态。

决胜规则（重复行导致多种最短对齐时，保证结果确定）：
- 前向扫描中，删除与插入候选并列（V[k-1] + 1 == V[k+1]）时优先删除；
- 反向扫描中，并列时优先选择上移路径（对应反向的插入）；
- 全过程无随机性，同一输入永远产生同一编辑序列。
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass

from branchforge.lines import split_lines


@dataclass(frozen=True, slots=True)
class Edit:
    """对基线行区间 [start, end) 的替换；start == end 表示纯插入。"""

    start: int
    end: int
    replacement: bytes


def _middle_snake(
    a: list[bytes], alo: int, b: list[bytes], blo: int, n: int, m: int
) -> tuple[int, int, int, int, int]:
    """在 a[alo:alo+n] x b[blo:blo+m] 上找中点蛇。

    返回 (x, y, u, v, d)：蛇从相对坐标 (x, y) 到 (u, v)，d 为该盒子的最短编辑距离。
    """
    delta = n - m
    off = n + m
    size = 2 * (n + m) + 1
    vf = array("i", [-1]) * size
    vb = array("i", [n + 1]) * size
    vf[off + 1] = 0
    vb[off + delta - 1] = n

    for d in range(0, (n + m) // 2 + 2):
        # 前向：对角线 k 与 d 同奇偶，且有效对角线落在 [-m, n] 内。
        k_hi = min(d, n)
        if (k_hi - d) % 2:
            k_hi -= 1
        k_lo = max(-d, -m)
        if (k_lo + d) % 2:
            k_lo += 1
        for k in range(k_lo, k_hi + 1, 2):
            down = vf[off + k + 1]
            right = vf[off + k - 1]
            down_ok = down >= 0 and down - k <= m
            right_ok = right >= 0 and right + 1 <= n
            if down_ok and (not right_ok or down > right + 1):
                x = down
            elif right_ok:
                x = right + 1
            else:
                vf[off + k] = -1
                continue
            y = x - k
            if y < 0 or y > m:
                vf[off + k] = -1
                continue
            xs, ys = x, y
            while x < n and y < m and a[alo + x] == b[blo + y]:
                x += 1
                y += 1
            vf[off + k] = x
            if delta % 2 != 0 and delta - (d - 1) <= k <= delta + (d - 1):
                rv = vb[off + k]
                if rv <= n and x >= rv:
                    return (xs, ys, x, y, 2 * d - 1)
        # 反向：对角线 k 与 delta + d 同奇偶。
        k_hi = min(delta + d, n)
        if (k_hi - delta - d) % 2:
            k_hi -= 1
        k_lo = max(delta - d, -m)
        if (k_lo - delta - d) % 2:
            k_lo += 1
        for k in range(k_hi, k_lo - 1, -2):
            up = vb[off + k - 1]
            left = vb[off + k + 1]
            up_ok = up <= n
            left_ok = 1 <= left <= n
            if left_ok and (not up_ok or left - 1 < up):
                x = left - 1
            elif up_ok:
                x = up
            else:
                vb[off + k] = n + 1
                continue
            y = x - k
            if y < 0 or y > m:
                vb[off + k] = n + 1
                continue
            xs, ys = x, y
            while x > 0 and y > 0 and a[alo + x - 1] == b[blo + y - 1]:
                x -= 1
                y -= 1
            vb[off + k] = x
            if delta % 2 == 0 and -d <= k <= d:
                fv = vf[off + k]
                if fv >= 0 and x <= fv:
                    return (x, y, xs, ys, 2 * d)
    raise AssertionError("middle snake not found")  # pragma: no cover


# 操作元组：(基线位置, 类别, 行)；类别 0=删除该行，1=在该基线位置前插入行。
_Op = tuple[int, int, bytes | None]


def _collect_ops(
    a: list[bytes], b: list[bytes], ops: list[_Op]
) -> None:
    stack = [(0, len(a), 0, len(b))]
    while stack:
        alo, an, blo, bn = stack.pop()
        start = 0
        lo = min(an, bn)
        while start < lo and a[alo + start] == b[blo + start]:
            start += 1
        end = 0
        rem = lo - start
        while end < rem and a[alo + an - 1 - end] == b[blo + bn - 1 - end]:
            end += 1
        alo2, an2 = alo + start, an - start - end
        blo2, bn2 = blo + start, bn - start - end
        if an2 == 0:
            for j in range(bn2):
                ops.append((alo2, 1, b[blo2 + j]))
            continue
        if bn2 == 0:
            for i in range(an2):
                ops.append((alo2 + i, 0, None))
            continue
        x, y, u, v, _d = _middle_snake(a, alo2, b, blo2, an2, bn2)
        stack.append((alo2 + u, an2 - u, blo2 + v, bn2 - v))
        stack.append((alo2, x, blo2, y))


def _hunks_from_ops(ops: list[_Op]) -> list[Edit]:
    edits: list[Edit] = []
    cur_start = -1
    cur_end = -1
    parts: list[bytes] = []

    def flush() -> None:
        nonlocal cur_start, cur_end, parts
        if cur_start >= 0:
            edits.append(Edit(cur_start, cur_end, b"".join(parts)))
        cur_start = -1
        cur_end = -1
        parts = []

    for pos, kind, line in ops:
        if kind == 0:
            if cur_start < 0:
                cur_start, cur_end = pos, pos + 1
            elif pos == cur_end:
                cur_end = pos + 1
            else:
                flush()
                cur_start, cur_end = pos, pos + 1
        else:
            assert line is not None
            if cur_start < 0:
                cur_start = cur_end = pos
                parts = [line]
            elif cur_start <= pos <= cur_end:
                parts.append(line)
            else:
                flush()
                cur_start = cur_end = pos
                parts = [line]
    flush()
    return edits


def diff(base: bytes, target: bytes) -> list[Edit]:
    """返回把 base 变为 target 的编辑序列（按基线下标升序）。

    删除行数加插入行数最小；没有被保留行隔开的连续改动合并为一项。
    """
    a = split_lines(base)
    b = split_lines(target)
    ops: list[_Op] = []
    _collect_ops(a, b, ops)
    return _hunks_from_ops(ops)
