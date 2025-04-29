# Matrix *arr Bot

[![Docker Publish](https://github.com/JamesAtIntegratnIO/arr-matrix-bot/actions/workflows/docker_push.yaml/badge.svg)](https://github.com/JamesAtIntegratnIO/arr-matrix-bot/actions/workflows/docker_push.yaml)[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Optional: Add if you include a LICENSE file -->

A Matrix bot designed to interact with Sonarr and Radarr instances. It allows users to search for media, get detailed information, check service status, and receive notifications directly in a Matrix room when downloads complete.

## Features

*   **Sonarr Integration:**
    *   Search for TV series using `!sonarr search <term>`.
    *   Filter search results to show only series not yet added (`--unadded` flag).
    *   Get detailed information and a poster for a specific series using `!sonarr info <tvdb_id>`.
    *   Receive formatted notification cards in Matrix when an episode finishes downloading and importing (via Webhook).
*   **Radarr Integration:**
    *   Search for movies using `!radarr search <term>`.
    *   Filter search results to show only movies not yet added (`--unadded` flag).
    *   Get detailed information and a poster for a specific movie using `!radarr info <tmdb_id>`.
    *   Receive formatted notification cards in Matrix when a movie finishes downloading and importing (via Webhook).
*   **Status Command:**
    *   Check the connection status of the bot and all integrated services using `!status`.
*   **Help Command:**
    *   Display available commands and usage instructions with `!help [command]`.
*   **Docker Support:**
    *   Includes a Dockerfile for easy containerized deployment.
    *   GitHub Actions workflow automatically builds and pushes the image to GitHub Container Registry (GHCR). Pre-built images are available at `ghcr.io/jamesatintegratnio/arr-matrix-bot`.

## Setup

You can run this bot either directly with Python or using Docker.

### Python (Native)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/JamesAtIntegratnIO/arr-matrix-bot.git
    cd arr-matrix-bot
    ```
2.  **Prerequisites:**
    *   Python 3.11 or higher is required.
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
    *   Edit `config.json` with your details (see [Configuration](#configuration) below). Ensure Sonarr/Radarr URLs are accessible from where you run the script.
6.  **Run the bot:**
    ```bash
    python -m matrix_bot
    ```

### Docker

1.  **Clone the repository (Optional - only needed if building locally):**
    ```bash
    # Not needed if using the pre-built image from GHCR
    git clone https://github.com/JamesAtIntegratnIO/arr-matrix-bot.git
    cd arr-matrix-bot
    ```
2.  **Configure:**
    *   Create a `config.json` file (e.g., in your current directory or a dedicated config directory).
    *   Edit `config.json` with your details (see [Configuration](#configuration) below).
    *   **Important:** If Sonarr/Radarr are running on the *Docker host machine*, use `http://host.docker.internal:<port>` for the `sonarr_url` and `radarr_url` values (e.g., `http://host.docker.internal:8989`). `host.docker.internal` is a special DNS name Docker provides for containers to reach the host. If Sonarr/Radarr are in *other Docker containers* on the same Docker network, use their container names (e.g., `http://sonarr:8989`).
3.  **Build the Docker image (Optional - only if not using pre-built):**
    ```bash
    # Only needed if you cloned the repo and want to build yourself
    docker build -t ghcr.io/jamesatintegratnio/arr-matrix-bot:latest .
    # Or use a custom tag:
    # docker build -t your-custom-name:latest .
    ```
4.  **Run the Docker container:**
    ```bash
    # Make sure you have created config.json in your current directory first
    docker run -d \
      --name matrix-arr-bot \
      -p 9095:9095 \
      -v "$(pwd)/config.json:/app/config.json:ro" \
      --restart unless-stopped \
      ghcr.io/jamesatintegratnio/arr-matrix-bot:latest
      # Replace image name if you built a custom one
    ```
    *   `-p 9095:9095`: Maps the host port 9095 to the container's port 9095 for the webhook listener. Adjust the *first* 9095 if that port is busy on your host.
    *   `-v "$(pwd)/config.json:/app/config.json:ro"`: Mounts your local `config.json` into the container as read-only (`:ro`). Use `%cd%` instead of `$(pwd)` on Windows CMD, or provide the full path to your config file.

## Configuration

The bot is configured using a `config.json` file.

```json
{
  "matrix_homeserver": "YOUR_HOMESERVER_URL",              // e.g., "https://matrix.org"
  "matrix_user": "@your_bot:your_server.com",            // Bot's full Matrix User ID
  "matrix_password": "YOUR_BOT_PASSWORD",                // Bot's Matrix password
  "target_room_id": "!YOUR_TARGET_ROOM:your_server.com", // Optional: Room ID for notifications and commands. If set, commands ONLY work here.
  "command_prefix": "!",                                 // Prefix for bot commands (e.g., "!")
  "sonarr_url": "http://localhost:8989",                 // URL for your Sonarr instance (see Docker notes above)
  "sonarr_api_key": "YOUR_SONARR_API_KEY",               // Found in Sonarr > Settings > General
  "radarr_url": "http://localhost:7878",                 // URL for your Radarr instance (see Docker notes above)
  "radarr_api_key": "YOUR_RADARR_API_KEY",               // Found in Radarr > Settings > General
  "tvdb_base_url": "https://api4.thetvdb.com/v4",        // TVDB API URL (usually no need to change)
  "tvdb_api_key": "YOUR_TVDB_API_KEY_HERE",              // Your personal TVDB API key (v4) - Get from TheTVDB.com
  "verify_tls": true,                                    // Set to false to ignore TLS certificate errors (use with caution)
  "webhook_host": "0.0.0.0",                             // Host IP for the webhook server to listen on. '0.0.0.0' listens on all available network interfaces within the container/host. Usually correct.
  "webhook_port": 9095                                   // Port for the bot's webhook server (must match port mapping in Docker)
}
```
*   **`target_room_id`:** If you set this value, the bot will *only* respond to commands in this specific room and send notifications here. If left empty or `null`, the bot will respond to commands in *any* room it is invited to (which might cause duplicate responses if running multiple instances).

## Usage

Interact with the bot in the configured `target_room_id` (or any room if `target_room_id` is not set). Replace `!` with your configured `command_prefix`.

### Commands

*   **Help:**
    *   `!help`: Show list of available commands.
    *   `!help <command>`: Show detailed help for a specific command (e.g., `!help sonarr`).
*   **Status:**
    *   `!status`: Check the connection status of the bot and all configured services.
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
    *   `<WEBHOOK_PORT>` is the *host* port you mapped in your `docker run` command (e.g., the *first* `9095` in `-p 9095:9095`) or the `webhook_port` from `config.json` if running natively.
    *   `<IP_OR_HOSTNAME>` is the address Radarr can use to reach the machine running the bot:
        *   **Native Python:** The IP address of the machine running the script.
        *   **Docker:** The IP address of the Docker host machine. Must be reachable by Radarr.
        *   **WSL2:** If running the bot in WSL2 and Radarr is on the Windows host, try `http://localhost:<WEBHOOK_PORT>/...`. If Radarr is external or `localhost` doesn't work, you'll need to configure port forwarding from Windows to WSL2 (e.g., using `netsh interface portproxy`) and use the Windows host's IP address in the URL. See WSL documentation for details.
2.  **Configure Radarr:**
    *   Go to your Radarr instance.
    *   Navigate to `Settings` -> `Connect`.
    *   Click `+` to add a connection.
    *   Select `Webhook`.
    *   **Name:** Give it a name (e.g., "Matrix Bot").
    *   **On Grab:** Uncheck (optional).
    *   **On Download:** Check (Recommended - triggers after import).
    *   **On Upgrade:** Check (Optional).
    *   **URL:** Enter the Bot's Radarr Webhook URL determined in step 1.
    *   **Method:** Set to `POST`.
    *   Click `Test`. You should see a success message in Radarr and a confirmation ("✅ Received Radarr 'Test' webhook successfully!") from the bot in your Matrix room (if `target_room_id` is set).
    *   Click `Save`.

### Webhook Notifications (Sonarr)

To receive notifications when Sonarr finishes downloading and importing an episode:

1.  **Determine the Bot's Webhook URL:** This will be `http://<IP_OR_HOSTNAME>:<WEBHOOK_PORT>/webhook/sonarr`.
    *   `<WEBHOOK_PORT>` and `<IP_OR_HOSTNAME>` are determined the same way as for the Radarr webhook (see above).
2.  **Configure Sonarr:**
    *   Go to your Sonarr instance.
    *   Navigate to `Settings` -> `Connect`.
    *   Click `+` to add a connection.
    *   Select `Webhook`.
    *   **Name:** Give it a name (e.g., "Matrix Bot").
    *   **On Grab:** Uncheck (optional).
    *   **On Download:** Check (Recommended - triggers after import).
    *   **On Upgrade:** Check (Optional).
    *   **URL:** Enter the Bot's Sonarr Webhook URL determined in step 1.
    *   **Method:** Set to `POST`.
    *   Click `Test`. You should see a success message in Sonarr and a confirmation ("✅ Received Sonarr 'Test' webhook successfully!") from the bot in your Matrix room (if `target_room_id` is set).
    *   Click `Save`.

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a pull request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` file for more information. (Consider adding a `LICENSE` file with the MIT license text to your repository).