#!/usr/bin/env python
"""
Backup the scheduler database to a compressed file.
Usage: python scripts/backup_database.py [--output BACKUP_FILE]
"""
import sys
import os
import subprocess
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '.')

def backup_database(output_file=None):
    """Backup PostgreSQL database to a SQL dump file."""
    
    # Default output: backups/scheduler_YYYYMMDD_HHMMSS.sql.gz
    if not output_file:
        backups_dir = Path('backups')
        backups_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = backups_dir / f'scheduler_{timestamp}.sql.gz'
    
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Get connection details from environment
    db_host = os.getenv('POSTGRES_HOST', 'localhost')
    db_port = os.getenv('POSTGRES_PORT', '5432')
    db_user = os.getenv('POSTGRES_USER', 'csuf')
    db_name = os.getenv('POSTGRES_DB', 'scheduler')
    db_password = os.getenv('POSTGRES_PASSWORD', 'csufpass')
    
    # Set password in environment for pg_dump
    env = os.environ.copy()
    env['PGPASSWORD'] = db_password
    
    print(f"🔄 Backing up database: {db_name}")
    print(f"📁 Output file: {output_file}")
    
    try:
        # Use pg_dump to backup the entire database
        cmd = [
            'pg_dump',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-Fc',  # Custom format (more compact)
            '-b',   # Include blobs
            '-v',   # Verbose
            db_name
        ]
        
        # Pipe through gzip for compression
        with open(output_file, 'wb') as f:
            dump_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            gzip_proc = subprocess.Popen(['gzip'], stdin=dump_proc.stdout, stdout=f, stderr=subprocess.PIPE)
            dump_proc.stdout.close()
            
            _, err = gzip_proc.communicate()
            dump_proc.wait()
            
            if gzip_proc.returncode != 0:
                print(f"❌ Backup failed: {err.decode()}")
                return False
        
        size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"✅ Backup complete! File size: {size_mb:.2f} MB")
        print(f"   Location: {output_file.absolute()}")
        return True
        
    except FileNotFoundError:
        print("❌ Error: pg_dump not found. Please install PostgreSQL client tools.")
        print("   On Windows: Install PostgreSQL and add bin folder to PATH")
        print("   Or use: choco install postgresql --force --forceX86")
        return False
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def list_backups():
    """List all available backups."""
    backups_dir = Path('backups')
    if not backups_dir.exists():
        print("No backups found yet.")
        return
    
    backups = sorted(backups_dir.glob('scheduler_*.sql.gz'), reverse=True)
    if not backups:
        print("No backups found.")
        return
    
    print("\n📋 Available backups:")
    for i, backup in enumerate(backups[:10], 1):  # Show last 10
        size_mb = backup.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"  {i}. {backup.name} ({size_mb:.2f} MB) - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(backups) > 10:
        print(f"  ... and {len(backups) - 10} more")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Backup the scheduler database')
    parser.add_argument('--output', '-o', help='Output backup file path')
    parser.add_argument('--list', '-l', action='store_true', help='List available backups')
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
    else:
        success = backup_database(args.output)
        sys.exit(0 if success else 1)
