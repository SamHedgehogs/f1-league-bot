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
    Tab piloti = 'RISULTATI LG F1'
    A: piattaforma
    B: scuderia
    C: pilota
    D: ruolo
    E: TOT
    F..: gare
    """
    sheets = get_service()
    result = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="RISULTATI LG F1!A2:Z100"
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


def update_cell(row, col_letter, value, sheet_name="RISULTATI LG F1"):
    """
    VERSIONE DI TEST:
    ignora row/col_letter e prova sempre a scrivere 12345 in A2
    del tab 'RISULTATI LG F1'.
    Serve solo per verificare che l'accesso in scrittura funzioni.
    """
    sheets = get_service()
    range_ = "RISULTATI LG F1!A2"
    body = {"values": [[12345]]}
    sheets.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()


def get_standings():
    """
    Classifica piloti e team.
    Piloti: tab 'RISULTATI LG F1', C = pilota, E = TOT.
    Team: tab 'Scuderie', A = team, B = TOT.
    """
    sheets = get_service()

    # Piloti
    result_pilots = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="RISULTATI LG F1!C2:E100"
    ).execute()
    values_p = result_pilots.get("values", [])
    pilots = []
    for row in values_p:
        if len(row) < 1:
            continue
        name = row[0]   # C = pilota
        tot = 0.0
        if len(row) >= 3 and row[2]:
            try:
                tot = float(row[2])  # E = TOT
            except ValueError:
                tot = 0.0
        pilots.append({"name": name, "tot": tot})

    # Team
    result_teams = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Scuderie!A2:B50"
    ).execute()
    values_t = result_teams.get("values", [])
    teams = []
    for row in values_t:
        if len(row) < 1:
            continue
        name = row[0]   # A = team
        tot = 0.0
        if len(row) >= 2 and row[1]:
            try:
                tot = float(row[1])  # B = TOT
            except ValueError:
                tot = 0.0
        teams.append({"name": name, "tot": tot})

    return pilots, teams
