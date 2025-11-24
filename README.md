# Energy Monitor

A Flask-based web application for monitoring energy consumption using the Octopus Energy GraphQL API. Designed to run on Raspberry Pi with plans to integrate real-time data from Octopus Home Mini.

## Features

- Fetches half-hourly electricity and gas consumption data from Octopus Energy
- Stores data locally in SQLite database
- GraphQL API integration (ready for Home Mini real-time data)
- RESTful API endpoints for consumption data and stats
- Lightweight Flask web interface

## Requirements

- Raspberry Pi (tested on Pi 3)
- Raspberry Pi OS Lite (64-bit)
- Python 3.7+
- Octopus Energy account with API access

## Installation

1. Clone the repository:
```bash
git clone git@github.com:smurphin/energy-monitor.git
cd energy-monitor
```

2. Create virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask requests schedule
```

3. Initialize the database:
```bash
python app.py
# Ctrl+C to stop after database is created
```

## Configuration

Set environment variables in `~/.bashrc`:
```bash
export OCTOPUS_API_KEY='sk_live_xxxxxxxxxxxxx'
export OCTOPUS_ACCOUNT_NUMBER='A-12345678'
```

Get your API key from the [Octopus Energy dashboard](https://octopus.energy/dashboard/).

Reload environment:
```bash
source ~/.bashrc
```

## Usage

### Run the application
```bash
cd energy-monitor
source venv/bin/activate
python app.py
```

Access the web interface at `http://your-pi-ip:5000`

### API Endpoints

- `GET /` - Web interface homepage
- `GET /api/account-info` - View account and meter details
- `GET /api/fetch-data` - Manually trigger data fetch from Octopus API
- `GET /api/consumption/electricity?days=7` - Get electricity consumption
- `GET /api/consumption/gas?days=7` - Get gas consumption
- `GET /api/stats` - View summary statistics

## Roadmap

- [ ] Add scheduled daily data fetching
- [ ] Integrate Home Mini for real-time consumption data
- [ ] Create data visualization dashboard
- [ ] Add cost calculations based on tariff rates
- [ ] Build custom in-home display (IHD) using Pi Zero

## Architecture

- **Flask**: Web framework
- **SQLite**: Local data storage
- **GraphQL**: Octopus Energy API integration
- **Raspberry Pi**: Server platform

## License

MIT License - see LICENSE file for details

## Author

Darren Murphy ([@smurphin](https://github.com/smurphin))
