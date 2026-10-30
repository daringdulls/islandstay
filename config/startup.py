"""Prepare the database when a serverless instance starts (Vercel has no start script).

Runs once per cold start: applies pending migrations, loads the island guides into an empty database and
creates the admin account from ADMIN_EMAIL / ADMIN_PASSWORD. It is cheap when there is nothing to do, and a
Postgres advisory lock stops two instances starting at the same moment from migrating together.
Set AUTO_SETUP=0 to switch it off.
"""
import logging
import os

log = logging.getLogger(__name__)
LOCK_ID = 7_401_960  # any constant; identifies this app's setup lock


def pending_migrations():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def run():
    if os.environ.get("AUTO_SETUP", "1") != "1":
        return
    from django.core.management import call_command
    from django.db import connection

    try:
        is_pg = connection.vendor == "postgresql"
        if is_pg:
            with connection.cursor() as c:
                c.execute("SELECT pg_advisory_lock(%s)", [LOCK_ID])
        try:
            if pending_migrations():
                log.info("Applying database migrations")
                call_command("migrate", interactive=False, verbosity=1)
            call_command("seed_maldives", if_empty=True, verbosity=0)
            call_command("ensure_admin", verbosity=0)
        finally:
            if is_pg:
                with connection.cursor() as c:
                    c.execute("SELECT pg_advisory_unlock(%s)", [LOCK_ID])
    except Exception:  # never stop the site from starting; the error is in the logs
        log.exception("Automatic database setup failed")
