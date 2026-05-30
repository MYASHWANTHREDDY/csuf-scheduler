#!/usr/bin/env python
"""
Restore the scheduler database from a backup file.
Usage: python scripts/restore_database.py BACKUP_FILE [--force]
"""
import sys
import os
import subprocess
from pathlib import Path
import argparse

sys.path.insert(0, '.')

def restore_database(backup_file, force=False):
    """Restore PostgreSQL database from a backup file."""
    
    backup_path = Path(backup_file)
    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_file}")
        return False
    
    # Get connection details from environment
    db_host = os.getenv('POSTGRES_HOST', 'localhost')
    db_port = os.getenv('POSTGRES_PORT', '5432')
    db_user = os.getenv('POSTGRES_USER', 'csuf')
    db_name = os.getenv('POSTGRES_DB', 'scheduler')
    db_password = os.getenv('POSTGRES_PASSWORD', 'csufpass')
    
    # Confirm with user (unless --force)
    if not force:
        print("⚠️  WARNING: This will OVERWRITE all current data in the database!")
        print(f"   Database: {db_name}")
        print(f"   Backup file: {backup_path.name}")
        response = input("\nType 'yes' to confirm restore: ")
        if response.lower() != 'yes':
            print("❌ Restore cancelled.")
            return False
    
    # Set password in environment for pg_restore
    env = os.environ.copy()
    env['PGPASSWORD'] = db_password
    
    print(f"\n🔄 Restoring database from: {backup_path.name}")
    
    try:
        # Use pg_restore to restore the database
        cmd = [
            'pg_restore',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-d', db_name,
            '-c',  # Drop objects before recreating (clean)
            '-v',  # Verbose
            str(backup_path)
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Restore failed!")
            print(f"Error: {result.stderr}")
            return False
        
        print(f"✅ Restore complete!")
        print(f"   All data has been restored from: {backup_path.name}")
        print(f"   Database: {db_name}")
        return True
        
    except FileNotFoundError:
        print("❌ Error: pg_restore not found. Please install PostgreSQL client tools.")
        print("   On Windows: Install PostgreSQL and add bin folder to PATH")
        print("   Or use: choco install postgresql --force --forceX86")
        return False
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False


def list_backups():
    """List all available backups."""
    backups_dir = Path('backups')
    if not backups_dir.exists():
        print("No backups found yet.")
        return []
    
    backups = sorted(backups_dir.glob('scheduler_*.sql.gz'), reverse=True)
    if not backups:
        print("No backups found.")
        return []
    
    print("\n📋 Available backups:")
    for i, backup in enumerate(backups[:10], 1):
        size_mb = backup.stat().st_size / (1024 * 1024)
        print(f"  {i}. {backup.name} ({size_mb:.2f} MB)")
    
    return backups


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Restore the scheduler database from a backup')
    parser.add_argument('backup', nargs='?', help='Backup file path (can be filename or full path)')
    parser.add_argument('--force', '-f', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--list', '-l', action='store_true', help='List available backups')
    
    args = parser.parse_args()
    
    if args.list or not args.backup:
        backups = list_backups()
        if args.list or not args.backup:
            sys.exit(0)
    
    # If backup is just a filename, look in backups directory
    backup_file = args.backup
    if not Path(backup_file).exists() and '/' not in backup_file and '\\' not in backup_file:
        backups_dir = Path('backups')
        possible_path = backups_dir / backup_file
        if possible_path.exists():
            backup_file = str(possible_path)
        else:
            # Try to find most recent matching backup
            matching = list(backups_dir.glob(f'scheduler_*{backup_file}*.sql.gz'))
            if matching:
                backup_file = str(sorted(matching, reverse=True)[0])
    
    success = restore_database(backup_file, force=args.force)
    sys.exit(0 if success else 1)
