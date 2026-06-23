"""Execute a .sql file against a Fabric Warehouse using an AAD access token (service
principal). sqlcmd -G cannot do SP auth; pyodbc + SQL_COPT_SS_ACCESS_TOKEN can.
Splits the script on `GO` batch separators (pyodbc executes one batch at a time)."""

import os
import re
import struct
import sys

import pyodbc

SQL_COPT_SS_ACCESS_TOKEN = 1256  # ODBC attribute for AAD access token

server = os.environ["SQL_SERVER"]
database = os.environ["SQL_DATABASE"]
sql_file = os.environ["SQL_FILE"]
token = os.environ["SQL_ACCESS_TOKEN"]

# Token must be UTF-16-LE, length-prefixed (ODBC access-token struct)
tb = token.encode("utf-16-le")
token_struct = struct.pack(f"<I{len(tb)}s", len(tb), tb)

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={server};DATABASE={database};"
    "Encrypt=yes;TrustServerCertificate=no;"
)

print(f"Connecting to {server} / {database} ...", file=sys.stderr)
cnxn = pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
cnxn.autocommit = True
cur = cnxn.cursor()

with open(sql_file, "r", encoding="utf-8") as fh:
    content = fh.read()

batches = re.split(r"(?im)^\s*GO\s*$", content)
executed = 0
for i, raw in enumerate(batches):
    stmt = raw.strip()
    if not stmt:
        continue
    try:
        cur.execute(stmt)
        while True:
            if cur.description:
                for row in cur.fetchall():
                    print("  result:", tuple(row), file=sys.stderr)
            if not cur.nextset():
                break
        executed += 1
    except Exception as exc:  # noqa: BLE001 — surface the exact SQL that failed
        print(f"[batch {i}] ERROR: {exc}", file=sys.stderr)
        print("---- failing batch ----", file=sys.stderr)
        print(stmt[:800], file=sys.stderr)
        sys.exit(1)

print(f"Executed {executed} batch(es) successfully.", file=sys.stderr)
