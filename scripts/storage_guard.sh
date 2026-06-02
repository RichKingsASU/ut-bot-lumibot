#!/usr/bin/env bash
# =============================================================================
# storage_guard.sh — Self-healing tick-storage drive guard
# =============================================================================
# Detects unmounted/broken tick-storage drive (UUID=267ED1667ED12F75),
# remounts by UUID via fstab, restarts affected Docker containers, and sends
# Telegram alerts on state transitions only (deduped). Safe to run every 2 min.
#
# Design: state-aware, idempotent, alert-deduped, zero-dependency except bash+curl
# Mount rule: ALWAYS by UUID via fstab. NEVER by device node. NEVER fsck/repair.
# =============================================================================

# Strict mode — but we handle non-zero exits explicitly for health checks
set -uo pipefail

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
MOUNT_POINT="/mnt/tick-storage"
DRIVE_UUID="267ED1667ED12F75"
PROJECT_DIR="/home/k2/ut-bot-lumibot"
ENV_FILE="${PROJECT_DIR}/.env"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"
# Services that bind-mount tick-storage (verified against docker-compose.yml)
BIND_MOUNTED_SERVICES="questdb qdrant"
# Sentinel check: these dirs must exist inside the mount to confirm correct volume
SENTINEL_PARENT="${MOUNT_POINT}/historical"
SENTINEL_SUBDIRS="crypto equities"

# State and log file paths — prefer /var/lib and /var/log, fallback to project
if [[ -w /var/lib ]] || mkdir -p /var/lib/storage_guard 2>/dev/null; then
    STATE_DIR="/var/lib/storage_guard"
else
    STATE_DIR="${PROJECT_DIR}/logs"
    mkdir -p "${STATE_DIR}"
fi
STATE_FILE="${STATE_DIR}/state"

if [[ -w /var/log ]]; then
    LOG_FILE="/var/log/storage_guard.log"
else
    LOG_FILE="${PROJECT_DIR}/logs/storage_guard.log"
    mkdir -p "$(dirname "${LOG_FILE}")"
fi

# Lock file — prefer /run (tmpfs), fallback to /tmp
LOCK_FILE="/run/storage_guard.lock"
[[ -w /run ]] || LOCK_FILE="/tmp/storage_guard.lock"

# Alert dedup: re-alert a persisting FAILED state at most once per 30 minutes
FAILED_ALERT_INTERVAL_SEC=1800
# Write test file path
WRITE_TEST_FILE="${MOUNT_POINT}/.storage_guard_write_test"

# ---------------------------------------------------------------------------
# SENTINEL OVERRIDE for unit-testing (set GUARD_TARGET=/tmp/fake env var)
# ---------------------------------------------------------------------------
if [[ -n "${GUARD_TARGET:-}" ]]; then
    MOUNT_POINT="${GUARD_TARGET}"
    SENTINEL_PARENT="${MOUNT_POINT}/historical"
    WRITE_TEST_FILE="${MOUNT_POINT}/.storage_guard_write_test"
fi

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
HOSTNAME_SHORT="$(hostname -s)"
NOW_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

log() {
    local level="$1"
    shift
    echo "[${NOW_UTC}] [${level}] $*" | tee -a "${LOG_FILE}"
}

# Load TELEGRAM_BOT_TOKEN from .env (pure bash, no source — avoid polluting env)
load_telegram_token() {
    local token=""
    if [[ -f "${ENV_FILE}" ]]; then
        token=$(grep -m1 '^TELEGRAM_BOT_TOKEN=' "${ENV_FILE}" | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d '[:space:]')
    fi
    echo "${token}"
}

send_telegram() {
    local message="$1"
    local token
    token=$(load_telegram_token)
    if [[ -z "${token}" ]]; then
        log "ERROR" "TELEGRAM_BOT_TOKEN not found in ${ENV_FILE} — cannot alert"
        return 1
    fi
    # Prefix every message with host + UTC timestamp for self-contained phone view
    local full_msg="${HOSTNAME_SHORT} | ${NOW_UTC}
${message}"
    /usr/bin/curl -s --max-time 15 \
        -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d chat_id="8641189809" \
        --data-urlencode "text=${full_msg}" \
        > /dev/null 2>&1
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        log "WARN" "curl to Telegram returned non-zero: ${rc}"
    fi
    return $rc
}

