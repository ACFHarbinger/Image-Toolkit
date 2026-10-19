"""User edits to risk rules, kept in cloud_jobs.db over the shipped seed (#830)."""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List

from .engine import Rule, RuleSet, load_seed

ORIGIN_USER = "user"


class RuleStore:
    def __init__(self, db: Any, clock: Callable[[], float] = time.time):
        self._db = db
        self._clock = clock

    def user_rules(self) -> Dict[str, Rule]:
        rows = self._db.query("SELECT rule_json FROM risk_rules WHERE origin = ?", (ORIGIN_USER,))
        rules = [Rule.from_dict(json.loads(r[0])) for r in rows]
        return {r.id: r for r in rules}

    def save(self, rule: Rule) -> None:
        """Validates through Rule.from_dict, so a malformed edit never reaches the table."""
        Rule.from_dict(rule.to_dict())
        self._db.execute(
            "INSERT INTO risk_rules(rule_id, rule_json, origin, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(rule_id) DO UPDATE SET rule_json = excluded.rule_json, "
            "origin = excluded.origin, updated_at = excluded.updated_at",
            (rule.id, json.dumps(rule.to_dict(), sort_keys=True), ORIGIN_USER, self._clock()))

    def restore_default(self, rule_id: str) -> None:
        self._db.execute("DELETE FROM risk_rules WHERE rule_id = ? AND origin = ?", (rule_id, ORIGIN_USER))

    def restore_all(self) -> None:
        self._db.execute("DELETE FROM risk_rules WHERE origin = ?", (ORIGIN_USER,))

    def ruleset(self) -> RuleSet:
        return RuleSet(load_seed(), self.user_rules())

    def edited_ids(self) -> List[str]:
        return sorted(self.user_rules())
