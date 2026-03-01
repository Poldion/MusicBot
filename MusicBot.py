# Importing libraries and modules
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
from collections import deque
import asyncio

# Environment variables for tokens and other sensitive data
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN ist nicht gesetzt. Bitte prüfe deine .env-Datei im Projektverzeichnis.")

# Create the structure for queueing songs - Dictionary of queues
SONG_QUEUES = {}

# Lautstärke-Variable (0 bis 100, Standard: 100)
volume = 100

# YT-DLP Options for searching (fast, no streaming URL)
YDL_SEARCH_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "extract_flat": "in_playlist",
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# YT-DLP Options for playing (get streaming URL)
YDL_PLAY_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "cachedir": False,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


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
    await interaction.response.defer()
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not isinstance(voice_client, discord.VoiceClient) or not voice_client.is_connected():
        await interaction.followup.send("I'm not connected to any voice channel.")
        return

    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()
    
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    else:
        await voice_client.disconnect()
        
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

    # Prüfen, ob der Query ein YouTube-Link ist
    if any(domain in song_query for domain in ["youtube.com", "youtu.be"]):
        query = song_query
    else:
        query = "ytsearch1: " + song_query

    # Use SEARCH options first to get the video ID/URL quickly
    # This avoids the "Requested format is not available" error during the initial search phase
    results = await search_ytdlp_async(query, YDL_SEARCH_OPTIONS)

    tracks = results.get("entries", []) if "entries" in results else [results] if results else []
    if not tracks:
        await interaction.followup.send("No results found.")
        return
    first_track = tracks[0]

    webpage_url = first_track.get("webpage_url") or first_track.get("url")
    title = first_track.get("title", "Untitled")
    guild_id = str(interaction.guild_id)

    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    # Store info dict if we pre-extracted it, otherwise None
    song_data = {
        "webpage_url": webpage_url,
        "title": title,
        "info": None  # Always fetch fresh info before playing
    }
    SONG_QUEUES[guild_id].append(song_data)

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}** (Volume: {volume}%)")
        await play_next_song(voice_client, guild_id, interaction.channel, announce=False)


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

    if any(domain in song_query for domain in ["youtube.com", "youtu.be"]):
        query = song_query
    else:
        query = "ytsearch1: " + song_query

    # Use SEARCH options first to get the video ID/URL quickly
    results = await search_ytdlp_async(query, YDL_SEARCH_OPTIONS)
    tracks = results.get("entries", []) if "entries" in results else [results] if results else []
    if not tracks:
        await interaction.followup.send("No results found.")
        return
    first_track = tracks[0]

    webpage_url = first_track.get("webpage_url") or first_track.get("url")
    title = first_track.get("title", "Untitled")
    guild_id = str(interaction.guild_id)

    song_data = {
        "webpage_url": webpage_url,
        "title": title,
        "info": None  # Always fetch fresh info before playing
    }

    # Add to front of queue with pre-extracted info
    SONG_QUEUES.setdefault(guild_id, deque()).appendleft(song_data)

    await interaction.followup.send(f"Now playing immediately: **{title}** (Volume: {volume}%)")

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()  # This triggers after_play -> play_next_song
    else:
        await play_next_song(voice_client, guild_id, interaction.channel, announce=False)


async def play_next_song(voice_client, guild_id, channel, announce=True):
    global volume
    if SONG_QUEUES[guild_id]:
        song_data = SONG_QUEUES[guild_id].popleft()
        webpage_url = song_data["webpage_url"]
        title = song_data["title"]
        info = song_data.get("info")

        try:
            # Only extract if we don't have the info already
            if not info:
                # Use PLAY options here to get the actual streaming URL
                info = await search_ytdlp_async(webpage_url, YDL_PLAY_OPTIONS)
                if "entries" in info:
                    info = info["entries"][0]

            audio_url = info["url"]
            print(f"Playing {title} from {audio_url}")
        except Exception as e:
            print(f"Error extracting {title}: {e}")
            await channel.send(f"Could not play **{title}**. Skipping...")
            # Recursively call to play next
            await play_next_song(voice_client, guild_id, channel)
            return

        ffmpeg_volume = volume / 100

        ffmpeg_before_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

        # Pass HTTP headers to ffmpeg to avoid 403
        if "http_headers" in info:
            headers_list = []
            for key, value in info["http_headers"].items():
                headers_list.append(f"{key}: {value}")
            headers_str = "\r\n".join(headers_list)

            if headers_str:
                headers_str += "\r\n"
                # Escape quotes for command line
                headers_str = headers_str.replace('"', '\\"')
                ffmpeg_before_options += f" -headers \"{headers_str}\""

        ffmpeg_options = {
            "before_options": ffmpeg_before_options,
            "options": f"-vn -b:a 96k -filter:a volume={ffmpeg_volume}"
        }

        # In Docker (Linux), ffmpeg is in the PATH, so we don't need to specify the executable path.
        # If running locally on Windows, we might need it, but for Docker compatibility, we remove it.
        # discord.py will find ffmpeg automatically if it's installed in the system.
        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options)

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_play)
        if announce:
            asyncio.create_task(channel.send(f"Now playing: **{title}** (Volume: {volume}%)"))
    else:
        if voice_client.is_connected():
            await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()


# Slash-Command zum Setzen der Lautstärke (0 bis 100)
@bot.tree.command(name="volume", description="Setzt die Lautstärke (0 bis 100, Standard: 100)")
@app_commands.describe(value="Neue Lautstärke (z.B. 50 für 50%)")
async def set_volume(interaction: discord.Interaction, value: int):
    global volume
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