# Read state file → outputs: STATE LAST_ALERT_TS (tab-separated)
read_state() {
    if [[ -f "${STATE_FILE}" ]]; then
        cat "${STATE_FILE}"
    else
        printf "UNKNOWN\t0"
    fi
}

write_state() {
    local new_state="$1"
    local alert_ts="${2:-$(date -u +%s)}"
    printf '%s\t%s\n' "${new_state}" "${alert_ts}" > "${STATE_FILE}"
}

# ---------------------------------------------------------------------------
# A) CONCURRENCY LOCK
# ---------------------------------------------------------------------------
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    # Another instance is running — exit silently
    exit 0
fi

# ---------------------------------------------------------------------------
# READ CURRENT STATE
# ---------------------------------------------------------------------------
state_line="$(read_state)"
PREV_STATE="$(echo "${state_line}" | awk '{print $1}')"
LAST_ALERT_TS="$(echo "${state_line}" | awk '{print $2}')"
NOW_EPOCH="$(date -u +%s)"

# ---------------------------------------------------------------------------
# TEST-ALERT FLAG (--test-alert): sends one alert via the real curl path, exits
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--test-alert" ]]; then
    log "INFO" "--test-alert flag: sending test Telegram message"
    send_telegram "🧪 storage_guard alert path test — curl+token+network confirmed OK"
    log "INFO" "Test alert sent (check Telegram chat 8641189809)"
    exit 0
fi

# ---------------------------------------------------------------------------
# C) HEALTH CHECK (three layers)
# ---------------------------------------------------------------------------
HEALTH_PASS=0  # 0=unknown, 1=pass, 2=fail

check_health() {
    # Layer 1: Is it mounted?
    if ! /bin/mountpoint -q "${MOUNT_POINT}" 2>/dev/null; then
        log "DEBUG" "Layer 1 FAIL: ${MOUNT_POINT} not mounted"
        return 1
    fi

    # Layer 2: Sentinel — correct volume with expected structure?
    local sentinel_ok=1
    if [[ ! -d "${SENTINEL_PARENT}" ]]; then
        log "DEBUG" "Layer 2 FAIL: sentinel dir ${SENTINEL_PARENT} missing"
        return 1
    fi
    for subdir in ${SENTINEL_SUBDIRS}; do
        if [[ ! -d "${SENTINEL_PARENT}/${subdir}" ]]; then
            log "DEBUG" "Layer 2 FAIL: sentinel subdir ${SENTINEL_PARENT}/${subdir} missing"
            return 1
        fi
    done

    # Layer 3: Write test (confirms not remounted read-only after I/O errors)
    local write_ok=0
    if /usr/bin/timeout 10 /bin/bash -c "echo ok > '${WRITE_TEST_FILE}' && /bin/rm -f '${WRITE_TEST_FILE}'" 2>/dev/null; then
        write_ok=1
    fi
    if [[ $write_ok -eq 0 ]]; then
        log "DEBUG" "Layer 3 FAIL: write test failed on ${MOUNT_POINT}"
        /bin/rm -f "${WRITE_TEST_FILE}" 2>/dev/null || true
        return 1
    fi

    return 0  # All three layers pass
}

# Run the health check
if check_health; then
    # ---------- HEALTHY PATH ----------
    if [[ "${PREV_STATE}" == "DOWN" || "${PREV_STATE}" == "FAILED" || "${PREV_STATE}" == "RECOVERED" ]]; then
        # Transition from a bad/recovering state back to healthy — log prominently
        log "INFO" "STATE: HEALTHY (was ${PREV_STATE}) — no action needed"
    else
        # Normal healthy run — single terse line
        log "INFO" "STATE: HEALTHY — mounted, sentinel OK, write OK — no action"
    fi
    write_state "HEALTHY" "${NOW_EPOCH}"
    exit 0
fi

