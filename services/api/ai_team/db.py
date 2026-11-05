from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from . import (  # noqa: F401 - register additive tables
    issue_models,
    memory_models,  # noqa: F401 - register additive tables
)
from .config import Settings
from .models import Base


class Database:
    def __init__(self, settings: Settings):
        sqlite = settings.database_url.startswith("sqlite:")
        if sqlite and ":memory:" not in settings.database_url:
            Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(
                parents=True, exist_ok=True
            )
        self.engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False, "timeout": 15} if sqlite else {},
            pool_pre_ping=True,
            **({} if sqlite else {"pool_size": 5, "max_overflow": 5}),
        )
        if sqlite:

            @event.listens_for(self.engine, "connect")
            def set_pragmas(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")
        else:
            self.engine = self.engine.execution_options(schema_translate_map={None: "ai_team"})

    def initialize(self):
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as connection:
                connection.execute(text("CREATE SCHEMA IF NOT EXISTS ai_team"))
                connection.execute(text("REVOKE ALL ON SCHEMA ai_team FROM PUBLIC"))
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        with Session(self.engine, expire_on_commit=False) as session:
            yield session
