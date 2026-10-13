"""One seed resolver shared by sampling, cache matching and plan builders."""

from __future__ import annotations

MAX_SEED = (1 << 64) - 1


def parse_segment_seed(value) -> int | None:
    """Empty means inherit; decimal strings preserve uint64 precision in JSON."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("分段一采 seed 必须是 0 至 18446744073709551615 的整数，或留空继承全局。")
    text = str(value).strip()
    if not text.isascii() or not text.isdecimal():
        raise ValueError(f"无效的分段一采 seed：{value!r}；请输入非负十进制整数。")
    seed = int(text)
    if seed > MAX_SEED:
        raise ValueError("分段一采 seed 超出 uint64 范围。")
    return seed


def seed_from_row(row) -> int | None:
    return parse_segment_seed((row or {}).get("first_pass_seed"))


def resolve_segment_seed(seg, plan) -> int:
    override = parse_segment_seed(getattr(seg, "first_pass_seed", None))
    return int(getattr(plan, "sample_seed", 0) or 0) if override is None else override


def seed_from_group(group, row) -> int | None:
    """A wired group override wins; empty groups inherit the Director card."""
    override = seed_from_row(group)
    return seed_from_row(row) if override is None else override
