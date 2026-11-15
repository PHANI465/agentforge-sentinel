"""Apply migrations and grant only the demo runtime role. No credentials are printed."""
import os
import secrets
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from sentinel import db
from sentinel.db.roles import grant_runtime

ROLE = "sentinel_hosted"


def main() -> None:
    owner = os.environ["SENTINEL_HOSTED_OPERATOR_URL"]
    parts = urlsplit(owner)
    password = secrets.token_urlsafe(32)
    db.migrate(owner)
    grant_runtime(owner, ROLE, password)
    with db.connect(owner) as conn:
        conn.execute(Path(__file__).with_name("guest.sql").read_text(encoding="utf-8"))
    hostname = parts.netloc.rsplit("@", 1)[1]
    runtime = urlunsplit(parts._replace(netloc=f"{ROLE}:{quote(password, safe='')}@{hostname}"))
    with db.connect(runtime) as conn:
        row = conn.execute(
            "SELECT current_user, has_table_privilege('api_sessions','INSERT') AS can_insert,"
            " has_function_privilege('sentinel_demo.issue_session(text,uuid,uuid,uuid)',"
            " 'EXECUTE') AS can_issue"
        ).fetchone()
        if row["current_user"] != ROLE or row["can_insert"] or not row["can_issue"]:
            raise RuntimeError("Unexpected runtime role grants")
    # The caller must supply a private file outside the deployment package.
    path = Path(os.environ["SENTINEL_HOSTED_RUNTIME_FILE"])
    with path.open("x", encoding="utf-8") as out:
        out.write(runtime)
    print("Migrations, scoped guest issuance and runtime role verified.")


if __name__ == "__main__":
    main()
