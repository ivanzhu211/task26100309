"""BranchForge 三方合并内核的公共数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Edit:
    """对基线的一次最小编辑。

    [start, end) 是基线行下标的左闭右开区间；replacement 是替换这些行的字节。
    start == end 表示在该位置纯插入（replacement 非空）。
    """

    start: int
    end: int
    replacement: bytes


@dataclass(frozen=True)
class Conflict:
    """一个三方冲突块。

    [base_start, base_end) 是冲突区域在基线上的行区间；
    base/ours/theirs 分别是该区域在三个版本中的原文（重放各侧编辑后的完整区域字节）。
    """

    base_start: int
    base_end: int
    base: bytes
    ours: bytes
    theirs: bytes


# merge 的输出块：普通字节块（bytes）或冲突块（Conflict）。
type Block = bytes | Conflict
