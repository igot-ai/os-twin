<#
.SYNOPSIS
    Exports trace/event/metric data from JSONL files into a SQLite database.

.DESCRIPTION
    Reads trace.jsonl and channel.jsonl files and inserts them into a
    queryable SQLite database for analysis, dashboards, and historical reports.

    Creates tables: events, spans, metrics, messages

    Part of Epic 5 — Enhanced Observability.

.PARAMETER LogDir
    Path to the log directory containing trace.jsonl.
.PARAMETER WarRoomsDir
    Path to war-rooms (scans all room-*/channel.jsonl).
.PARAMETER OutputDb
    Path to the SQLite database file. Default: <LogDir>/ostwin.db
.PARAMETER Append
    Append to existing DB. Default: recreate.

.EXAMPLE
    ./Export-ToSqlite.ps1 -LogDir "./logs" -WarRoomsDir "./war-rooms"
    ./Export-ToSqlite.ps1 -LogDir "./logs" -OutputDb "./analysis.db" -Append
#>
[CmdletBinding()]
param(
    [string]$LogDir = '',
    [string]$WarRoomsDir = '',
    [string]$OutputDb = '',
    [switch]$Append
)

# --- Resolve paths ---
$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..") -ErrorAction SilentlyContinue).Path

if (-not $LogDir) {
    $LogDir = if ($env:AGENT_OS_LOG_DIR) { $env:AGENT_OS_LOG_DIR }
              else { Join-Path $agentsDir "logs" }
}

if (-not $WarRoomsDir) {
    $WarRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
                   else { Join-Path $agentsDir "war-rooms" }
}

if (-not $OutputDb) {
    $OutputDb = Join-Path $LogDir "ostwin.db"
}

