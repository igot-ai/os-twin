"""Backend policy wrapper that updates the code index on file changes.

Intercepts write() and edit() calls on the inner backend. When a file
with an indexable extension (outside .agents/) is successfully written
or edited, triggers a CocoIndex incremental re-index.

Usage:
    from code_index_hook import IndexingBackendWrapper
    wrapped = IndexingBackendWrapper(composite_backend)
"""

from __future__ import annotations

import logging
from typing import Any

from deepagents.backends.protocol import (
    BackendProtocol,
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)

logger = logging.getLogger(__name__)

# Lazy-import code_index to avoid loading cocoindex at import time
_code_index = None


def _get_code_index():
    """Lazy-load the code_index module."""
    global _code_index
    if _code_index is None:
        import sys
        from pathlib import Path

        memory_dir = str(Path(__file__).resolve().parent.parent / "memory")
        if memory_dir not in sys.path:
            sys.path.insert(0, memory_dir)
        import code_index

        _code_index = code_index
    return _code_index


class IndexingBackendWrapper(BackendProtocol):
    """Backend wrapper that triggers code index updates on file changes.

    Delegates all operations to the inner backend. After a successful
    write or edit to an indexable file, schedules a background index update.
    """

    def __init__(self, inner: BackendProtocol) -> None:
        self.inner = inner
        self._pending_update = False

    def _update_index(self, file_path: str) -> None:
        """Trigger an index update if the file is indexable."""
        try:
            ci = _get_code_index()
            if ci.is_indexable(file_path):
                ci.notify_file_changed(file_path)
        except Exception:
            logger.debug("Code index update skipped for %s", file_path, exc_info=True)

    # --- Passthrough: read-only operations ---

    def ls_info(self, path: str) -> list[FileInfo]:
        return self.inner.ls_info(path)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        return self.inner.read(file_path, offset=offset, limit=limit)

    def grep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        return self.inner.grep_raw(pattern, path, glob)

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        return self.inner.glob_info(pattern, path)

    # --- Intercepted: write operations ---

    def write(self, file_path: str, content: str) -> WriteResult:
        result = self.inner.write(file_path, content)
        if result.error is None:
            self._update_index(file_path)
        return result

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        result = self.inner.edit(file_path, old_string, new_string, replace_all)
        if result.error is None:
            self._update_index(file_path)
        return result

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        results = self.inner.upload_files(files)
        for (path, _content), resp in zip(files, results):
            if resp.error is None:
                self._update_index(path)
        return results

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return self.inner.download_files(paths)
