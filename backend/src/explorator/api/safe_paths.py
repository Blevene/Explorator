"""Filesystem paths built from request or database values, kept inside a root."""

import os


def resolve_under(root: str, *parts: str) -> str:
    """Join *parts* onto *root* and return the real path, which must lie inside *root*.

    Raises ValueError when the result escapes *root* (``..``, absolute parts,
    symlinks) or is *root* itself.
    """
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, *parts))
    if target == base or os.path.commonpath([base, target]) != base:
        msg = f"path escapes {root!r}"
        raise ValueError(msg)
    return target


def is_under(root: str, path: str) -> bool:
    """True when *path* (after resolving symlinks and ``..``) lies inside *root*."""
    base = os.path.realpath(root)
    target = os.path.realpath(path)
    return target != base and os.path.commonpath([base, target]) == base
