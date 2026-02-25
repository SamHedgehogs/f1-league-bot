import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]  # read+write

def get_service():
    json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not json_str:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON non impostata")
    info = json.loads(json_str)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    return service.spreadsheets()

def get_pilots():
    """
    Legge i piloti dal tab 'Piloti', righe 2–100 (adatta se servono più righe).
    """
    sheets = get_service()
    result = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Piloti!A2:Z100"
    ).execute()
    values = result.get("values", [])
    pilots = []
    for idx, row in enumerate(values, start=2):
        piattaforma = row[0] if len(row) > 0 else ""
        team = row[1] if len(row) > 1 else ""
        pilota = row[2] if len(row) > 2 else ""
        ruolo = row[3] if len(row) > 3 else ""
        pilots.append({
            "row": idx,
            "piattaforma": piattaforma,
            "team": team,
            "pilota": pilota,
            "ruolo": ruolo,
            "raw": row,
        })
    return pilots


def update_cell(row, col_letter, value):
    """
    Aggiorna una singola cella, es. H5
    """
    sheets = get_service()
    range_ = f"RISULTATI LG F1!{col_letter}{row}"
    body = {"values": [[value]]}
    sheets.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

def get_standings():
    """
    Legge classifica piloti e team.
    Adatta range/colonne alla tua configurazione.
    """
    sheets = get_service()
    # Piloti: pilota (C), TOT (es. E) righe 2–24
    result_pilots = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="RISULTATI LG F1!C2:E24"
    ).execute()
    values_p = result_pilots.get("values", [])
    pilots = []
    for row in values_p:
        if len(row) < 1:
            continue
        name = row[0]
        tot = 0.0
        if len(row) >= 3 and row[2]:
            try:
                tot = float(row[2])
            except ValueError:
                tot = 0.0
        pilots.append({"name": name, "tot": tot})

    # Team: nome (B), TOT (es. E) righe 33–43
    result_teams = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="RISULTATI LG F1!B33:E43"
    ).execute()
    values_t = result_teams.get("values", [])
    teams = []
    for row in values_t:
        if len(row) < 1:
            continue
        name = row[0]
        tot = 0.0
        if len(row) >= 3 and row[2]:
            try:
                tot = float(row[2])
            except ValueError:
                tot = 0.0
        teams.append({"name": name, "tot": tot})

    return pilots, teams
