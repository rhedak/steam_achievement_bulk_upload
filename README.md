> **Deprecated — no longer maintained.** Valve shipped an [updated achievement system](https://store.steampowered.com/news/group/4145017/view/677385962174549063) with official **Bulk Import/Export** in Steamworks (definitions, localization, and icons via CSV). Use the partner portal’s achievement editor instead of this tool. See the [Step by Step: Achievements](https://partner.steamgames.com/doc/features/achievements/ach_guide) guide, **Bulk Import/Export** section.

# steam-ach-upload

Bulk-upload Steam achievements to the [Steamworks partner portal](https://partner.steamgames.com/) using browser automation (Playwright). Reads a CSV file of achievements and uploads each one — including icons — without you having to click through the portal manually.

*Warning: Currently only works if your steam website is set to English. You can fork and adjust the code for your preferred language or set your website to English.*

## Features

- Uploads name, description, achieved icon, and unachieved icon for every achievement in one run
- Browser opens visibly so you can monitor progress and intervene if needed
- Login session is persisted, so you only authenticate once
- `--start N` lets you resume mid-way after a failure
- `--dry-run` prints the upload plan without touching the browser

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### From source (recommended for development)

```bash
git clone https://github.com/rhedak/steam_achievement_bulk_upload
cd steam-ach-upload
uv sync
uv run playwright install chromium
```

### From PyPI

```bash
pip install steam-ach-upload
playwright install chromium
```

See also the package on [pypi](https://pypi.org/project/steam-ach-upload/)

## CSV format

Create a CSV file with the following columns (see [`sample/achievements.csv`](sample/achievements.csv) for an example):

| Column               | Description                                                       |
|----------------------|-------------------------------------------------------------------|
| `API Name`           | Steam internal achievement identifier (e.g. `ACH_FIRST_STEPS`)   |
| `Display Name (EN)`  | Name shown to players                                             |
| `Description (EN)`   | Description shown to players                                      |
| `Achieved Icon`      | Path to unlocked icon, relative to the CSV file                   |
| `Unachieved Icon`    | Path to locked icon, relative to the CSV file                     |

Icon paths are resolved relative to the CSV file's directory, so you can keep icons in a subfolder next to the CSV (e.g. `icons/my_ach_done.png`).

## Usage

```bash
# Upload all achievements
steam-ach-upload 1234567 path/to/achievements.csv

# Preview what would be uploaded (no browser)
steam-ach-upload 1234567 path/to/achievements.csv --dry-run

# Resume from row 15 after a failure
steam-ach-upload 1234567 path/to/achievements.csv --start 15

# Use a custom directory for the browser session
steam-ach-upload 1234567 path/to/achievements.csv --profile-dir ~/.steam_browser_session

# Debug: open browser, click New Achievement once, print page HTML, then exit
steam-ach-upload 1234567 path/to/achievements.csv --debug
```

Replace `1234567` with your actual Steam App ID, found in the Steamworks dashboard URL:
`https://partner.steamgames.com/apps/achievements/YOUR_APP_ID`

## First run / login

On first run the browser will open to the achievements page. Log in with your Steamworks account, then the upload will start automatically. Subsequent runs reuse the saved session.

## Running with uv (no install)

```bash
uv run --with steam-ach-upload steam-ach-upload 1234567 achievements.csv
```

Or from a local clone:

```bash
uv run python -m steam_ach_upload 1234567 achievements.csv
```

## Running tests

```bash
uv run pytest
```

## How it works

The portal requires achievements to be saved before icons can be attached. The tool therefore uploads each achievement in two passes:

1. Fill in the API name, display name, and description → Save
2. Re-open the saved row via Edit → upload achieved icon → upload unachieved icon → Save

If a row fails, the error is printed with the `--start N` command to retry from that point.

## License

See [LICENSE](LICENSE).

## Disclaimer

Built with support by Claude Code.

## Self-Promotion

If this package has been at all helpful to you consider checking out my game.

[Steam](https://store.steampowered.com/app/4757690/Panzer_Island/)

[Itcho.io](https://rhedak.itch.io/panzer-island-web)