# Ensure output directory exists
$outputDir = Split-Path $OutputDb
if ($outputDir -and -not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

# --- Check for Python + sqlite3 ---
$python = if (Test-Path (Join-Path $agentsDir ".venv" "bin" "python")) {
    (Join-Path $agentsDir ".venv" "bin" "python")
} else { "python3" }

# --- Generate Python SQLite import script ---
$pythonScript = @"
import json
import sqlite3
import sys
import os
from datetime import datetime

db_path = sys.argv[1]
log_dir = sys.argv[2]
warrooms_dir = sys.argv[3]
append = sys.argv[4] == 'true'

if not append and os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create tables
cur.executescript('''
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    level TEXT,
    message TEXT,
    trace_id TEXT,
    span_id TEXT,
    properties TEXT,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    name TEXT,
    status TEXT,
    duration_ms REAL,
    attributes TEXT,
    event_count INTEGER,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    name TEXT,
    value REAL,
    type TEXT,
    labels TEXT,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id TEXT,
    ts TEXT,
    from_role TEXT,
    to_role TEXT,
    type TEXT,
    ref TEXT,
    body TEXT,
    room_id TEXT,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT UNIQUE,
    task_ref TEXT,
    status TEXT,
    retries INTEGER,
    goals_total INTEGER,
    goals_met INTEGER,
    config TEXT,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_level ON events(level);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
''')

imported = {'events': 0, 'spans': 0, 'metrics': 0, 'messages': 0, 'rooms': 0}

# Import trace.jsonl events
trace_file = os.path.join(log_dir, 'trace.jsonl')
if os.path.exists(trace_file):
    with open(trace_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                props = {k: v for k, v in d.items()
                         if k not in ('ts', 'level', 'message', 'trace_id', 'span_id')}
                cur.execute(
                    'INSERT INTO events (ts, level, message, trace_id, span_id, properties) VALUES (?,?,?,?,?,?)',
                    (d.get('ts'), d.get('level'), d.get('message'),
                     d.get('trace_id', ''), d.get('span_id', ''),
                     json.dumps(props) if props else None)
                )
                imported['events'] += 1
            except Exception:
                pass

# Import trace report JSON files (for spans)
if os.path.exists(log_dir):
    for fname in os.listdir(log_dir):
        if fname.startswith('trace-') and fname.endswith('.json'):
            fpath = os.path.join(log_dir, fname)
            try:
                with open(fpath) as f:
                    report = json.load(f)
                for span in report.get('spans', []):
                    cur.execute(
                        'INSERT INTO spans (trace_id, span_id, parent_span_id, name, status, duration_ms, attributes, event_count) VALUES (?,?,?,?,?,?,?,?)',
                        (report.get('trace_id'), span.get('span_id'), span.get('parent_span_id'),
                         span.get('name'), span.get('status'), span.get('duration_ms'),
                         json.dumps(span.get('attributes', {})),
                         span.get('event_count', 0))
                    )
                    imported['spans'] += 1
            except Exception:
                pass

# Import war-room channels and configs
if os.path.exists(warrooms_dir):
    for room_name in sorted(os.listdir(warrooms_dir)):
        room_path = os.path.join(warrooms_dir, room_name)
        if not os.path.isdir(room_path) or not room_name.startswith('room-'):
            continue

        # Channel messages
        channel_file = os.path.join(room_path, 'channel.jsonl')
        if os.path.exists(channel_file):
            with open(channel_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        m = json.loads(line)
                        cur.execute(
                            'INSERT INTO messages (msg_id, ts, from_role, to_role, type, ref, body, room_id) VALUES (?,?,?,?,?,?,?,?)',
                            (m.get('id'), m.get('ts'), m.get('from'), m.get('to'),
                             m.get('type'), m.get('ref'), m.get('body'), room_name)
                        )
                        imported['messages'] += 1
                    except Exception:
                        pass

        # Room config + status
        config_file = os.path.join(room_path, 'config.json')
        status_file = os.path.join(room_path, 'status')
        retries_file = os.path.join(room_path, 'retries')
        goal_file = os.path.join(room_path, 'goal-verification.json')

        task_ref = ''
        status = 'unknown'
        retries = 0
        goals_total = 0
        goals_met = 0
        config_json = None

        if os.path.exists(config_file):
            try:
                with open(config_file) as f:
                    cfg = json.load(f)
                task_ref = cfg.get('task_ref', '')
                config_json = json.dumps(cfg)
                goals_total = len(cfg.get('goals', {}).get('definition_of_done', []))
            except Exception:
                pass

        if os.path.exists(status_file):
            status = open(status_file).read().strip()
        if os.path.exists(retries_file):
            try:
                retries = int(open(retries_file).read().strip())
            except Exception:
                pass
        if os.path.exists(goal_file):
            try:
                with open(goal_file) as f:
                    gv = json.load(f)
                goals_met = gv.get('summary', {}).get('goals_met', 0)
            except Exception:
                pass

        cur.execute(
            'INSERT OR REPLACE INTO rooms (room_id, task_ref, status, retries, goals_total, goals_met, config) VALUES (?,?,?,?,?,?,?)',
            (room_name, task_ref, status, retries, goals_total, goals_met, config_json)
        )
        imported['rooms'] += 1

conn.commit()
conn.close()

print(json.dumps({
    'database': db_path,
    'imported': imported,
    'tables': ['events', 'spans', 'metrics', 'messages', 'rooms']
}))
"@

# --- Execute ---
$scriptFile = Join-Path $env:TMPDIR "ostwin-sqlite-export.py"
if (-not $env:TMPDIR) { $scriptFile = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-sqlite-export.py" }
$pythonScript | Out-File -FilePath $scriptFile -Encoding utf8

$appendFlag = if ($Append) { "true" } else { "false" }

try {
    $output = & $python $scriptFile $OutputDb $LogDir $WarRoomsDir $appendFlag 2>&1
    $result = $output | ConvertFrom-Json

    Write-Host ""
    Write-Host "[EXPORT] SQLite database: $($result.database)" -ForegroundColor Green
    Write-Host "  Events:   $($result.imported.events)"
    Write-Host "  Spans:    $($result.imported.spans)"
    Write-Host "  Messages: $($result.imported.messages)"
    Write-Host "  Rooms:    $($result.imported.rooms)"
    Write-Host "  Tables:   $($result.tables -join ', ')"
    Write-Host ""

    Write-Output $result
}
catch {
    Write-Error "SQLite export failed: $_"
    exit 1
}
finally {
    Remove-Item $scriptFile -Force -ErrorAction SilentlyContinue
}
