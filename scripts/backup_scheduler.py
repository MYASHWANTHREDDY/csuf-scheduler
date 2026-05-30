#!/usr/bin/env python
"""
Automated backup scheduler using APScheduler.
Backs up the database at regular intervals and cleans up old backups.

Usage: python scripts/backup_scheduler.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

sys.path.insert(0, '.')

from apscheduler.schedulers.blocking import BlockingScheduler
from scripts.backup_database import backup_database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BACKUP_DIR = Path('backups')
RETENTION_DAYS = 30  # Keep backups for this many days
MAX_BACKUPS = 50     # Keep at most this many backups


def perform_backup():
    """Perform a backup and cleanup old ones."""
    try:
        logger.info("Starting scheduled backup...")
        success = backup_database()
        if success:
            cleanup_old_backups()
            logger.info("Scheduled backup completed successfully")
        else:
            logger.error("Scheduled backup failed")
    except Exception as e:
        logger.error(f"Error during scheduled backup: {e}")


def cleanup_old_backups():
    """Remove backups older than RETENTION_DAYS or if more than MAX_BACKUPS exist."""
    if not BACKUP_DIR.exists():
        return
    
    backups = sorted(BACKUP_DIR.glob('scheduler_*.sql.gz'), key=lambda p: p.stat().st_mtime)
    
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    
    for backup in backups:
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        
        # Delete if older than retention period
        if mtime < cutoff_date:
            try:
                backup.unlink()
                deleted_count += 1
                logger.info(f"Deleted old backup: {backup.name}")
            except Exception as e:
                logger.error(f"Failed to delete {backup.name}: {e}")
        
        # Delete excess backups (keep only MAX_BACKUPS)
        elif len(backups) - deleted_count > MAX_BACKUPS:
            try:
                backup.unlink()
                deleted_count += 1
                logger.info(f"Deleted excess backup: {backup.name}")
            except Exception as e:
                logger.error(f"Failed to delete {backup.name}: {e}")
    
    if deleted_count > 0:
        logger.info(f"Cleanup complete: deleted {deleted_count} old backup(s)")


def main():
    """Start the backup scheduler."""
    
    # Check if APScheduler is available
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        print("❌ APScheduler not installed")
        print("   Install with: pip install apscheduler")
        sys.exit(1)
    
    scheduler = BlockingScheduler()
    
    # Schedule backup every 6 hours
    scheduler.add_job(
        perform_backup,
        'interval',
        hours=6,
        id='database_backup',
        name='Database Backup',
        misfire_grace_time=600
    )
    
    # Also run at startup
    print("\n" + "=" * 80)
    print("AUTOMATED BACKUP SCHEDULER")
    print("=" * 80)
    print(f"📅 Schedule: Every 6 hours")
    print(f"📁 Backup directory: {BACKUP_DIR.absolute()}")
    print(f"🗑️  Retention: {RETENTION_DAYS} days / {MAX_BACKUPS} backups max")
    print("=" * 80)
    print("\nStarting scheduler... (Ctrl+C to stop)")
    print()
    
    perform_backup()  # Run immediately
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n\n✅ Scheduler stopped.")


if __name__ == '__main__':
    main()
