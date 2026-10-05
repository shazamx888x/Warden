"""Who is asking, and what they may read.

Warden authenticates the caller against the staff directory and resolves their
role, department and employee id. Everything downstream is a function of this:
the retrieval filter (W5) turns it into a set of access groups, and the tool
policy (W8) turns it into a set of permitted actions. An unauthenticated
caller gets nothing.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from warden import constants as C

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "data/corpus/employees.csv"


class NotAuthenticated(Exception):
    pass


@dataclass
class Principal:
    user_id: str
    employee_id: str
    role: str
    department: str
    name: str = ""
    # Set True ONLY for a tool the human explicitly asked for this turn. The
    # tool policy uses it to tell a user request from a model proposal.
    initiated_by_user: bool = False

    def grants(self) -> list:
        return C.grants_for(self.role, self.employee_id, self.department)


# region: identity
class Directory:
    """The staff directory. Credential is the employee id in this demo; in
    production it is an Entra ID / OIDC token, and only this class changes."""

    def __init__(self, path: Path | None = None):
        self.people = {}
        source = path or CORPUS
        if source.exists():
            with source.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    self.people[row["employee_id"]] = row

    def resolve(self, credential: str | None, initiated_by_user: bool = False) -> Principal:
        if not credential or credential not in self.people:
            raise NotAuthenticated("unknown or missing credential")
        row = self.people[credential]
        return Principal(
            user_id=row["employee_id"], employee_id=row["employee_id"],
            role=row["role"], department=row["department"], name=row["name"],
            initiated_by_user=initiated_by_user)
# endregion: identity
