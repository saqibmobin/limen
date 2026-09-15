"""Thin, cached wrapper over the git plumbing commands hldcheck needs.

All access is read-only and addressed by revision, so the working tree can be
dirty without affecting results.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from .model import CheckError


class Git:
    def __init__(self, repo: Path):
        self.repo = Path(repo).resolve()
        if not (self.repo / ".git").exists():
            # Support worktrees and bare-ish layouts via rev-parse rather than
            # insisting on a literal .git directory.
            rc, _, _ = self._run(["rev-parse", "--git-dir"])
            if rc != 0:
                raise CheckError(f"{self.repo} is not a git repository")

    def _run(self, args: list[str], binary: bool = False):
        proc = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
        )
        out = proc.stdout if binary else proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        return proc.returncode, out, err

    @lru_cache(maxsize=None)
    def rev_parse(self, rev: str) -> str | None:
        """Full 40-char SHA for a revision, or None if unknown to this repo."""
        rc, out, _ = self._run(["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"])
        return out.strip() if rc == 0 and out.strip() else None

    @lru_cache(maxsize=None)
    def path_kind(self, rev: str, path: str) -> str | None:
        """'blob', 'tree', or None if the path does not exist at rev."""
        clean = path.rstrip("/")
        rc, out, _ = self._run(["cat-file", "-t", f"{rev}:{clean}"])
        if rc != 0:
            return None
        kind = out.strip()
        return kind if kind in ("blob", "tree") else None

    @lru_cache(maxsize=None)
    def blob_text(self, rev: str, path: str) -> str | None:
        """UTF-8 text of a blob at rev, or None if absent/binary."""
        rc, out, _ = self._run(["cat-file", "blob", f"{rev}:{path}"], binary=True)
        if rc != 0:
            return None
        if b"\x00" in out[:8192]:
            return None
        return out.decode("utf-8", "replace")

    def is_dirty(self) -> bool:
        rc, out, _ = self._run(["status", "--porcelain", "--untracked-files=no"])
        return rc == 0 and bool(out.strip())

    def head(self) -> str | None:
        return self.rev_parse("HEAD")
