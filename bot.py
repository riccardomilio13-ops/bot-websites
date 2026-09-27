import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal

# ================= CONFIGURAZIONE =================
# INSERISCI QUI L'ID DEL TUO SERVER DI TEST PER AGGIORNARE I COMANDI ALL'ISTANTE
GUILD_ID = discord.Object(id=123456789012345678)  # Sostituisci con il tuo vero ID server
# ==================================================

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True # Necessario per moderazione e gestione ruoli
        super().__init__(command_prefix=".", intents=intents)

    async def setup_hook(self):
        # Carica i file di database locali
        self.load_databases()
        
        # Sincronizza i comandi slash sul server di test
        self.tree.copy_global_to(guild=GUILD_ID)
        await self.tree.sync(guild=GUILD_ID)
        print("Comandi Slash sincronizzati correttamente!")

    def load_databases(self):
        # Database dei Warn
        if not os.path.exists("warns.json"):
            with open("warns.json", "w") as f: json.dump({}, f)
        # Database dei Comandi Personalizzati
        if not os.path.exists("custom_commands.json"):
            with open("custom_commands.json", "w") as f: json.dump({}, f)

bot = MyBot()

# Funzioni di utilità per leggere/scrivere JSON
def get_json_data(filename):
    with open(filename, "r") as f: return json.load(f)
def save_json_data(filename, data):
    with open(filename, "w") as f: json.dump(data, f, indent=4)


@bot.event
async def on_ready():
    print(f"Bot online come {bot.user}")


# ================= SITEMA TICKET =================

class TicketView(discord.ui.View):
    def __init__(self, tipo_input: str, opzioni_testo: str):
        super().__init__(timeout=None) # Timeout None per renderlo persistente
        
        if tipo_input == "bottone":
            button = discord.ui.Button(label=opzioni_testo[:80], style=discord.ButtonStyle.primary, custom_id="ticket_btn")
            button.callback = self.create_ticket
            self.add_item(button)
        elif tipo_input == "tendina":
            select = discord.ui.Select(placeholder="Seleziona un'opzione...", custom_id="ticket_select")
            # Separa le opzioni se l'utente le divide con una virgola
            opzioni = [o.strip() for o in opzioni_testo.split(",")]
            for i, opz in enumerate(opzioni[:25]): # Massimo 25 opzioni
                select.add_option(label=opz[:100], value=f"opz_{i}")
            select.callback = self.create_ticket
            self.add_item(select)

    async def create_ticket(self, interaction: discord.Interaction):
        # Logica base per creare un canale ticket privato
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        canale = await guild.create_text_channel(name=f"ticket-{interaction.user.name}", overwrites=overwrites)
        await interaction.response.send_message(f"Ticket creato con successo in {canale.mention}!", ephemeral=True)
        await canale.send(f"Ciao {interaction.user.mention}, un membro dello staff sarà presto da te. Usa questo spazio per spiegare la tua richiesta.")

@bot.tree.command(name="setticket", description="Configura il pannello dei ticket")
@app_commands.checks.has_permissions(administrator=True)
async def setticket(interaction: discord.Interaction, nome_pannello: str, tipo: Literal["bottone", "tendina"], testo_opzioni: str):
    view = TicketView(tipo, testo_opzioni)
    embed = discord.Embed(title=nome_pannello, description="Clicca sul bottone o usa la tendina qui sotto per aprire un ticket di supporto.", color=discord.Color.blue())
    await interaction.response.send_message("Pannello Ticket generato!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=view)


# ================= MODERAZIONE =================

@bot.tree.command(name="ban", description="Banna un utente dal server")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, utente: discord.Member, motivo: str = "Nessun motivo fornito"):
    await utente.ban(reason=motivo)
    await interaction.response.send_message(f"🚫 {utente.mention} è stato bannato. Motivo: {motivo}")

@bot.tree.command(name="mute", description="Muta un utente nel server (Timeout)")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, utente: discord.Member, durata_minuti: int):
    import datetime
    durata = datetime.timedelta(minutes=durata_minuti)
    await utente.timeout(durata)
    await interaction.response.send_message(f"🤫 {utente.mention} è stato mutato per {durata_minuti} minuti.")

