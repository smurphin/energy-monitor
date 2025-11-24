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
