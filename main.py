#!/usr/bin/env python3
"""
FastF1 Flask API Server - Live F1 Timing Data
Provides REST API endpoints for Android app to consume
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import fastf1
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for Android app

# Enable FastF1 cache
fastf1.Cache.enable_cache(False)

# Global variables to store session data
current_session = None
session_data = {
    'positions': [],
    'track_status': [],
    'fastest_laps': [],
    'pit_stops': [],
    'race_control_messages': [],
    'last_update': None,
    'is_live': False
}

def load_session(year, event_name, session_type='R'):
    """Load a specific F1 session"""
    global current_session, session_data
    
    try:
        print(f"Loading session: {year} {event_name} {session_type}")
        session = fastf1.get_session(year, event_name, session_type)
        session.load()
        current_session = session
        
        # Update session data
        update_session_data()
        return True
    except Exception as e:
        print(f"Error loading session: {e}")
        return False

def update_session_data():
    """Update all session data"""
    global current_session, session_data
    
    if current_session is None:
        return
    
    try:
        # Get positions
        results = current_session.results
        session_data['positions'] = [
            {
                'position': int(row['Position']),
                'driver': row['Abbreviation'],
                'full_name': row['FullName'],
                'team': row['TeamName'],
                'number': int(row['DriverNumber']),
                'grid_position': int(row['GridPosition']) if 'GridPosition' in row else None,
                'status': row['Status']
            }
            for _, row in results.iterrows()
        ]
        
        # Get track status
        if hasattr(current_session, 'track_status'):
            track_status = current_session.track_status
            status_changes = track_status[track_status['Status'] != '1'].copy()
            
            status_names = {
                '1': 'Green Flag',
                '2': 'Yellow Flag',
                '4': 'Safety Car',
                '5': 'Red Flag',
                '6': 'Virtual Safety Car',
                '7': 'VSC Ending'
            }
            
            session_data['track_status'] = [
                {
                    'time': str(row['Time']),
                    'status': status_names.get(str(row['Status']), 'Unknown'),
                    'status_code': str(row['Status'])
                }
                for _, row in status_changes.iterrows()
            ]
        
        # Get fastest laps
        laps = current_session.laps
        fastest = laps.loc[laps['LapTime'].notna()].sort_values('LapTime').head(10)
        
        session_data['fastest_laps'] = [
            {
                'driver': row['Driver'],
                'team': row['Team'],
                'lap_number': int(row['LapNumber']),
                'lap_time': str(row['LapTime']),
                'lap_time_seconds': row['LapTime'].total_seconds()
            }
            for _, row in fastest.iterrows()
        ]
        
        # Get pit stops
        pit_stops = laps[laps['PitInTime'].notna()].copy()
        session_data['pit_stops'] = [
            {
                'driver': row['Driver'],
                'team': row['Team'],
                'lap_number': int(row['LapNumber']),
                'pit_duration': str(row['PitOutTime'] - row['PitInTime']) if 'PitOutTime' in row else None
            }
            for _, row in pit_stops.iterrows()
        ]
        
        # Get race control messages
        if hasattr(current_session, 'race_control_messages'):
            messages = current_session.race_control_messages
            session_data['race_control_messages'] = [
                {
                    'time': str(row['Time']),
                    'message': row['Message'],
                    'category': row.get('Category', 'Other')
                }
                for _, row in messages.iterrows()
            ]
        
        session_data['last_update'] = datetime.now().isoformat()
        
    except Exception as e:
        print(f"Error updating session data: {e}")

# ==================== API ENDPOINTS ====================

@app.route('/')
def home():
    """API documentation"""
    return jsonify({
        'message': 'FastF1 Live Timing API',
        'version': '1.0',
        'endpoints': {
            '/api/session/load': 'POST - Load a session (year, event, session_type)',
            '/api/positions': 'GET - Get current positions',
            '/api/top3': 'GET - Get top 3 positions',
            '/api/track-status': 'GET - Get track status/flags',
            '/api/fastest-laps': 'GET - Get fastest laps',
            '/api/pit-stops': 'GET - Get pit stops',
            '/api/race-control': 'GET - Get race control messages',
            '/api/full-data': 'GET - Get all data at once',
            '/api/status': 'GET - Get API status'
        }
    })

@app.route('/api/session/load', methods=['POST'])
def load_session_endpoint():
    """Load a specific session"""
    data = request.json
    year = data.get('year', 2024)
    event = data.get('event', 'Abu Dhabi')
    session_type = data.get('session_type', 'R')
    
    success = load_session(year, event, session_type)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Session loaded: {year} {event} {session_type}',
            'data': session_data
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to load session'
        }), 500

@app.route('/api/positions')
def get_positions():
    """Get all driver positions"""
    return jsonify({
        'success': True,
        'data': session_data['positions'],
        'last_update': session_data['last_update']
    })

@app.route('/api/top3')
def get_top3():
    """Get top 3 positions"""
    top3 = session_data['positions'][:3] if len(session_data['positions']) >= 3 else session_data['positions']
    return jsonify({
        'success': True,
        'data': top3,
        'last_update': session_data['last_update']
    })

@app.route('/api/track-status')
def get_track_status():
    """Get track status and flags"""
    return jsonify({
        'success': True,
        'data': session_data['track_status'],
        'last_update': session_data['last_update']
    })

@app.route('/api/fastest-laps')
def get_fastest_laps():
    """Get fastest laps"""
    limit = request.args.get('limit', 5, type=int)
    return jsonify({
        'success': True,
        'data': session_data['fastest_laps'][:limit],
        'last_update': session_data['last_update']
    })

@app.route('/api/pit-stops')
def get_pit_stops():
    """Get pit stops"""
    return jsonify({
        'success': True,
        'data': session_data['pit_stops'],
        'last_update': session_data['last_update']
    })

@app.route('/api/race-control')
def get_race_control():
    """Get race control messages"""
    limit = request.args.get('limit', 10, type=int)
    return jsonify({
        'success': True,
        'data': session_data['race_control_messages'][:limit],
        'last_update': session_data['last_update']
    })

@app.route('/api/full-data')
def get_full_data():
    """Get all data at once"""
    return jsonify({
        'success': True,
        'data': session_data,
        'last_update': session_data['last_update']
    })

@app.route('/api/status')
def get_status():
    """Get API status"""
    return jsonify({
        'success': True,
        'status': 'running',
        'session_loaded': current_session is not None,
        'last_update': session_data['last_update'],
        'is_live': session_data['is_live']
    })

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Manually refresh session data"""
    if current_session is None:
        return jsonify({
            'success': False,
            'message': 'No session loaded'
        }), 400
    
    update_session_data()
    return jsonify({
        'success': True,
        'message': 'Data refreshed',
        'last_update': session_data['last_update']
    })

# ==================== STARTUP ====================

if __name__ == '__main__':
    print("=" * 60)
    print("FastF1 Flask API Server Starting...")
    print("=" * 60)
    
    # Load default session (Abu Dhabi 2024 Race)
    print("\nLoading default session: 2024 Abu Dhabi Race")
    load_session(2024, 'Abu Dhabi', 'R')
    
    print("\n" + "=" * 60)
    print("Server ready!")
    print("API running at: http://localhost:5000")
    print("=" * 60)
    print("\nAvailable endpoints:")
    print("  GET  /api/positions       - All driver positions")
    print("  GET  /api/top3            - Top 3 positions")
    print("  GET  /api/track-status    - Track status/flags")
    print("  GET  /api/fastest-laps    - Fastest laps")
    print("  GET  /api/pit-stops       - Pit stops")
    print("  GET  /api/race-control    - Race control messages")
    print("  GET  /api/full-data       - All data at once")
    print("  POST /api/session/load    - Load different session")
    print("  POST /api/refresh         - Refresh data")
    print("=" * 60 + "\n")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