# ---------------------------------------------------------------------------
# D) DEVICE PRESENCE CHECK (health failed — is drive even visible?)
# ---------------------------------------------------------------------------
DEVICE_VISIBLE=0
# Use lsblk (doesn't need root, reads kernel sysfs) to check for our UUID
if /bin/lsblk -o UUID 2>/dev/null | /bin/grep -qi "${DRIVE_UUID}"; then
    DEVICE_VISIBLE=1
else
    # Also try blkid (may need cached data)
    if /sbin/blkid 2>/dev/null | /bin/grep -qi "${DRIVE_UUID}"; then
        DEVICE_VISIBLE=1
    fi
fi

if [[ $DEVICE_VISIBLE -eq 0 ]]; then
    # Hardware/cable/power drop — drive not even visible to kernel
    log "ERROR" "STATE: FAILED — device UUID=${DRIVE_UUID} NOT detected by kernel (cable/power/enclosure?)"
    # Dedup: only alert if new FAILED state or if 30min interval elapsed
    SECONDS_SINCE_ALERT=$(( NOW_EPOCH - LAST_ALERT_TS ))
    if [[ "${PREV_STATE}" != "FAILED" || $SECONDS_SINCE_ALERT -ge $FAILED_ALERT_INTERVAL_SEC ]]; then
        send_telegram "🔴 tick-storage DEVICE NOT DETECTED
UUID=${DRIVE_UUID} is not visible to the kernel.
Cable/enclosure/power failure suspected.
Drive is physically absent — NO mount attempt possible.
Manual intervention required. Do NOT repair — just reconnect."
        log "INFO" "ALERT sent: device not detected"
        write_state "FAILED" "${NOW_EPOCH}"
    else
        log "INFO" "FAILED state persists (${SECONDS_SINCE_ALERT}s since last alert — deduped)"
        write_state "FAILED" "${LAST_ALERT_TS}"
    fi
    exit 1
fi

# ---------------------------------------------------------------------------
# E) RECOVERY SEQUENCE (device visible but not healthy/mounted)
# ---------------------------------------------------------------------------
log "INFO" "STATE: DOWN — UUID=${DRIVE_UUID} visible but ${MOUNT_POINT} unhealthy — attempting recovery"

# E1: Alert on DOWN transition (deduped)
if [[ "${PREV_STATE}" != "DOWN" && "${PREV_STATE}" != "FAILED" ]]; then
    send_telegram "⚠️ tick-storage DOWN
Drive detected (UUID=${DRIVE_UUID}) but not healthy at ${MOUNT_POINT}.
Attempting auto-remount now..."
    log "INFO" "ALERT sent: DOWN transition detected"
fi
write_state "DOWN" "${NOW_EPOCH}"

# E2: udevadm settle — let kernel catch up to re-enumeration
log "INFO" "Running udevadm settle (max 5s)..."
/bin/udevadm settle --timeout=5 2>/dev/null || true

# E3: Attempt mount by UUID via fstab (fstab maps UUID → mountpoint)
log "INFO" "Attempting mount via fstab: mount ${MOUNT_POINT}"
MOUNT_OUTPUT=""
MOUNT_RC=0

# Primary: fstab-based mount (resolves UUID automatically)
MOUNT_OUTPUT=$( /usr/bin/timeout 30 /bin/mount "${MOUNT_POINT}" 2>&1 ) || MOUNT_RC=$?

if [[ $MOUNT_RC -ne 0 ]]; then
    # Fallback: explicit UUID mount (belt-and-suspenders)
    log "WARN" "fstab mount failed (rc=${MOUNT_RC}), trying explicit UUID mount..."
    MOUNT_RC=0
    MOUNT_OUTPUT=$( /usr/bin/timeout 30 /bin/mount -U "${DRIVE_UUID}" "${MOUNT_POINT}" 2>&1 ) || MOUNT_RC=$?
fi

# E4: If mount failed — alert and STOP (no fsck, no retry-loop)
if [[ $MOUNT_RC -ne 0 ]]; then
    log "ERROR" "Mount FAILED (rc=${MOUNT_RC}): ${MOUNT_OUTPUT}"
    CURRENT_DEVICE=$( /bin/lsblk -o NAME,UUID 2>/dev/null | /bin/grep -i "${DRIVE_UUID}" | awk '{print $1}' || echo "unknown" )
    send_telegram "🔴 tick-storage AUTO-REMOUNT FAILED
