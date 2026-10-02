"""行拆分工具：仅以 LF 分行，LF 属于该行；不做任何换行归一化。"""

from __future__ import annotations


def split_lines(data: bytes) -> list[bytes]:
    """把字节串拆成保留 LF 的行列表。

    空串返回零行；末行允许没有 LF。对任意输入都有
    b"".join(split_lines(data)) == data。
    """
    if not data:
        return []
    parts = data.split(b"\n")
    lines = [part + b"\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines
