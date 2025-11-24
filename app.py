from flask import Flask, jsonify, render_template, request
import subprocess
import json
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env()

OCTOPUS_API_KEY = os.getenv('OCTOPUS_API_KEY', '')
ACCOUNT_NUMBER = os.getenv('OCTOPUS_ACCOUNT_NUMBER', '')

DB_PATH = 'energy.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS consumption
                 (fuel_type TEXT,
                  interval_start TEXT,
                  interval_end TEXT,
                  consumption REAL,
                  updated_at TEXT,
                  PRIMARY KEY (fuel_type, interval_start))''')
    conn.commit()
    conn.close()

def curl_get(url, auth=None):
    """Use curl instead of requests"""
    cmd = ['curl', '-s', '--max-time', '30']
    if auth:
        cmd.extend(['-u', f'{auth[0]}:'])
    cmd.append(url)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"curl failed: {result.stderr}")
    return json.loads(result.stdout)

class OctopusREST:
    BASE_URL = 'https://api.octopus.energy/v1'
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.auth = (api_key, '')
        self.account_data = None
    
    def get_account_info(self, account_number):
        url = f'{self.BASE_URL}/accounts/{account_number}/'
        self.account_data = curl_get(url, auth=self.auth)
        return self.account_data
    
    def get_electricity_consumption(self, mpan, serial, period_from, period_to):
        url = f'{self.BASE_URL}/electricity-meter-points/{mpan}/meters/{serial}/consumption/'
        url += f'?period_from={period_from}&period_to={period_to}&page_size=1500&order_by=period'
        data = curl_get(url, auth=self.auth)
        return data['results']
    
    def get_gas_consumption(self, mprn, serial, period_from, period_to):
        url = f'{self.BASE_URL}/gas-meter-points/{mprn}/meters/{serial}/consumption/'
        url += f'?period_from={period_from}&period_to={period_to}&page_size=1500&order_by=period'
        data = curl_get(url, auth=self.auth)
        return data['results']

def store_consumption(fuel_type, readings):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for reading in readings:
        c.execute('''INSERT OR REPLACE INTO consumption 
                     (fuel_type, interval_start, interval_end, consumption, updated_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (fuel_type, 
                   reading['interval_start'],
                   reading['interval_end'],
                   reading['consumption'],
                   datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return '''
    <html>
    <head><title>Energy Monitor</title></head>
    <body>
        <h1>Energy Monitor</h1>
        <p><a href="/api/account-info">View Account Info</a></p>
        <p><a href="/api/fetch-data">Fetch Latest Data</a></p>
        <p><a href="/api/consumption/electricity?days=7">View Electricity (7 days)</a></p>
        <p><a href="/api/consumption/gas?days=7">View Gas (7 days)</a></p>
        <p><a href="/api/stats">View Stats</a></p>
    </body>
    </html>
    '''

@app.route('/api/account-info')
def account_info():
    if not OCTOPUS_API_KEY or not ACCOUNT_NUMBER:
        return jsonify({'error': 'API key or account number not configured'}), 500
    
    try:
        client = OctopusREST(OCTOPUS_API_KEY)
        data = client.get_account_info(ACCOUNT_NUMBER)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fetch-data')
def fetch_latest_data():
    if not OCTOPUS_API_KEY or not ACCOUNT_NUMBER:
        return jsonify({'error': 'API key or account number not configured'}), 500
    
    try:
        client = OctopusREST(OCTOPUS_API_KEY)
        account = client.get_account_info(ACCOUNT_NUMBER)
        
        period_to = datetime.utcnow().isoformat() + 'Z'
        period_from = (datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z'
        
        elec_count = 0
        gas_count = 0
        
        for prop in account.get('properties', []):
            for meter_point in prop.get('electricity_meter_points', []):
                mpan = meter_point['mpan']
                for meter in meter_point.get('meters', []):
                    serial = meter['serial_number']
                    try:
                        readings = client.get_electricity_consumption(mpan, serial, period_from, period_to)
                        store_consumption('electricity', readings)
                        elec_count += len(readings)
                    except Exception as e:
                        print(f"Error fetching electricity: {e}")
            
            for meter_point in prop.get('gas_meter_points', []):
                mprn = meter_point['mprn']
                for meter in meter_point.get('meters', []):
                    serial = meter['serial_number']
                    try:
                        readings = client.get_gas_consumption(mprn, serial, period_from, period_to)
                        store_consumption('gas', readings)
                        gas_count += len(readings)
                    except Exception as e:
                        print(f"Error fetching gas: {e}")
        
        return jsonify({
            'status': 'success',
            'electricity_readings': elec_count,
            'gas_readings': gas_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/consumption/<fuel_type>')
def get_consumption(fuel_type):
    days = request.args.get('days', 7, type=int)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    c.execute('''SELECT interval_start, interval_end, consumption 
                 FROM consumption 
                 WHERE fuel_type = ? AND interval_start > ?
                 ORDER BY interval_start DESC LIMIT 500''', (fuel_type, cutoff))
    rows = c.fetchall()
    conn.close()
    data = [{'interval_start': r[0], 'interval_end': r[1], 'consumption': r[2]} 
            for r in rows]
    return jsonify(data)

@app.route('/api/stats')
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    stats = {}
    for fuel in ['electricity', 'gas']:
        c.execute('''SELECT COUNT(*), SUM(consumption), MIN(interval_start), MAX(interval_start)
                     FROM consumption WHERE fuel_type = ?''', (fuel,))
        row = c.fetchone()
        stats[fuel] = {
            'reading_count': row[0],
            'total_consumption': row[1],
            'earliest_reading': row[2],
            'latest_reading': row[3]
        }
    conn.close()
    return jsonify(stats)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