Mount error (rc=${MOUNT_RC}): ${MOUNT_OUTPUT}
Drive UUID=${DRIVE_UUID} (device: ${CURRENT_DEVICE:-unknown}) is visible but mount rejected.
Likely: loose cable, flapping connection, or filesystem error.
NOT attempting repair (risk of data destruction).
Manual intervention required: check cable, then: sudo mount /mnt/tick-storage"
    log "INFO" "ALERT sent: remount failed"
    write_state "FAILED" "${NOW_EPOCH}"
    exit 1
fi

log "INFO" "Mount command succeeded — running post-mount health verification..."

# E5: Post-mount health re-check (verify sentinel + write before declaring victory)
sleep 2  # Brief settle after mount
if ! check_health; then
    log "ERROR" "Mount succeeded but post-mount health check FAILED (wrong volume or read-only?)"
    send_telegram "🔴 tick-storage MOUNTED BUT UNHEALTHY
Mount appeared to succeed but sentinel/write checks still fail.
Possible: wrong volume, read-only remount, or filesystem corruption.
Containers NOT restarted — manual inspection required.
Check: ls ${SENTINEL_PARENT}"
    log "INFO" "ALERT sent: mounted but health still failing"
    write_state "FAILED" "${NOW_EPOCH}"
    exit 1
fi

log "INFO" "Post-mount health verified — proceeding to container restart"

# E6: Restart bind-mounted containers to clear stale file handles
RESTART_OUTPUT=""
RESTART_RC=0
log "INFO" "Restarting bind-mounted containers: ${BIND_MOUNTED_SERVICES}"
RESTART_OUTPUT=$( cd "${PROJECT_DIR}" && /usr/bin/docker compose restart ${BIND_MOUNTED_SERVICES} 2>&1 ) || RESTART_RC=$?

if [[ $RESTART_RC -ne 0 ]]; then
    log "WARN" "Container restart returned rc=${RESTART_RC}: ${RESTART_OUTPUT}"
fi

# Wait for containers to settle
log "INFO" "Waiting 15s for containers to settle..."
sleep 15

# Check container logs for errno=5 / "No such file" errors post-restart
CONTAINER_ERRORS=""
for svc in ${BIND_MOUNTED_SERVICES}; do
    SVC_LOGS=$( cd "${PROJECT_DIR}" && /usr/bin/docker compose logs --tail=30 "${svc}" 2>&1 )
    if echo "${SVC_LOGS}" | /bin/grep -qiE 'errno=5|no such file|EIO|Input.output error'; then
        CONTAINER_ERRORS="${CONTAINER_ERRORS}  ⚠️ ${svc}: stale handle errors still present in logs\n"
        log "WARN" "${svc} still shows I/O errors after restart"
    else
        log "INFO" "${svc} logs clean after restart"
    fi
done

# E7: Mark RECOVERED, send success alert
CURRENT_DEVICE=$( /bin/lsblk -o NAME,UUID,MOUNTPOINT 2>/dev/null | /bin/grep -i "${DRIVE_UUID}" | awk '{print $1}' || echo "unknown" )
DF_LINE=$( /bin/df -h "${MOUNT_POINT}" 2>/dev/null | tail -1 || echo "(df failed)" )

RECOVERY_MSG="✅ tick-storage RECOVERED
Remounted by UUID via fstab ✓
Containers restarted: ${BIND_MOUNTED_SERVICES} ✓
Current device node: /dev/${CURRENT_DEVICE:-unknown} (may differ from last time)
${DF_LINE}"

if [[ -n "${CONTAINER_ERRORS}" ]]; then
    RECOVERY_MSG="${RECOVERY_MSG}
WARNINGS (manual check recommended):
${CONTAINER_ERRORS}"
fi

log "INFO" "STATE: RECOVERED — sending alert"
send_telegram "${RECOVERY_MSG}"
write_state "RECOVERED" "${NOW_EPOCH}"
log "INFO" "Recovery complete. Containers: ${BIND_MOUNTED_SERVICES}"
exit 0
