from flask import Flask, jsonify, render_template, request
import requests
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Config
OCTOPUS_API_KEY = os.getenv('OCTOPUS_API_KEY', '')
ACCOUNT_NUMBER = os.getenv('OCTOPUS_ACCOUNT_NUMBER', '')

DB_PATH = 'energy.db'

def init_db():
    """Initialize SQLite database"""
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

class OctopusGraphQL:
    """Octopus Energy GraphQL API client"""
    BASE_URL = 'https://api.octopus.energy/v1/graphql/'
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.token = None
    
    def get_token(self):
        """Get Kraken token using API key"""
        if self.token:
            return self.token
        
        mutation = """
        mutation($apiKey: String!) {
          obtainKrakenToken(input: {APIKey: $apiKey}) {
            token
          }
        }
        """
        
        variables = {"apiKey": self.api_key}
        
        response = requests.post(
            self.BASE_URL,
            json={"query": mutation, "variables": variables}
        )
        response.raise_for_status()
        
        data = response.json()
        if 'errors' in data:
            raise Exception(f"GraphQL error: {data['errors']}")
        
        self.token = data['data']['obtainKrakenToken']['token']
        return self.token
    
    def query(self, query_string, variables=None):
        """Execute a GraphQL query"""
        token = self.get_token()
        
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            self.BASE_URL,
            headers=headers,
            json={"query": query_string, "variables": variables or {}}
        )
        response.raise_for_status()
        
        data = response.json()
        if 'errors' in data:
            raise Exception(f"GraphQL error: {data['errors']}")
        
        return data['data']
    
    def get_account_details(self, account_number):
        """Get account and meter details"""
        query = """
        query($accountNumber: String!) {
          account(accountNumber: $accountNumber) {
            number
            properties {
              electricityMeterPoints {
                mpan
                meters {
                  serialNumber
                }
              }
              gasMeterPoints {
                mprn
                meters {
                  serialNumber
                }
              }
            }
          }
        }
        """
        
        variables = {"accountNumber": account_number}
        return self.query(query, variables)
    
    def get_consumption(self, account_number, period_from, period_to):
        """Get electricity and gas consumption"""
        query = """
        query($accountNumber: String!, $fromDatetime: DateTime!, $toDatetime: DateTime!) {
          account(accountNumber: $accountNumber) {
            properties {
              electricityMeterPoints {
                mpan
                meters {
                  serialNumber
                  consumption(
                    first: 1500
                    fromDatetime: $fromDatetime
                    toDatetime: $toDatetime
                    orderBy: PERIOD_ASC
                  ) {
                    edges {
                      node {
                        startAt
                        endAt
                        value
                      }
                    }
                  }
                }
              }
              gasMeterPoints {
                mprn
                meters {
                  serialNumber
                  consumption(
                    first: 1500
                    fromDatetime: $fromDatetime
                    toDatetime: $toDatetime
                    orderBy: PERIOD_ASC
                  ) {
                    edges {
                      node {
                        startAt
                        endAt
                        value
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "accountNumber": account_number,
            "fromDatetime": period_from,
            "toDatetime": period_to
        }
        
        return self.query(query, variables)

def store_consumption(fuel_type, readings):
    """Store readings in SQLite"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for reading in readings:
        c.execute('''INSERT OR REPLACE INTO consumption 
                     (fuel_type, interval_start, interval_end, consumption, updated_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (fuel_type, 
                   reading['startAt'],
                   reading['endAt'],
                   reading['value'],
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
        <p><a href="/api/consumption/electricity">View Electricity Data (JSON)</a></p>
        <p><a href="/api/consumption/gas">View Gas Data (JSON)</a></p>
        <p><a href="/api/stats">View Stats</a></p>
    </body>
    </html>
    '''

@app.route('/api/account-info')
def account_info():
    """Get account and meter details"""
    if not OCTOPUS_API_KEY or not ACCOUNT_NUMBER:
        return jsonify({'error': 'API key or account number not configured'}), 500
    
    try:
        client = OctopusGraphQL(OCTOPUS_API_KEY)
        data = client.get_account_details(ACCOUNT_NUMBER)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fetch-data')
def fetch_latest_data():
    """Fetch consumption data from GraphQL API"""
    if not OCTOPUS_API_KEY or not ACCOUNT_NUMBER:
        return jsonify({'error': 'API key or account number not configured'}), 500
    
    try:
        client = OctopusGraphQL(OCTOPUS_API_KEY)
        
        # Fetch last 7 days
        period_to = datetime.utcnow().isoformat() + 'Z'
        period_from = (datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z'
        
        data = client.get_consumption(ACCOUNT_NUMBER, period_from, period_to)
        
        elec_count = 0
        gas_count = 0
        
        # Process electricity
        properties = data.get('account', {}).get('properties', [])
        for prop in properties:
            for meter_point in prop.get('electricityMeterPoints', []):
                for meter in meter_point.get('meters', []):
                    readings = [edge['node'] for edge in meter.get('consumption', {}).get('edges', [])]
                    if readings:
                        store_consumption('electricity', readings)
                        elec_count += len(readings)
            
            # Process gas
            for meter_point in prop.get('gasMeterPoints', []):
                for meter in meter_point.get('meters', []):
                    readings = [edge['node'] for edge in meter.get('consumption', {}).get('edges', [])]
                    if readings:
                        store_consumption('gas', readings)
                        gas_count += len(readings)
        
        return jsonify({
            'status': 'success',
            'electricity_readings': elec_count,
            'gas_readings': gas_count,
            'period_from': period_from,
            'period_to': period_to
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/consumption/<fuel_type>')
def get_consumption(fuel_type):
    """Get consumption data"""
    days = request.args.get('days', 7, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    c.execute('''SELECT interval_start, interval_end, consumption 
                 FROM consumption 
                 WHERE fuel_type = ? AND interval_start > ?
                 ORDER BY interval_start DESC''', (fuel_type, cutoff))
    
    rows = c.fetchall()
    conn.close()
    
    data = [{'interval_start': r[0], 'interval_end': r[1], 'consumption': r[2]} 
            for r in rows]
    
    return jsonify(data)

@app.route('/api/stats')
def get_stats():
    """Get summary stats"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    stats = {}
    for fuel in ['electricity', 'gas']:
        c.execute('''SELECT 
                        COUNT(*), 
                        SUM(consumption),
                        MIN(interval_start),
                        MAX(interval_start)
                     FROM consumption 
                     WHERE fuel_type = ?''', (fuel,))
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
