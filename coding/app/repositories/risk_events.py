import sqlite3
from pathlib import Path
from typing import Any


class RiskEventRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists risk_events (
                    id integer primary key autoincrement,
                    message_text text not null,
                    source_group text not null,
                    sender_name text not null,
                    risk_score real not null,
                    model_version text not null,
                    decision text,
                    reviewer text
                )
                """
            )

    def create_event(self, **payload: object) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                insert into risk_events(message_text, source_group, sender_name, risk_score, model_version)
                values (:message_text, :source_group, :sender_name, :risk_score, :model_version)
                """,
                payload,
            )
            return int(cursor.lastrowid)

    def record_decision(self, event_id: int, decision: str, reviewer: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update risk_events
                set decision = ?, reviewer = ?
                where id = ?
                """,
                (decision, reviewer, event_id),
            )

    def get_event(self, event_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                select id, message_text, source_group, sender_name, risk_score, model_version, decision, reviewer
                from risk_events
                where id = ?
                """,
                (event_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Risk event {event_id} not found")

        return dict(row)
