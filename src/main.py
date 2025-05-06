import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.oauth2.service_account
from googleapiclient.discovery import build
import datetime

# --- Configuration ---
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
SPREADSHEET_ID = '1lsZMuxGS7l3eCDbmPggYoKqMjcxwEB3HVoWhUqpIVMQ'
SHEET_NAME = 'RegistroDiario'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app)

# --- Google Sheets API Setup ---
def get_sheets_service():
    try:
        creds = google.oauth2.service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        return service
    except FileNotFoundError:
        app.logger.error(f"Credentials file not found at {SERVICE_ACCOUNT_FILE}")
        return None
    except Exception as e:
        app.logger.error(f"Error building Google Sheets service: {e}")
        return None

# --- API Routes ---
@app.route('/')
def index():
    return "Backend for GTA Farm Tracker Google Sheets Integration is running."

# Endpoint for single log entry (kept for potential future use or testing)
@app.route('/log_meta', methods=['POST'])
def log_meta():
    service = get_sheets_service()
    if not service:
        return jsonify({'error': 'Could not connect to Google Sheets API'}), 500

    data = request.get_json()
    if not data or 'name' not in data or 'id' not in data or 'timestamp' not in data:
        return jsonify({'error': 'Missing required data: name, id, timestamp'}), 400

    member_name = data['name']
    member_id = data['id']
    timestamp_str = data['timestamp']

    try:
        dt_object = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        formatted_timestamp = dt_object.strftime('%d/%m/%Y %H:%M:%S')
    except ValueError:
        formatted_timestamp = timestamp_str

    values = [[member_name, formatted_timestamp, member_id]]
    body = {'values': values}

    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body).execute()
        app.logger.info(f"Appended {result.get('updates').get('updatedCells')} cells via /log_meta.")
        return jsonify({'success': True, 'message': 'Data logged to Google Sheet'}), 200
    except Exception as e:
        app.logger.error(f"Error appending data via /log_meta: {e}")
        return jsonify({'error': f'Failed to append data: {e}'}), 500

# New endpoint for bulk synchronization
@app.route('/sync_history', methods=['POST'])
def sync_history():
    service = get_sheets_service()
    if not service:
        return jsonify({'error': 'Could not connect to Google Sheets API'}), 500

    entries = request.get_json() # Expecting a list of entry objects
    if not isinstance(entries, list) or not entries:
        return jsonify({'error': 'Invalid data format: Expected a non-empty list of entries'}), 400

    values_to_append = []
    for entry in entries:
        if 'name' not in entry or 'id' not in entry or 'timestamp' not in entry:
            app.logger.warning(f"Skipping invalid entry during sync: {entry}")
            continue # Skip invalid entries

        member_name = entry['name']
        member_id = entry['id']
        timestamp_str = entry['timestamp']

        try:
            dt_object = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            formatted_timestamp = dt_object.strftime('%d/%m/%Y %H:%M:%S')
        except ValueError:
            formatted_timestamp = timestamp_str # Fallback

        # Append [Name, DataHora, ID]
        values_to_append.append([member_name, formatted_timestamp, member_id])

    if not values_to_append:
        return jsonify({'success': True, 'message': 'No valid entries to sync'}), 200

    body = {'values': values_to_append}

    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body).execute()
        app.logger.info(f"Appended {result.get('updates').get('updatedCells')} cells via /sync_history.")
        return jsonify({'success': True, 'message': f'{len(values_to_append)} entries synced to Google Sheet'}), 200
    except Exception as e:
        app.logger.error(f"Error appending bulk data via /sync_history: {e}")
        return jsonify({'error': f'Failed to append bulk data: {e}'}), 500

# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

