#!/bin/sh
# Print the dev Neo4j password from backend/.env, generating a random one the
# first time (or when it is still the old public default).
#
#   scripts/neo4j-password.sh          print it (generate if needed)
#   scripts/neo4j-password.sh rotate   make the running dev Neo4j use it: no-op
#                                      when it already does, swaps it in when the
#                                      volume still has the old default, and
#                                      fails loudly otherwise
set -eu
env_file="${ENV_FILE:-backend/.env}"
old_default="explorator_dev"
key_re='^[[:space:]]*(export[[:space:]]+)?NEO4J_PASSWORD[[:space:]]*='

touch "$env_file"
# Last assignment wins, as in python-dotenv. Unquoted values lose a trailing
# " # comment"; surrounding quotes and CR are dropped.
pw=$(grep -E "$key_re" "$env_file" | tail -n 1 | sed -E "s/$key_re[[:space:]]*//" | tr -d '\r' \
    | sed -E -e 's/^"(.*)".*/\1/' -e t -e "s/^'(.*)'.*/\1/" -e t \
        -e 's/[[:space:]]+#.*$//' -e 's/[[:space:]]*$//')

if [ -z "$pw" ] || [ "$pw" = "$old_default" ]; then
    pw=$(od -An -N18 -tx1 /dev/urandom | tr -d ' \n')
    if grep -qE "$key_re" "$env_file"; then
        sed -E -i.bak "s/$key_re.*/NEO4J_PASSWORD=$pw/" "$env_file" && rm -f "$env_file.bak"
    else
        [ -s "$env_file" ] && [ -n "$(tail -c 1 "$env_file")" ] && echo >> "$env_file"
        echo "NEO4J_PASSWORD=$pw" >> "$env_file"
    fi
    echo "neo4j-password: generated a new Neo4j password in $env_file" >&2
fi

if [ "${1:-}" != "rotate" ]; then
    printf '%s' "$pw"
    exit 0
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -qx neo4j; then
    echo "neo4j-password: the dev Neo4j isn't running; nothing to rotate" >&2
    exit 0
fi

# Already on the configured password? (The container's NEO4J_AUTH is the value
# compose took from $env_file; reading it there keeps the password out of argv.)
if docker compose exec -T neo4j sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" "RETURN 1"' \
    >/dev/null 2>&1; then
    exit 0
fi

# A volume created before passwords were generated still has the old default;
# NEO4J_AUTH only applies to a fresh volume. Swap it in place (data is kept).
# The new password goes over stdin, not argv.
if printf "ALTER CURRENT USER SET PASSWORD FROM '%s' TO '%s';\n" "$old_default" "$pw" \
    | docker compose exec -T neo4j cypher-shell -u neo4j -p "$old_default" -d system \
    >/dev/null 2>&1; then
    echo "neo4j-password: changed the dev Neo4j password from the old default" >&2
    exit 0
fi

cat >&2 <<EOF
neo4j-password: ERROR: the dev Neo4j accepts neither NEO4J_PASSWORD from $env_file
nor the old default, so the backend would fall back to in-memory mode.
This happens when $env_file was replaced (e.g. re-copied from .env.example)
after the password was generated. To fix it, either:
  - put the previous NEO4J_PASSWORD back into $env_file (check backups such
    as $env_file.bak*), then run this again; or
  - reset the password in the database (data is kept), see
    https://neo4j.com/docs/operations-manual/5/authentication-authorization/password-and-user-recovery/
EOF
exit 1
