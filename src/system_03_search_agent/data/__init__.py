"""The user-data store: schema, engine, and session factory for `search_agent_users`.

Depends on:
    - Environment variable: USER_DB_URL (read-write connection to the
      search_agent_users PostgreSQL database)

Reads:
    - Environment variable: USER_DB_URL

Writes:
    - Nothing at import time. Schema changes are owned exclusively by the
      Alembic migrations under alembic/versions/.

This package never imports, references, or connects to the knowledge-graph
database or its read-only role. The user-data instance and the graph
instance share no connection pool, credential, or schema namespace
(Technical_specification.md Section 15).
"""

from system_03_search_agent.data.base import Base, get_engine, get_user_db_url

__all__ = ["Base", "get_engine", "get_user_db_url"]
