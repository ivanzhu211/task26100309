"""基于 diff 的三方合并。

流程：
1. 分别计算 ours、theirs 相对 base 的编辑序列。
2. 按相碰规则对编辑做传递闭包分组（并查集）：
   - 两侧非空编辑区间有共同基线行时相碰；
   - 纯插入仅在位置严格落入另一编辑区间内部时与其相碰；
   - 两个纯插入在同一位置时相碰；
   - 区间仅首尾相接不算相碰。
3. 每个分组是冲突候选区域，恰好覆盖传递闭合后的最小编辑集合，不扩大、不拆散。
   只含一侧编辑的区域直接采纳；含两侧编辑的区域在区域基线上分别重放各侧编辑，
   所得字节完全一致时只保留一次，否则输出 Conflict 块（保留基线范围与三侧原文，
   未被编辑覆盖的基线内容包含在对应侧的区域原文中）。
4. 边界插入不与相邻替换相碰；输出排序时，位置 p 的纯插入排在结束于 p 的
   替换之后、开始于 p 的替换之前。
"""

from __future__ import annotations

from .diff import diff, split_lines
from .types import Block, Conflict, Edit


def _collides(a: Edit, b: Edit) -> bool:
    a_ins = a.start == a.end
    b_ins = b.start == b.end
    if a_ins and b_ins:
        return a.start == b.start
    if a_ins:
        return b.start < a.start < b.end
    if b_ins:
        return a.start < b.start < a.end
    return a.start < b.end and b.start < a.end


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        self.parent[self.find(x)] = self.find(y)


def _replay(base_lines: list[bytes], start: int, end: int, edits: list[Edit]) -> bytes:
    """在基线区域 [start, end) 上重放一侧的编辑，返回区域原文。"""
    out: list[bytes] = []
    cur = start
    for e in edits:
        out.extend(base_lines[cur:e.start])
        out.append(e.replacement)
        cur = e.end
    out.extend(base_lines[cur:end])
    return b"".join(out)


def merge(base: bytes, ours: bytes, theirs: bytes) -> list[Block]:
    """按文件顺序返回普通字节块（bytes）与冲突块（Conflict）。"""
    base_lines = split_lines(base)
    edits_ours = diff(base, ours)
    edits_theirs = diff(base, theirs)
    n_ours = len(edits_ours)
    all_edits = edits_ours + edits_theirs

    uf = _UnionFind(len(all_edits))
    for i in range(n_ours):
        for j in range(n_ours, len(all_edits)):
            if _collides(all_edits[i], all_edits[j]):
                uf.union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(all_edits)):
        groups.setdefault(uf.find(i), []).append(i)

    # 每个分组整理为 (rs, re, ours_edits, theirs_edits)
    regions: list[tuple[int, int, list[Edit], list[Edit]]] = []
    for members in groups.values():
        o_edits = [all_edits[i] for i in members if i < n_ours]
        t_edits = [all_edits[i] for i in members if i >= n_ours]
        non_empty = [e for e in o_edits + t_edits if e.start != e.end]
        if non_empty:
            rs = min(e.start for e in non_empty)
            re = max(e.end for e in non_empty)
        else:
            rs = re = (o_edits + t_edits)[0].start
        regions.append((rs, re, o_edits, t_edits))

    # 按基线位置排序；同起点时纯插入（空区间）排在非空编辑之前，
    # 使边界插入位于前一替换之后、后一替换之前。
    regions.sort(key=lambda r: (r[0], 0 if r[0] == r[1] else 1))

    blocks: list[Block] = []
    cursor = 0
    for rs, re, o_edits, t_edits in regions:
        if cursor < rs:
            blocks.append(b"".join(base_lines[cursor:rs]))
        if o_edits and t_edits:
            ours_text = _replay(base_lines, rs, re, o_edits)
            theirs_text = _replay(base_lines, rs, re, t_edits)
            if ours_text == theirs_text:
                if ours_text:
                    blocks.append(ours_text)
            else:
                blocks.append(
                    Conflict(
                        base_start=rs,
                        base_end=re,
                        base=b"".join(base_lines[rs:re]),
                        ours=ours_text,
                        theirs=theirs_text,
                    )
                )
        else:
            side = o_edits or t_edits
            text = _replay(base_lines, rs, re, side)
            if text:
                blocks.append(text)
        if re > cursor:
            cursor = re
    if cursor < len(base_lines):
        blocks.append(b"".join(base_lines[cursor:]))
    return blocks
