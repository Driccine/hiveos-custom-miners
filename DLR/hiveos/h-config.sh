#!/usr/bin/env bash
# Hive sources this file.
dlr_write_config() {
    local account="${CUSTOM_TEMPLATE:-}" rig="${WORKER_NAME:-rig1}" temporary
    if [[ $account =~ ^[[:xdigit:]]{64}$ ]]; then
        account="$account.$rig"
    fi
    if [[ ! $account =~ ^[[:xdigit:]]{64}\.[a-zA-Z0-9_-]{1,32}$ ]]; then
        echo "DLR: indique un compte Ting public de 64 caractères hexadécimaux suivi de .worker." >&2
        return 1
    fi
    temporary=$(mktemp "${CUSTOM_CONFIG_FILENAME}.XXXXXX") || return 1
    if ! printf '%s\n' "$account" > "$temporary" || ! mv -f -- "$temporary" "$CUSTOM_CONFIG_FILENAME"; then
        rm -f -- "$temporary"
        return 1
    fi
}
dlr_write_config
