"""逐行最短差异。

算法：Myers O(ND) 贪心算法（在编辑图上按代价 d 逐层扩展 frontier），
通过保存每层的 V 数组回溯出完整脚本。设 D 为最短编辑成本（删除+插入行数），
时间 O((N+M)*D)，空间 O(D^2 + N + M)；在本库面向的场景（D 很小）下，
不会生成与两份全文行数乘积同阶的状态。

决胜规则（保证确定性）：扩展 frontier 时，若删除与插入能让对角线 k 到达同样
远的基线位置（V[k-1] == V[k+1]），优先选择删除（沿基线向右走），其次插入；
随后尽可能跟随 snake（连续的保留行）。整个过程中行只按完整字节比较，
比较前把每行映射为整数 id，比较本身与行内容无关，因此结果完全确定。
"""

from __future__ import annotations

from .types import Edit


def split_lines(data: bytes) -> list[bytes]:
    """按 LF 切行，LF 属于该行；空串返回零行；末行可以没有 LF。"""
    if not data:
        return []
    parts = data.split(b"\n")
    lines = [part + b"\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _line_ids(base_lines: list[bytes], target_lines: list[bytes]) -> tuple[list[int], list[int]]:
    ids: dict[bytes, int] = {}
    base_ids = [ids.setdefault(line, len(ids)) for line in base_lines]
    target_ids = [ids.setdefault(line, len(ids)) for line in target_lines]
    return base_ids, target_ids


def _myers_backtrack(a: list[int], b: list[int]) -> list[tuple]:
    """返回操作序列：('eq', n) | ('del', base_idx) | ('ins', target_idx)。"""
    n, m = len(a), len(b)
    if n == 0 and m == 0:
        return []
    max_d = n + m
    # 工作数组 v 按下标 k + offset 存储；每层结束后只把当前带宽 [-d, d]
    # 内的 frontier 压缩存入 snapshots（第 d 层共 d+1 个值），
    # 因此路径回溯的空间为 O(D^2)，与全文行数无关。
    offset = max_d
    size = 2 * max_d + 1
    v = [0] * size
    snapshots: list[list[int]] = []
    found_d = -1
    for d in range(0, max_d + 1):
        for k in range(-d, d + 1, 2):
            if k == -d or (k != d and v[k - 1 + offset] < v[k + 1 + offset]):
                x = v[k + 1 + offset]  # 插入（向下）
            else:
                x = v[k - 1 + offset] + 1  # 删除（向右）
            y = x - k
            while x < n and y < m and a[x] == b[y]:
                x += 1
                y += 1
            v[k + offset] = x
            if x >= n and y >= m:
                found_d = d
                break
        snapshots.append([v[k + offset] for k in range(-d, d + 1, 2)])
        if found_d >= 0:
            break

    ops: list[tuple] = []
    x, y = n, m
    for d in range(found_d, 0, -1):
        vprev = snapshots[d - 1]
        k = x - y

        def prev_at(kk: int) -> int:
            return vprev[(kk + d - 1) // 2]

        if k == -d or (k != d and prev_at(k - 1) < prev_at(k + 1)):
            prev_k = k + 1  # 上一步是插入
        else:
            prev_k = k - 1  # 上一步是删除
        x_edge = prev_at(prev_k)
        y_edge = x_edge - prev_k
        # snake 部分（从 (x_edge, y_edge) 对角走到 (x, y)）
        snake = x - x_edge if prev_k == k + 1 else x - x_edge - 1
        if snake:
            ops.append(("eq", snake))
        if prev_k == k + 1:
            ops.append(("ins", y_edge))
            x, y = x_edge, y_edge
        else:
            ops.append(("del", x_edge))
            x, y = x_edge, y_edge
    if x:
        ops.append(("eq", x))
    ops.reverse()
    return ops


def diff(base: bytes, target: bytes) -> list[Edit]:
    """返回把 base 变成 target 的最短编辑序列。

    每项 Edit 给出基线行下标的左闭右开区间及替换字节；空区间表示插入。
    没有被保留行隔开的连续改动合并为一项。
    """
    base_lines = split_lines(base)
    target_lines = split_lines(target)
    a, b = _line_ids(base_lines, target_lines)
    ops = _myers_backtrack(a, b)

    edits: list[Edit] = []
    base_cursor = 0
    run_start = -1
    run_end = -1
    inserted: list[bytes] = []

    def close_run() -> None:
        nonlocal run_start
        if run_start >= 0:
            edits.append(Edit(run_start, run_end, b"".join(inserted)))
            run_start = -1
            inserted.clear()

    for op in ops:
        kind = op[0]
        if kind == "eq":
            close_run()
            base_cursor += op[1]
        elif kind == "del":
            if run_start < 0:
                run_start = base_cursor
                run_end = base_cursor
            run_end = base_cursor + 1
            base_cursor += 1
        else:  # ins
            if run_start < 0:
                run_start = base_cursor
                run_end = base_cursor
            inserted.append(target_lines[op[1]])
    close_run()
    return edits