@bot.tree.command(name="unmute", description="Togli il mute a un utente")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, utente: discord.Member):
    await utente.timeout(None)
    await interaction.response.send_message(f"🔊 {utente.mention} non è più mutato.")


# ================= SISTEMA WARN =================

@bot.tree.command(name="warn", description="Assegna un ammonimento a un utente")
@app_commands.checks.has_permissions(kick_members=True)
async def warn(interaction: discord.Interaction, utente: discord.Member, motivo: str, livello: Literal[1, 2, 3, 4, 5]):
    data = get_json_data("warns.json")
    user_id = str(utente.id)
    
    if user_id not in data:
        data[user_id] = []
        
    warn_entry = {"motivo": motivo, "livello": livello, "staff": interaction.user.name}
    data[user_id].append(warn_entry)
    save_json_data("warns.json", data)
    
    await interaction.response.send_message(f"⚠️ {utente.mention} è stato ammonito! [Livello: {livello}/5] - Motivo: {motivo}")

@bot.tree.command(name="contawarn", description="Visualizza i warn di un utente")
async def contawarn(interaction: discord.Interaction, utente: discord.Member):
    data = get_json_data("warns.json")
    user_id = str(utente.id)
    
    if user_id not in data or len(data[user_id]) == 0:
        await interaction.response.send_message(f"✅ {utente.mention} non ha alcun ammonimento attivo.")
        return
        
    embed = discord.Embed(title=f"Warn di {utente.name}", color=discord.Color.orange())
    for i, w in enumerate(data[user_id], 1):
        embed.add_field(name=f"Warn #{i} (Livello {w['livello']})", value=f"**Motivo:** {w['motivo']}\n**Staff:** {w['staff']}", inline=False)
        
    await interaction.response.send_message(embed=embed)


# ================= GESTIONE RUOLI =================

@bot.tree.command(name="pex", description="Aggiunge un ruolo a un utente")
@app_commands.checks.has_permissions(manage_roles=True)
async def pex(interaction: discord.Interaction, utente: discord.Member, ruolo: discord.Role):
    await utente.add_roles(ruolo)
    await interaction.response.send_message(f"✅ Aggiunto il ruolo {ruolo.mention} a {utente.mention}")

@bot.tree.command(name="depex", description="Rimuove un ruolo da un utente")
@app_commands.checks.has_permissions(manage_roles=True)
async def depex(interaction: discord.Interaction, utente: discord.Member, ruolo: discord.Role):
    await utente.remove_roles(ruolo)
    await interaction.response.send_message(f"❌ Rimosso il ruolo {ruolo.mention} da {utente.mention}")


# ================= COMANDI PERSONALIZZATI DICIOTTI =================

@bot.tree.command(name="addcomando", description="Crea un comando personalizzato testuale")
@app_commands.checks.has_permissions(administrator=True)
async def addcomando(interaction: discord.Interaction, nome_comando: str, testo_risposta: str):
    nome_comando = nome_comando.lower().replace("/", "") # Rimuove eventuali slash inseriti per errore
    data = get_json_data("custom_commands.json")
    
    data[nome_comando] = testo_risposta
    save_json_data("custom_commands.json", data)
    
    await interaction.response.send_message(f"⚙️ Comando dinamico registrato! Ora puoi usare il prefisso prefissato `.` seguito da `{nome_comando}` (Es: `.{nome_comando}`), oppure attendere il riavvio del bot.", ephemeral=True)

# Listener che intercetta i vecchi messaggi con il punto '.' per eseguire i comandi personalizzati dinamici
@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    if message.content.startswith("."):
        cmd_trigger = message.content[1:].lower().strip()
        data = get_json_data("custom_commands.json")
        
        if cmd_trigger in data:
            await message.channel.send(data[cmd_trigger])
            
    await bot.process_commands(message)

# Gestione degli errori per i permessi dei comandi Slash
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Non hai i permessi necessari per usare questo comando.", ephemeral=True)


# Sostituisci con il tuo token o lascialo così se usi Railway
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Errore: Impossibile trovare il DISCORD_TOKEN.")
