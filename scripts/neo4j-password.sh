#!/bin/sh
# Print the dev Neo4j password from backend/.env, generating a random one the
# first time (or when it is still the old public default).
#
#   scripts/neo4j-password.sh          print it (generate if needed)
#   scripts/neo4j-password.sh rotate   change a running dev Neo4j that still
#                                      uses the old default to this password
set -eu
env_file="${ENV_FILE:-backend/.env}"
old_default="explorator_dev"

touch "$env_file"
pw=$(sed -n 's/^NEO4J_PASSWORD=//p' "$env_file" | tail -n 1 | tr -d "\"'\r")

if [ -z "$pw" ] || [ "$pw" = "$old_default" ]; then
    pw=$(od -An -N18 -tx1 /dev/urandom | tr -d ' \n')
    if grep -q '^NEO4J_PASSWORD=' "$env_file"; then
        sed -i.bak "s/^NEO4J_PASSWORD=.*/NEO4J_PASSWORD=$pw/" "$env_file" && rm -f "$env_file.bak"
    else
        [ -s "$env_file" ] && [ -n "$(tail -c 1 "$env_file")" ] && echo >> "$env_file"
        echo "NEO4J_PASSWORD=$pw" >> "$env_file"
    fi
    echo "neo4j-password: generated a new Neo4j password in $env_file" >&2
fi

if [ "${1:-}" = "rotate" ]; then
    # A volume created before passwords were generated still has the old
    # default; NEO4J_AUTH only applies to a fresh volume. Swap it in place.
    if docker compose exec -T neo4j cypher-shell -u neo4j -p "$old_default" -d system \
        "ALTER CURRENT USER SET PASSWORD FROM '$old_default' TO '$pw'" >/dev/null 2>&1; then
        echo "neo4j-password: changed the dev Neo4j password from the old default" >&2
    fi
    exit 0
fi

printf '%s' "$pw"
