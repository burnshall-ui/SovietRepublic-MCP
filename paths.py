"""Game directory locations and the containment check that guards them.

Save names and building names arrive as MCP tool arguments, which makes them
untrusted input: a caller can pass anything, including "../../..". Path joining
accepts that happily and walks straight out of the game directory.

This lives apart from mcp_server so the containment logic can be imported and
tested without the MCP SDK or a copy of the game installed.
"""

from pathlib import Path

SAVES_DIR = Path(__file__).parent.parent / "media_soviet" / "save"
BUILDINGS_DIR = Path(__file__).parent.parent / "media_soviet" / "buildings_types"
ACTIVE_SAVE_FILE = Path(__file__).parent / "active_save.cfg"


def resolve_within(base: Path, *parts: str) -> Path | None:
    """Join ``parts`` onto ``base`` and return the result only if it stays inside.

    Returns ``None`` when the joined path would escape ``base`` — whether by
    traversal ("../../etc"), by an absolute path (which silently replaces
    ``base`` when joined), or by a symlink pointing outside.

    ``resolve()`` is what makes this work: it collapses ".." and follows
    symlinks, so the comparison happens on the real target rather than on the
    literal string the caller supplied.
    """
    if not parts or any(not isinstance(p, str) or p == "" for p in parts):
        return None

    try:
        candidate = base.joinpath(*parts).resolve()
        base_resolved = base.resolve()
    except (OSError, ValueError, RuntimeError):
        # Null bytes, symlink loops, paths past the OS limit.
        return None

    if candidate == base_resolved or base_resolved in candidate.parents:
        return candidate
    return None
