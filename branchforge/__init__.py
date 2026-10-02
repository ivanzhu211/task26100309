"""BranchForge：逐行三方合并内核。"""

from .diff import diff
from .merge import merge
from .types import Conflict, Edit

__all__ = ["diff", "merge", "Edit", "Conflict"]
