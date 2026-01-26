# Discord Music Bot (Remastered)

A simple Discord music bot with a per-server queue that plays YouTube audio and supports the most important control commands (play, playnow, skip, pause, resume, stop, volume). It is built with `discord.py`, `yt-dlp`, and `ffmpeg`.

The original bot is based on a YouTube tutorial (see below) but has been updated to use slash commands, `yt-dlp`, and Docker.

---

## Features

- Slash commands (application commands)
  - `/play` – Play a song or add it to the queue (YouTube URL or search query)
  - `/playnow` – Play a song immediately and interrupt the current playback
  - `/skip` – Skip the currently playing song
  - `/pause` – Pause the current playback
  - `/resume` – Resume paused playback
  - `/stop` – Stop playback, clear the queue, and leave the voice channel
  - `/volume` – Set the volume for future songs (0–100%)
- Server-specific queue (one queue per guild)
- Volume control via FFmpeg audio filter
- Ready-to-use Docker image: `docker.io/poldion/musicbot`

Original tutorial video: https://youtu.be/U5CUkxUh2CQ

---

## Requirements

### General

- A Discord account and a bot application in the [Discord Developer Portal](https://discord.com/developers/applications)
- The bot must be invited to your server with the required permissions for voice and slash commands

### For manual Python installation

- Python 3.11 (recommended; at least 3.8)
- `pip`
- `ffmpeg` available on your system
  - **Linux (Debian/Ubuntu):**
    ```bash
    sudo apt update
    sudo apt install ffmpeg
    ```
  - **Windows:**
    - Download ffmpeg from https://www.ffmpeg.org/download.html, or use a pre-bundled `bin/ffmpeg` folder inside your project.
    - Make sure your code either:
      - Uses the system `ffmpeg` (via `PATH`), **or**
      - Explicitly points to your local `bin/ffmpeg` folder when creating `FFmpegOpusAudio`.

---

## Configuration (.env)

The bot reads the Discord token from the environment variable `DISCORD_TOKEN`. The easiest way is to create a `.env` file in the project directory:

```env
DISCORD_TOKEN=YOUR_DISCORD_TOKEN_HERE
```

The file is automatically loaded via `python-dotenv`.

---

## Installation & Run with Docker (pre-built image)

The pre-built image is available at: **`docker.io/poldion/musicbot`**.

### 1. Install Docker

See the official docs: https://docs.docker.com/engine/install/

### 2. Prepare the `.env` file

Create a `.env` file in any directory:

```env
DISCORD_TOKEN=YOUR_DISCORD_TOKEN_HERE
```

### 3. Start the container

In the directory where your `.env` file is located:

```bash
docker run --rm \
  --name musicbot \
  --env-file .env \
  docker.io/poldion/musicbot:latest
```

- `--rm` removes the container after it stops
- `--env-file .env` passes the Discord token into the container

Optionally run it in the background (detached):

```bash
docker run -d \
  --name musicbot \
  --env-file .env \
  docker.io/poldion/musicbot:latest
```

View logs:

```bash
docker logs -f musicbot
```

---

## Installation & Deployment with Docker Compose

With Docker Compose you can manage the bot easily via `docker compose up -d`.

### 1. Create `docker-compose.yml`

Create a file called `docker-compose.yml` in an empty directory (or in your project directory) with content similar to this:

```yaml
version: "3.9"

services:
  musicbot:
    image: docker.io/poldion/musicbot:latest
    container_name: musicbot
    restart: unless-stopped
    env_file:
      - .env
```

Alternatively, you can pass the token directly as an environment variable in the compose file (less secure, but sometimes convenient):

```yaml
version: "3.9"

services:
  musicbot:
    image: docker.io/poldion/musicbot:latest
    container_name: musicbot
    restart: unless-stopped
    environment:
      DISCORD_TOKEN: "YOUR_DISCORD_TOKEN_HERE"
```

### 2. Create `.env` next to it (if you use `env_file`)

In the same directory:

```env
DISCORD_TOKEN=YOUR_DISCORD_TOKEN_HERE
```

### 3. Start the bot

```bash
docker compose up -d
```

- `docker compose logs -f` shows you the logs
- `docker compose down` stops the bot

---

## Manual installation (without Docker)

If you want to run the bot directly on your system with Python:

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/discord-music-bot-remastered.git
cd discord-music-bot-remastered
```

*(Adjust the URL to match your repository if you forked or renamed it.)*

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows (PowerShell/CMD)
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

*If you prefer not to use `requirements.txt`, you can install the required packages manually:*

```bash
pip install discord.py python-dotenv yt-dlp PyNaCl
```

### 4. Create `.env`

```env
DISCORD_TOKEN=YOUR_DISCORD_TOKEN_HERE
```

### 5. Start the bot

```bash
python MusicBot.py
```

The console should show something similar to:

- `Starte Bot...` ("Starting bot..." – log message in German)
- `<BotName> is online!`
- An invite link for your bot

---

## Build the Docker image yourself

If you want to build your own image or customize the bot, you can use the provided `Dockerfile`.

### 1. Requirements

- Docker installed
- Project source code available (e.g., cloned from your fork)

### 2. Build the image

In the project directory (where `Dockerfile` and `MusicBot.py` are located):

```bash
docker build -t musicbot:latest .
```

This will create a local image called `musicbot:latest`.

### 3. Run locally (without a registry)

```bash
# in the directory containing your .env

docker run --rm \
  --name musicbot \
  --env-file .env \
  musicbot:latest
```

### 4. Push your own image to a registry (optional)

If you want to use your own Docker Hub repository (or another registry):

```bash
# Example: your Docker Hub username is "yourname"
docker tag musicbot:latest yourname/musicbot:latest

docker login
# Enter your Docker Hub username and password/token

docker push yourname/musicbot:latest
```

In your `docker-compose.yml` you can then replace `docker.io/poldion/musicbot:latest` with your own image:

```yaml
services:
  musicbot:
    image: yourname/musicbot:latest
    container_name: musicbot
    restart: unless-stopped
    env_file:
      - .env
```

---

## Notes & Troubleshooting

- **Bot is offline / never appears online:**
  - Double-check that `DISCORD_TOKEN` is set correctly (no extra spaces, correct bot token).
  - Make sure the bot is enabled in the Developer Portal and that the correct intents are turned on (e.g. Message Content Intent if needed).
- **No audio / no sound in the voice channel:**
  - Ensure `ffmpeg` is installed (locally), or installed in the container (the Dockerfile in this repo already installs `ffmpeg`).
  - On Windows, verify that your code points to the correct `ffmpeg` binary (either via `PATH` or a local `bin/ffmpeg` folder).
- **Slash commands are not visible:**
  - Wait a few minutes for Discord to propagate and sync the commands.
  - Make sure the bot is invited to the correct server.

If you want to support additional platforms (e.g. Raspberry Pi, ARM, specific cloud providers), the README can be extended with platform-specific notes.
