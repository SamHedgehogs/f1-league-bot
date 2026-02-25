import os
import json
import re
import discord
from discord.ext import commands
from discord import app_commands

from sheets_client import get_pilots, update_cell, get_standings, get_service

TOKEN = os.getenv("DISCORD_TOKEN")

# Metti qui gli ID reali dei canali
CHANNEL_ISCRIZIONE = 1476155744733888514      # canale "iscrizione"
CHANNEL_CALENDARIO = 1476155763410862154      # canale "calendario"
CHANNEL_RISULTATI = 1476155799771283621       # canale "risultati"
CHANNEL_CLASSIFICA = 1476155822743617617      # canale "classifica"

POINTS_RACE = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
POINTS_SPRINT = [8, 7, 6, 5, 4, 3, 2, 1]

STATE_FILE = "race_state.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


class TipoGara(discord.Enum):
    GARA = "GARA"
    SPRINT = "SPRINT"


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync error: {e}")
    print(f"Logged in as {bot.user}")


def find_first_empty_column(sheet_name: str, header_row: int, start_col_letter: str) -> str:
    """
    Trova la prima colonna vuota nella riga header_row,
    a partire da start_col_letter (es. F per Piloti, C per Scuderie).
    """
    sheets = get_service()
    start_col = ord(start_col_letter)
    end_col = ord("Z")
    range_ = f"{sheet_name}!{start_col_letter}{header_row}:{chr(end_col)}{header_row}"
    result = sheets.values().get(
        spreadsheetId=os.getenv("SPREADSHEET_ID"),
        range=range_
    ).execute()
    values = result.get("values", [])
    if not values:
        return start_col_letter

    row_vals = values[0]
    for i in range(start_col, end_col + 1):
        idx = i - start_col
        cell_val = row_vals[idx] if idx < len(row_vals) else ""
        if cell_val in ("", None):
            return chr(i)

    return chr(end_col)


@bot.tree.command(
    name="set_current_race",
    description="Imposta la gara attuale (nome) e il tipo (gara/sprint)"
)
@app_commands.describe(nome_gara="Es. BELGIO", tipo="GARA o SPRINT")
async def set_current_race(
    interaction: discord.Interaction,
    nome_gara: str,
    tipo: TipoGara
):
    nome_gara_up = nome_gara.upper().strip()

    # 1) colonna libera in Piloti (da F in poi)
    col_piloti = find_first_empty_column("Piloti", header_row=1, start_col_letter="F")
    update_cell(row=1, col_letter=col_piloti, value=nome_gara_up, sheet_name="Piloti")

    # 2) colonna libera in Scuderie (da C in poi)
    sheets = get_service()
    col_team = find_first_empty_column("Scuderie", header_row=1, start_col_letter="C")
    range_team_header = f"Scuderie!{col_team}1"
    body = {"values": [[nome_gara_up]]}
    sheets.values().update(
        spreadsheetId=os.getenv("SPREADSHEET_ID"),
        range=range_team_header,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    # 3) salva nello state
    state = {
        "current_race": {
            "nome": nome_gara_up,
            "tipo": tipo.value,
            "col_piloti": col_piloti,
            "col_team": col_team,
        }
    }
    save_state(state)

    await interaction.response.send_message(
        f"Gara corrente impostata su **{nome_gara_up}** ({tipo.value}). "
        f"Piloti colonna {col_piloti}, Scuderie colonna {col_team}.",
        ephemeral=True
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.channel.id != CHANNEL_RISULTATI:
        return

    state = load_state()
    race_info = state.get("current_race")
    if not race_info:
        await message.channel.send("Prima imposta la gara con /set_current_race.", delete_after=10)
        return

    current_type = race_info.get("tipo", "GARA")
    col_letter = race_info.get("col_piloti")
    if not col_letter:
        await message.channel.send("Colonna gara non trovata, reimposta con /set_current_race.", delete_after=10)
        return

    points_table = POINTS_SPRINT if current_type == "SPRINT" else POINTS_RACE

    lines = message.content.splitlines()

    pilots = get_pilots()
    pilot_map = {p["pilota"].strip().lower(): p["row"] for p in pilots if p["pilota"]}

    # es. "1 Tummy", "2 Samuel"
    pattern = re.compile(r"^\s*(\d+)\s+(.+)$")

    updates = []
    for line in lines:
        m = pattern.match(line)
        if not m:
            continue
        pos = int(m.group(1))
        name = m.group(2).strip()
        key = name.lower()

        if pos <= 0:
            continue

        pts = points_table[pos - 1] if pos <= len(points_table) else 0

        row = pilot_map.get(key)
        if row is None:
            updates.append((pos, name, pts, None))
            continue

        update_cell(row=row, col_letter=col_letter, value=pts, sheet_name="Piloti")
        updates.append((pos, name, pts, row))

    await post_standings(message.guild)

    if updates:
        msg_lines = []
        for pos, name, pts, row in updates:
            if row is None:
                msg_lines.append(f"{pos}) {name} -> {pts} pt (NON TROVATO)")
            else:
                msg_lines.append(f"{pos}) {name} -> {pts} pt (riga {row})")
        await message.channel.send("Risultati elaborati:\n" + "\n".join(msg_lines))


async def post_standings(guild: discord.Guild):
    pilots, teams = get_standings()
    pilots_sorted = sorted(pilots, key=lambda x: x["tot"], reverse=True)
    teams_sorted = sorted(teams, key=lambda x: x["tot"], reverse=True)

    channel = guild.get_channel(CHANNEL_CLASSIFICA)
    if channel is None:
        return

    async for msg in channel.history(limit=100):
        if msg.author == bot.user:
            await msg.delete()

    desc_p = ""
    for i, p in enumerate(pilots_sorted, start=1):
        desc_p += f"{i}) {p['name']} - {p['tot']} pt\n"

    desc_t = ""
    for i, t in enumerate(teams_sorted, start=1):
        desc_t += f"{i}) {t['name']} - {t['tot']} pt\n"

    embed_p = discord.Embed(title="Classifica Piloti", description=desc_p or "Nessun dato")
    embed_t = discord.Embed(title="Classifica Costruttori", description=desc_t or "Nessun dato")

    await channel.send(embeds=[embed_p, embed_t])


bot.run(TOKEN)
