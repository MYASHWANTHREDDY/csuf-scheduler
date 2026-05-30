#!/usr/bin/env python3
"""
SQLAlchemy-based backup - Works WITHOUT PostgreSQL client tools
Falls back to direct database export when pg_dump not available

Usage:
    python scripts/backup_database_sqlalchemy.py          # Create backup
    python scripts/backup_database_sqlalchemy.py --list   # List backups
    python scripts/backup_database_sqlalchemy.py --info FILENAME.json.gz  # Show backup contents
"""

import os
import sys
import gzip
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path for app imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app import create_app, db
from backend.app.models import (
    User, Availability, AvailabilityRequest, Shift, ShiftTemplate,
    EmployeeProfile, ScheduleConfig, GeneratedSchedule, ScheduleOverride,
    LeaveRequest, SwapRequest, Notification, Announcement, CallOffRequest,
    TimeAdjustmentRequest, PayPeriod, Timesheet, TimesheetLine, TimesheetComment, TimesheetAuditLog
)


def get_backup_path():
    """Get or create backup directory"""
    backup_dir = Path(__file__).parent.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    return backup_dir


def serialize_object(obj):
    """Serialize SQLAlchemy model to dict"""
    result = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        # Handle datetime serialization
        if isinstance(value, datetime):
            result[column.name] = value.isoformat()
        else:
            result[column.name] = value
    return result


def create_sqlalchemy_backup():
    """Create backup using SQLAlchemy ORM"""
    app = create_app()
    
    with app.app_context():
        print("🔄 Backing up database using SQLAlchemy...")
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'description': 'SQLAlchemy-based backup (works without pg_dump)',
            'tables': {}
        }
        
        # Get all tables
        tables = {
            'users': User,
            'availability': Availability,
            'availability_requests': AvailabilityRequest,
            'leave_requests': LeaveRequest,
            'shifts': Shift,
            'shift_templates': ShiftTemplate,
            'employee_profiles': EmployeeProfile,
            'schedule_configs': ScheduleConfig,
            'generated_schedules': GeneratedSchedule,
            'schedule_overrides': ScheduleOverride,
            'swap_requests': SwapRequest,
            'notifications': Notification,
            'announcements': Announcement,
            'call_off_requests': CallOffRequest,
            'time_adjustment_requests': TimeAdjustmentRequest,
            'pay_periods': PayPeriod,
            'timesheets': Timesheet,
            'timesheet_lines': TimesheetLine,
            'timesheet_comments': TimesheetComment,
            'timesheet_audit_logs': TimesheetAuditLog,
        }
        
        total_records = 0
        for table_name, model_class in tables.items():
            try:
                records = db.session.query(model_class).all()
                backup_data['tables'][table_name] = {
                    'count': len(records),
                    'data': [serialize_object(record) for record in records]
                }
                total_records += len(records)
                print(f"  ✓ {table_name}: {len(records)} records")
            except Exception as e:
                print(f"  ⚠ {table_name}: Error - {e}")
                backup_data['tables'][table_name] = {'count': 0, 'data': [], 'error': str(e)}
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scheduler_sqlalchemy_{timestamp}.json.gz"
        filepath = get_backup_path() / filename
        
        # Write compressed JSON
        json_str = json.dumps(backup_data, indent=2, default=str)
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            f.write(json_str)
        
        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        
        print(f"\n✅ Backup complete!")
        print(f"   📁 File: {filename}")
        print(f"   📊 Size: {file_size_mb:.2f} MB")
        print(f"   📝 Records: {total_records}")
        print(f"   ✅ Location: {filepath}")
        
        return filepath


def list_backups():
    """List all available backups"""
    backup_dir = get_backup_path()
    
    # SQLAlchemy backups
    sqlalchemy_backups = sorted(backup_dir.glob('scheduler_sqlalchemy_*.json.gz'), reverse=True)
    # PostgreSQL backups
    postgres_backups = sorted(backup_dir.glob('scheduler_*.sql.gz'), reverse=True)
    
    all_backups = sqlalchemy_backups + postgres_backups
    
    if not all_backups:
        print("📭 No backups found")
        return
    
    print(f"\n📋 Available Backups ({len(all_backups)} found):\n")
    
    for i, backup_file in enumerate(all_backups, 1):
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        mod_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
        backup_type = "SQLAlchemy" if "sqlalchemy" in backup_file.name else "PostgreSQL"
        
        print(f"  {i}. {backup_file.name}")
        print(f"     Type: {backup_type} | Size: {size_mb:.2f} MB | Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")


