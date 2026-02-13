#!/usr/bin/env python3
"""
Extract outage logs for FranklinWH BETA testing report.

Extracts logs from the network outage event and exports to CSV.
Focuses on connection failures, timeouts, and recovery events.
"""

import sqlite3
import csv
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Determine outage timeframe
# User mentioned outage "since 3am" and recovery around 9:44 AM AEDT (user's local time)
# That's approximately 3am to 10am local time today

def extract_outage_logs(db_path: str, output_csv: str, hours_back: int = 12):
    """Extract logs related to network outage and export to CSV."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Database schema: id, timestamp, level, source, message, metadata
    # Get logs from last N hours, focusing on errors and connection issues
    query = """
    SELECT 
        datetime(timestamp, 'unixepoch', 'localtime') as local_time,
        datetime(timestamp, 'unixepoch') as utc_time,
        timestamp,
        level,
        source,
        message,
        metadata
    FROM logs
    WHERE timestamp >= strftime('%s', 'now', '-' || ? || ' hours')
    ORDER BY timestamp ASC
    """
    
    cursor.execute(query, (hours_back,))
    all_logs = cursor.fetchall()
    
    # Also get specific error logs
    error_query = """
    SELECT 
        datetime(timestamp, 'unixepoch', 'localtime') as local_time,
        datetime(timestamp, 'unixepoch') as utc_time,
        timestamp,
        level,
        source,
        message,
        metadata
    FROM logs
    WHERE 
        level IN ('ERROR', 'WARNING', 'CRITICAL')
        AND timestamp >= strftime('%s', 'now', '-' || ? || ' hours')
    ORDER BY timestamp ASC
    """
    
    cursor.execute(error_query, (hours_back,))
    error_logs = cursor.fetchall()
    
    # Get connection-related logs
    connection_query = """
    SELECT 
        datetime(timestamp, 'unixepoch', 'localtime') as local_time,
        datetime(timestamp, 'unixepoch') as utc_time,
        timestamp,
        level,
        source,
        message,
        metadata
    FROM logs
    WHERE 
        (message LIKE '%broken%pipe%' 
         OR message LIKE '%connection%' 
         OR message LIKE '%timeout%'
         OR message LIKE '%reconnect%'
         OR message LIKE '%failed%'
         OR message LIKE '%network%'
         OR message LIKE '%modbus%')
        AND timestamp >= strftime('%s', 'now', '-' || ? || ' hours')
    ORDER BY timestamp ASC
    """
    
    cursor.execute(connection_query, (hours_back,))
    connection_logs = cursor.fetchall()
    
    # Write to CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'Local Time (AEDT)', 
            'UTC Time', 
            'Unix Timestamp',
            'Level', 
            'Source', 
            'Message', 
            'Metadata'
        ])
        
        # Use connection logs (most relevant)
        for row in connection_logs:
            writer.writerow(row)
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"OUTAGE LOG EXTRACTION SUMMARY")
    print(f"{'='*80}")
    print(f"Database: {db_path}")
    print(f"Time Range: Last {hours_back} hours")
    print(f"Total Logs: {len(all_logs)}")
    print(f"Error/Warning Logs: {len(error_logs)}")
    print(f"Connection-Related Logs: {len(connection_logs)}")
    print(f"Output CSV: {output_csv}")
    print(f"{'='*80}\n")
    
    # Analyze outage timeline
    if connection_logs:
        print("TIMELINE ANALYSIS:")
        print(f"First connection log: {connection_logs[0][0]}")
        print(f"Last connection log: {connection_logs[-1][0]}")
        print()
        
        # Count error types
        broken_pipe_count = sum(1 for log in connection_logs if 'broken' in log[5].lower() and 'pipe' in log[5].lower())
        timeout_count = sum(1 for log in connection_logs if 'timeout' in log[5].lower())
        failed_count = sum(1 for log in connection_logs if 'failed' in log[5].lower())
        reconnect_count = sum(1 for log in connection_logs if 'reconnect' in log[5].lower())
        
        print(f"Error Breakdown:")
        print(f"  'Broken pipe' errors: {broken_pipe_count}")
        print(f"  Timeout errors: {timeout_count}")
        print(f"  Failed operations: {failed_count}")
        print(f"  Reconnection attempts: {reconnect_count}")
        print()
        
        # Show first and last few errors
        print("FIRST 5 CONNECTION LOGS:")
        for log in connection_logs[:5]:
            print(f"  [{log[0]}] {log[3]}: {log[5][:100]}")
        
        print("\nLAST 5 CONNECTION LOGS:")
        for log in connection_logs[-5:]:
            print(f"  [{log[0]}] {log[3]}: {log[5][:100]}")
    
    conn.close()
    return len(connection_logs)


if __name__ == "__main__":
    db_path = "data/logs.db"
    output_csv = "outage_logs_export.csv"
    hours_back = 12  # Last 12 hours to cover 3am to now
    
    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)
    
    count = extract_outage_logs(db_path, output_csv, hours_back)
    
    print(f"\n✅ Extracted {count} connection-related logs to {output_csv}")
    print(f"\nThis CSV is ready for your FranklinWH BETA testing report.")
    print(f"\nNote: Multiple Modbus TCP clients were connected during this period:")
    print(f"  - This monitoring application")
    print(f"  - Home Assistant")
    print(f"  - Homey home automation")
