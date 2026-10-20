#!/usr/bin/env bash
set -euo pipefail

# PostgreSQL Backup Script for BotBinance
# Usage: ./backup_db.sh [--s3] [--retention-days N]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
USE_S3=false
S3_BUCKET=""
S3_ENDPOINT=""
DB_CONTAINER="botbinance-db"
DB_NAME="binance_bot"
DB_USER="bot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --s3                    Upload backup to S3-compatible storage
  --bucket BUCKET         S3 bucket name (required with --s3)
  --endpoint ENDPOINT     S3 endpoint URL (for MinIO, DigitalOcean Spaces, etc.)
  --retention-days N      Retention period in days (default: 30)
  --container NAME        Docker container name for PostgreSQL (default: botbinance-db)
  -h, --help              Show this help

Environment variables (can be set in .env):
  POSTGRES_PASSWORD       Database password
  AWS_ACCESS_KEY_ID       S3 access key
  AWS_SECRET_ACCESS_KEY   S3 secret key
  S3_BUCKET               S3 bucket name
  S3_ENDPOINT             S3 endpoint URL
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --s3) USE_S3=true; shift ;;
        --bucket) S3_BUCKET="$2"; shift 2 ;;
        --endpoint) S3_ENDPOINT="$2"; shift 2 ;;
        --retention-days) RETENTION_DAYS="$2"; shift 2 ;;
        --container) DB_CONTAINER="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) log_error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Load .env if exists
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Override with env vars if set
S3_BUCKET="${S3_BUCKET:-$S3_BUCKET}"
S3_ENDPOINT="${S3_ENDPOINT:-$S3_ENDPOINT}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"

if [[ -z "$POSTGRES_PASSWORD" ]]; then
    log_error "POSTGRES_PASSWORD not set in .env or environment"
    exit 1
fi

if [[ "$USE_S3" == true && -z "$S3_BUCKET" ]]; then
    log_error "--s3 requires --bucket or S3_BUCKET env var"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="${BACKUP_DIR}/binance_bot_${DATE}.sql.gz"
log_info "Starting backup to $BACKUP_FILE"

# Create backup using docker exec
if ! docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges | gzip > "$BACKUP_FILE"; then
    log_error "pg_dump failed"
    rm -f "$BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_info "Backup completed: $BACKUP_FILE ($BACKUP_SIZE)"

# Upload to S3 if requested
if [[ "$USE_S3" == true ]]; then
    log_info "Uploading to S3 bucket: $S3_BUCKET"
    
    S3_CMD="aws s3 cp"
    if [[ -n "$S3_ENDPOINT" ]]; then
        S3_CMD="$S3_CMD --endpoint-url $S3_ENDPOINT"
    fi
    
    if ! $S3_CMD "$BACKUP_FILE" "s3://${S3_BUCKET}/binance_bot_${DATE}.sql.gz"; then
        log_error "S3 upload failed"
        exit 1
    fi
    log_info "S3 upload completed"
fi

# Cleanup old local backups
log_info "Cleaning up backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name "binance_bot_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete

# Cleanup old S3 backups if using S3
if [[ "$USE_S3" == true ]]; then
    log_info "Cleaning up S3 backups older than $RETENTION_DAYS days"
    # Note: Requires lifecycle policy on bucket for automatic cleanup
    # This is a manual cleanup using aws cli
    CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y-%m-%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y-%m-%d 2>/dev/null)
    if [[ -n "$CUTOFF_DATE" ]]; then
        aws s3 ls "s3://${S3_BUCKET}/" | while read -r line; do
            FILE_DATE=$(echo "$line" | awk '{print $1}')
            FILE_NAME=$(echo "$line" | awk '{print $4}')
            if [[ "$FILE_DATE" < "$CUTOFF_DATE" && "$FILE_NAME" == binance_bot_*.sql.gz ]]; then
                aws s3 rm "s3://${S3_BUCKET}/${FILE_NAME}"
                log_info "Deleted old S3 backup: $FILE_NAME"
            fi
        done
    fi
fi

log_info "Backup process completed successfully"