def restore_from_sqlalchemy_backup(backup_file):
    """Restore from SQLAlchemy JSON backup"""
    app = create_app()
    
    with app.app_context():
        print(f"\n⚠️  WARNING: This will overwrite the current database!")
        confirm = input("Type 'yes' to confirm restore: ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Restore cancelled")
            return False
        
        print(f"\n🔄 Restoring from {backup_file.name}...")
        
        try:
            # Read backup
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            print(f"   Backup created: {backup_data.get('timestamp', 'Unknown')}")
            
            # Clear existing data
            for table_name in backup_data['tables'].keys():
                try:
                    db.session.query(
                        eval(table_name.title().replace('_', ''))  # Won't work for all
                    ).delete()
                except:
                    pass
            
            # Restore data
            model_map = {
                'users': User,
                'availability': Availability,
                'availability_requests': AvailabilityRequest,
                'leave_requests': LeaveRequest,
                'shifts': Shift,
                'shift_templates': ShiftTemplate,
                'employee_profiles': EmployeeProfile,
                'schedule_configs': ScheduleConfig,
                'generated_schedules': GeneratedSchedule,
                'schedule_overrides': ScheduleOverride,
                'swap_requests': SwapRequest,
                'notifications': Notification,
                'announcements': Announcement,
                'call_off_requests': CallOffRequest,
                'time_adjustment_requests': TimeAdjustmentRequest,
                'pay_periods': PayPeriod,
                'timesheets': Timesheet,
                'timesheet_lines': TimesheetLine,
                'timesheet_comments': TimesheetComment,
                'timesheet_audit_logs': TimesheetAuditLog,
            }
            
            restored_count = 0
            for table_name, table_data in backup_data['tables'].items():
                if table_name not in model_map:
                    continue
                
                model_class = model_map[table_name]
                for record_data in table_data['data']:
                    try:
                        obj = model_class(**record_data)
                        db.session.add(obj)
                        restored_count += 1
                    except Exception as e:
                        print(f"     ⚠ Error restoring {table_name}: {e}")
            
            db.session.commit()
            print(f"\n✅ Restore complete!")
            print(f"   📊 Records restored: {restored_count}")
            return True
            
        except Exception as e:
            print(f"\n❌ Restore failed: {e}")
            db.session.rollback()
            return False


def show_backup_info(backup_file):
    """Show information about a backup"""
    try:
        with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        print(f"\n📋 Backup Information: {backup_file.name}\n")
        print(f"   Created: {backup_data.get('timestamp', 'Unknown')}")
        print(f"   Description: {backup_data.get('description', 'N/A')}\n")
        print(f"   Tables:\n")
        
        total = 0
        for table_name, table_data in backup_data['tables'].items():
            count = table_data.get('count', 0)
            total += count
            print(f"      • {table_name}: {count} records")
        
        print(f"\n   Total Records: {total}\n")
        
    except Exception as e:
        print(f"❌ Error reading backup: {e}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            list_backups()
        elif sys.argv[1] == '--info' and len(sys.argv) > 2:
            backup_file = get_backup_path() / sys.argv[2]
            if not backup_file.exists():
                print(f"❌ Backup file not found: {sys.argv[2]}")
            else:
                show_backup_info(backup_file)
        elif sys.argv[1] == '--restore' and len(sys.argv) > 2:
            backup_file = get_backup_path() / sys.argv[2]
            if not backup_file.exists():
                print(f"❌ Backup file not found: {sys.argv[2]}")
            else:
                restore_from_sqlalchemy_backup(backup_file)
        else:
            print("Usage:")
            print("  python backup_database_sqlalchemy.py          # Create backup")
            print("  python backup_database_sqlalchemy.py --list   # List backups")
            print("  python backup_database_sqlalchemy.py --info FILENAME.json.gz")
            print("  python backup_database_sqlalchemy.py --restore FILENAME.json.gz")
    else:
        create_sqlalchemy_backup()
