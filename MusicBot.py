# Importing libraries and modules
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp # NEW
from collections import deque # NEW
import asyncio # NEW

# Environment variables for tokens and other sensitive data
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN ist nicht gesetzt. Bitte prüfe deine .env-Datei im Projektverzeichnis.")

# Create the structure for queueing songs - Dictionary of queues
SONG_QUEUES = {}

# Lautstärke-Variable (0 bis 100, Standard: 100)
volume = 100

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)


# Setup of intents. Intents are permissions the bot has on the server
intents = discord.Intents.default()
intents.message_content = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Bot ready-up code
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} is online!")
    app_info = await bot.application_info()
    client_id = app_info.id
    permissions = 3145728  # "Connect" + "Speak" + "Read Messages"
    invite_url = (
        f"https://discord.com/oauth2/authorize?client_id={client_id}"
        f"&permissions={permissions}&scope=bot+applications.commands"
    )
    print(f"Einladungslink für den Bot: {invite_url}")


@bot.tree.command(name="skip", description="Skips the current playing song")
async def skip(interaction: discord.Interaction):
    # Kurzoperation, hier reicht eine direkte Antwort ohne defer
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not isinstance(voice_client, discord.VoiceClient):
        await interaction.response.send_message("Not playing anything to skip.")
        return
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")


@bot.tree.command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: discord.Interaction):
    # Kurzoperation, direkte Antwort ist okay
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not isinstance(voice_client, discord.VoiceClient):
        await interaction.response.send_message("I'm not in a voice channel.")
        return
    if not voice_client.is_playing():
        await interaction.response.send_message("Nothing is currently playing.")
        return
    voice_client.pause()
    await interaction.response.send_message("Playback paused!")


@bot.tree.command(name="resume", description="Resume the currently paused song.")
async def resume(interaction: discord.Interaction):
    # Kurzoperation, direkte Antwort ist okay
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not isinstance(voice_client, discord.VoiceClient):
        await interaction.response.send_message("I'm not in a voice channel.")
        return
    if not voice_client.is_paused():
        await interaction.response.send_message("I’m not paused right now.")
        return
    voice_client.resume()
    await interaction.response.send_message("Playback resumed!")


@bot.tree.command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: discord.Interaction):
    # Antwort direkt zu Beginn deferren, damit Discord die Interaktion als "in Bearbeitung" markiert
    if hasattr(interaction.response, 'defer'):
        await interaction.response.defer()
    else:
        await interaction.defer()

    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not isinstance(voice_client, discord.VoiceClient) or not voice_client.is_connected():
        await interaction.followup.send("I'm not connected to any voice channel.")
        return

    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await voice_client.disconnect(force=False)
    await interaction.followup.send("Stopped playback and disconnected!")


@bot.tree.command(name="play", description="Play a song or add it to the queue.")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
    if hasattr(interaction.response, 'defer'):
        await interaction.response.defer()
    else:
        await interaction.defer()
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You must be in a voice channel.")
        return
    voice_channel = interaction.user.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not isinstance(voice_client, discord.VoiceClient):
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)
    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    }
    # Prüfen, ob der Query ein YouTube-Link ist
    if any(domain in song_query for domain in ["youtube.com", "youtu.be"]):
        query = song_query  # Direktlink verwenden
    else:
        query = "ytsearch1: " + song_query  # Suchbegriff verwenden
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", []) if "entries" in results else [results] if results else []
    if not tracks:
        await interaction.followup.send("No results found.")
        return
    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")
    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()
    SONG_QUEUES[guild_id].append((audio_url, title))
    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}**")
        await play_next_song(voice_client, guild_id, interaction.channel)


@bot.tree.command(name="playnow", description="Spielt einen Song sofort und unterbricht die aktuelle Wiedergabe.")
@app_commands.describe(song_query="YouTube-Link oder Suchbegriff")
async def playnow(interaction: discord.Interaction, song_query: str):
    if hasattr(interaction.response, 'defer'):
        await interaction.response.defer()
    else:
        await interaction.defer()
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You must be in a voice channel.")
        return
    voice_channel = interaction.user.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not isinstance(voice_client, discord.VoiceClient):
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)
    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    }
    # Prüfen, ob der Query ein YouTube-Link ist
    if any(domain in song_query for domain in ["youtube.com", "youtu.be"]):
        query = song_query
    else:
        query = "ytsearch1: " + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", []) if "entries" in results else [results] if results else []
    if not tracks:
        await interaction.followup.send("No results found.")
        return
    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")
    guild_id = str(interaction.guild_id)
    # Song an den Anfang der Queue stellen, ohne die Queue zu leeren
    SONG_QUEUES.setdefault(guild_id, deque()).appendleft((audio_url, title))
    # Aktuelle Wiedergabe sofort stoppen
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    await interaction.followup.send(f"Now playing immediately: **{title}**")
    await play_next_song(voice_client, guild_id, interaction.channel)


async def play_next_song(voice_client, guild_id, channel):
    global volume
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()

        # FFmpeg erwartet den Wert als Dezimalzahl (1.0 = 100%)
        ffmpeg_volume = volume / 100
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": f"-vn -c:a libopus -b:a 96k -filter:a volume={ffmpeg_volume}"
        }

        # Im Docker-Container (Linux) liegt ffmpeg im PATH, daher kein Windows-spezifischer Pfad
        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="ffmpeg")

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_play)
        asyncio.create_task(channel.send(f"Now playing: **{title}** (Volume: {volume}%)"))
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()

# Slash-Command zum Setzen der Lautstärke (0 bis 100)
@bot.tree.command(name="volume", description="Setzt die Lautstärke (0 bis 100, Standard: 100)")
@app_commands.describe(value="Neue Lautstärke (z.B. 50 für 50%)")
async def set_volume(interaction: discord.Interaction, value: int):
    global volume
    # Volume-Change ist eine sehr schnelle Operation, direkte Antwort reicht
    if value < 0 or value > 100:
        await interaction.response.send_message("Bitte gib einen Wert zwischen 0 und 100 an.", ephemeral=True)
        return
    volume = value
    await interaction.response.send_message(
        f"Lautstärke wurde auf {volume}% gesetzt. Die Änderung wirkt ab dem nächsten Song.", ephemeral=True)

print("Starte Bot...")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"Fehler beim Starten des Bots: {e}")
