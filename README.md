# Crowd Audio Clip Detector

Automatically finds and clips the most exciting moments in videos based on crowd audio spikes.

## Installation

1. **Ensure FFmpeg is installed** (already done via winget)

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```bash
python -m crowd_clipper.main VIDEO_PATH [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir` | `./clips` | Output directory for clips |
| `--threshold` | `2.0` | Spike detection sensitivity |
| `--pre-roll` | `1.5` | Seconds before spike to start clip |
| `--min-duration` | `5` | Minimum clip length (seconds) |
| `--max-duration` | `15` | Maximum clip length (seconds) |
| `--max-clips` | `10` | Maximum number of clips to extract |

### Example

```bash
python -m crowd_clipper.main wrestling_match.mp4 --output-dir ./highlights --max-clips 5
```

## How It Works

1. **Audio Extraction** - Extracts audio track from video using FFmpeg
2. **Energy Analysis** - Computes RMS energy envelope to measure loudness
3. **Spike Detection** - Finds moments where crowd noise exceeds baseline by threshold
4. **Clip Extraction** - Creates clips with pre-roll and proper end detection
