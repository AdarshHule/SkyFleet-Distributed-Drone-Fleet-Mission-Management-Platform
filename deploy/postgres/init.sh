#!/bin/bash
set -euo pipefail
run() { psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" "$@"; }

run -d "$POSTGRES_DB" -f /schemas/telemetry.sql
for db in skyfleet_test skyfleet_command skyfleet_command_test; do
  run -d "$POSTGRES_DB" -c "CREATE DATABASE $db"
done
run -d skyfleet_test -f /schemas/telemetry.sql
run -d skyfleet_command -f /schemas/command.sql
run -d skyfleet_command_test -f /schemas/command.sql