#!/bin/bash
# Automatisches Backup-System für Todo-App

# Konfiguration
BACKUP_DIR="/home/ubuntu/backups"
DB_PATH="/home/ubuntu/todo-app/instance/todos.db"
S3_BUCKET="your-todo-app-backups"  # Optional: S3 für Cloud-Backup
RETENTION_DAYS=30

# Backup-Verzeichnis erstellen
mkdir -p $BACKUP_DIR

# Timestamp für Backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/todos_$TIMESTAMP.db"

# SQLite Backup (sicher auch während Schreibvorgängen)
sqlite3 $DB_PATH ".backup $BACKUP_FILE"

# Komprimierung für Speicherplatz
gzip $BACKUP_FILE

# Alte Backups löschen (älter als RETENTION_DAYS)
find $BACKUP_DIR -name "todos_*.db.gz" -mtime +$RETENTION_DAYS -delete

# Optional: Upload zu AWS S3
# aws s3 cp $BACKUP_FILE.gz s3://$S3_BUCKET/backups/

# Log-Eintrag
echo "$(date): Backup erstellt: $BACKUP_FILE.gz" >> /var/log/todo-backup.log

# Backup-Status prüfen
if [ -f "$BACKUP_FILE.gz" ]; then
    echo "✅ Backup erfolgreich: $BACKUP_FILE.gz"
    exit 0
else
    echo "❌ Backup fehlgeschlagen!"
    exit 1
fi
