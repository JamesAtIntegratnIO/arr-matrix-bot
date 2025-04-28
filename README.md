# Matrix *arr Bot

[![Docker Publish](https://github.com/JamesAtIntegratnIO/arr-matrix-bot/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/JamesAtIntegratnIO/arr-matrix-bot/actions/workflows/docker-publish.yml)

A Matrix bot designed to interact with Sonarr and Radarr instances. It allows users to search for media, get detailed information, and receive notifications directly in a Matrix room when downloads complete.

## Features

*   **Sonarr Integration:**
    *   Search for TV series using `!sonarr search <term>`.
    *   Filter search results to show only series not yet added (`--unadded` flag).
    *   Get detailed information and a poster for a specific series using `!sonarr info <tvdb_id>`.
*   **Radarr Integration:**
    *   Search for movies using `!radarr search <term>`.
    *   Filter search results to show only movies not yet added (`--unadded` flag).
    *   Get detailed information and a poster for a specific movie using `!radarr info <tmdb_id>`.
*   **Webhook Notifications (Radarr):**
    *   Receive formatted notification cards in Matrix when a movie finishes downloading and importing in Radarr.
*   **Help Command:**
    *   Display available commands and usage instructions with `!help [command]`.
*   **Docker Support:**
    *   Includes a Dockerfile for easy containerized deployment.
    *   GitHub Actions workflow to automatically build and push the image to GHCR.

## Setup

You can run this bot either directly with Python or using Docker.

### Python (Native)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/JamesAtIntegratnIO/arr-matrix-bot.git
    cd arr-matrix-bot
    ```
2.  **Prerequisites:**
    *   Python 3.11 or higher recommended.
3.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    # On Windows: .venv\Scripts\activate
    # On macOS/Linux: source .venv/bin/activate
    ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Configure:**
    *   Copy `config.json.example` to `config.json` (or create `config.json`).
    *   Edit `config.json` with your details (see [Configuration](#configuration) below). Ensure Sonarr/Radarr URLs are accessible from where you run the script (e.g., `http://localhost:7878`).
6.  **Run the bot:**
    ```bash
    python -m matrix_bot
    ```

### Docker

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/JamesAtIntegratnIO/arr-matrix-bot.git
    cd arr-matrix-bot
    ```
2.  **Configure:**
    *   Create a `config.json` file in the project root.
    *   Edit `config.json` with your details (see [Configuration](#configuration) below).
    *   **Important:** If Sonarr/Radarr are running on the *Docker host machine*, use `http://host.docker.internal:<port>` for the `sonarr_url` and `radarr_url` values (e.g., `http://host.docker.internal:7878`). `host.docker.internal` is a special DNS name Docker provides for containers to reach the host.
3.  **Build the Docker image:**
    ```bash
    docker build -t ghcr.io/jamesatintegratnio/arr-matrix-bot:latest .
    # Or use a custom tag:
    # docker build -t your-custom-name:latest .
    ```
4.  **Run the Docker container:**
    ```bash
    docker run -d \
      --name matrix-arr-bot \
      -p 9095:9095 \
      -v "$(pwd)/config.json:/app/config.json" \
      --restart unless-stopped \
      ghcr.io/jamesatintegratnio/arr-matrix-bot:latest
      # Replace image name if you used a custom one
    ```
    *   `-p 9095:9095`: Maps the host port 9095 to the container's port 9095 for the webhook listener. Adjust the *first* 9095 if that port is busy on your host.
    *   `-v "$(pwd)/config.json:/app/config.json"`: Mounts your local `config.json` into the container. (Use `%cd%` instead of `$(pwd)` on Windows CMD).

## Configuration

The bot is configured using a `config.json` file in the project root.

```json
{
  "matrix_homeserver": "YOUR_HOMESERVER_URL",              // e.g., "https://matrix.org"
  "matrix_user": "@your_bot:your_server.com",            // Bot's full Matrix User ID
  "matrix_password": "YOUR_BOT_PASSWORD",                // Bot's Matrix password
  "target_room_id": "!YOUR_TARGET_ROOM:your_server.com", // Room ID for notifications and commands
  "command_prefix": "!",                                 // Prefix for bot commands
  "sonarr_url": "http://localhost:8989",                 // URL for your Sonarr instance (use host.docker.internal for Docker)
  "sonarr_api_key": "YOUR_SONARR_API_KEY",               // Found in Sonarr > Settings > General
  "radarr_url": "http://localhost:7878",                 // URL for your Radarr instance (use host.docker.internal for Docker)
  "radarr_api_key": "YOUR_RADARR_API_KEY",               // Found in Radarr > Settings > General
  "tvdb_base_url": "https://api4.thetvdb.com/v4",        // TVDB API URL (usually no need to change)
  "tvdb_api_key": "YOUR_TVDB_API_KEY_HERE",              // Your personal TVDB API key (v4)
  "verify_tls": true,                                    // Set to false to ignore TLS certificate errors (use with caution)
  "webhook_host": "0.0.0.0",                             // Host IP for the bot's webhook server to listen on (0.0.0.0 listens on all interfaces)
  "webhook_port": 9095                                   // Port for the bot's webhook server
}
```

## Usage

### Commands

Interact with the bot in the configured `target_room_id`. Replace `!` with your configured `command_prefix`.

*   **Help:**
    *   `!help`: Show list of commands.
    *   `!help sonarr`: Show detailed help for the Sonarr command.
    *   `!help radarr`: Show detailed help for the Radarr command.
*   **Sonarr:**
    *   `!sonarr search <series name>`: Search for a series.
    *   `!sonarr search --unadded <series name>`: Search only for series not in Sonarr.
    *   `!sonarr info <tvdb_id>`: Get details for a series by its TVDb ID.
*   **Radarr:**
    *   `!radarr search <movie name>`: Search for a movie.
    *   `!radarr search --unadded <movie name>`: Search only for movies not in Radarr.
    *   `!radarr info <tmdb_id>`: Get details for a movie by its TMDb ID.

### Webhook Notifications (Radarr)

To receive notifications when Radarr finishes downloading and importing a movie:

1.  **Determine the Bot's Webhook URL:** This will be `http://<IP_OR_HOSTNAME>:<WEBHOOK_PORT>/webhook/radarr`.
    *   `<WEBHOOK_PORT>` is the `webhook_port` from your `config.json` (default `9095`).
    *   `<IP_OR_HOSTNAME>` is the address Radarr can use to reach the machine running the bot:
        *   **Native Python:** The IP address of the machine running the script.
        *   **Docker:** The IP address of the Docker host machine.
        *   **WSL2:** If running the bot in WSL2 and Radarr is on the Windows host, try `http://localhost:9095/...`. If Radarr is external or `localhost` doesn't work, you'll need to forward port 9095 from Windows to WSL2 (using `netsh interface portproxy`) and use the Windows host's IP address in the URL. See WSL documentation for details.
2.  **Configure Radarr:**
    *   Go to your Radarr instance.
    *   Navigate to `Settings` -> `Connect`.
    *   Click `+` to add a connection.
    *   Select `Webhook`.
    *   **Name:** Give it a name (e.g., "Matrix Bot").
    *   **On Grab:** Uncheck (optional).
    *   **On Download:** Check (Recommended - triggers after import).
    *   **On Upgrade:** Check (Optional).
    *   **URL:** Enter the Bot's Webhook URL determined in step 1.
    *   **Method:** Set to `POST`.
    *   Click `Test`. You should see a success message in Radarr and a confirmation ("✅ Received Radarr 'Test' webhook successfully!") from the bot in your Matrix room.
    *   Click `Save`.

*(Note: Sonarr webhook notifications are not yet implemented but could be added similarly).*

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a pull request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` file for more information (or choose and add a license file).