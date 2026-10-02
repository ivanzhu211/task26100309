"""逐行三方合并：基于 diff 结果输出普通字节块与结构化冲突块。

相碰规则：
- 两侧非空编辑区间共享至少一条基线行时相碰；
- 纯插入仅在位置严格落入另一编辑区间内部时与之相碰；
- 两个纯插入位置相同则相碰；
- 区间仅首尾相接不算相碰。
冲突区域为相碰关系的传递闭包，不扩大、不拆散。
"""

from __future__ import annotations

from dataclasses import dataclass

from branchforge.diff import diff
from branchforge.lines import split_lines


@dataclass(frozen=True, slots=True)
class StableBlock:
    """无冲突内容块，按文件顺序排列。"""

    data: bytes


@dataclass(frozen=True, slots=True)
class ConflictBlock:
    """冲突块：保留基线行区间及三侧原文，不做标记渲染。"""

    base_start: int
    base_end: int
    base: bytes
    ours: bytes
    theirs: bytes


Block = StableBlock | ConflictBlock

# 带侧标记的编辑：(start, end, side, replacement)；side 0=ours，1=theirs。
_TaggedEdit = tuple[int, int, int, bytes]


def _components(edits: list[_TaggedEdit]) -> list[tuple[int, int, list[_TaggedEdit]]]:
    """把排序后的编辑按相碰关系的传递闭包聚成编辑集合。

    返回 (区域起点, 区域终点, 成员编辑) 列表，按文件顺序排列。
    连通编辑集合的基线覆盖区间必然连续，且区间内部点必然严格落在
    某个成员区间内部，因此用当前集合的覆盖区间即可判定新编辑是否相碰。
    """
    components: list[list] = []
    for edit in edits:
        s, e, _side, _repl = edit
        if components:
            cs, ce, members = components[-1]
            if e > s:
                hit = s < ce
            else:
                hit = (cs < s < ce) or (cs == ce == s)
            if hit:
                members.append(edit)
                components[-1][1] = max(ce, e)
                continue
        components.append([s, e, [edit]])
    return [(c[0], c[1], c[2]) for c in components]


def _replay(
    base_lines: list[bytes], rs: int, re: int, edits: list[_TaggedEdit]
) -> bytes:
    """在基线行区间 [rs, re) 上重放一侧编辑，未被覆盖的基线内容保留。"""
    out: list[bytes] = []
    pos = rs
    for s, e, _side, repl in edits:
        out.extend(base_lines[pos:s])
        out.append(repl)
        pos = e
    out.extend(base_lines[pos:re])
    return b"".join(out)


def merge(base: bytes, ours: bytes, theirs: bytes) -> list[Block]:
    """三方合并，返回按文件顺序排列的普通块与冲突块。"""
    base_lines = split_lines(base)
    tagged: list[_TaggedEdit] = [
        (e.start, e.end, 0, e.replacement) for e in diff(base, ours)
    ]
    tagged += [(e.start, e.end, 1, e.replacement) for e in diff(base, theirs)]
    tagged.sort(key=lambda item: (item[0], item[1], item[2]))

    blocks: list[Block] = []

    def emit_stable(data: bytes) -> None:
        if not data:
            return
        if blocks and isinstance(blocks[-1], StableBlock):
            blocks[-1] = StableBlock(blocks[-1].data + data)
        else:
            blocks.append(StableBlock(data))

    pos = 0
    for rs, re, members in _components(tagged):
        if rs > pos:
            emit_stable(b"".join(base_lines[pos:rs]))
        sides = {member[2] for member in members}
        if len(sides) == 1:
            emit_stable(_replay(base_lines, rs, re, members))
        else:
            ours_data = _replay(
                base_lines, rs, re, [m for m in members if m[2] == 0]
            )
            theirs_data = _replay(
                base_lines, rs, re, [m for m in members if m[2] == 1]
            )
            if ours_data == theirs_data:
                emit_stable(ours_data)
            else:
                blocks.append(
                    ConflictBlock(
                        rs,
                        re,
                        b"".join(base_lines[rs:re]),
                        ours_data,
                        theirs_data,
                    )
                )
        pos = re
    if pos < len(base_lines):
        emit_stable(b"".join(base_lines[pos:]))
    return blocks
