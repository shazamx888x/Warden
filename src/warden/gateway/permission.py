"""Control W5: permission-aware retrieval.

The model can only leak what it is shown. So Warden decides, before the
search runs, which access groups this caller may read, and the index only
returns documents from those groups. Another department's payroll register is
never retrieved for a line manager, so no prompt, however clever, can make the
model repeat it.
"""

from __future__ import annotations


# region: permission_filter
def allowed_groups(principal) -> list | None:
    """The access groups this caller may retrieve from.

    None would mean "no filter, search everything", which is exactly what the
    naive app does. Behind Warden the answer is always an explicit list.
    """
    return principal.grants()
# endregion: permission_filter
