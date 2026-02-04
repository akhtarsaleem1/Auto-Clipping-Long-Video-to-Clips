"""
Audio extraction and energy analysis module.

Handles extracting audio from video files and computing energy envelopes
for crowd spike detection.

Enhanced with frequency-based analysis for better crowd detection in
videos with constant commentary.
"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import Tuple, Optional
import numpy as np

try:
    import soundfile as sf
except ImportError as e:
    raise ImportError(
        "Required audio library not installed. Run: pip install soundfile"
    ) from e


def extract_audio(video_path: str, output_path: Optional[str] = None) -> str:
    """
    Extract audio from video file using FFmpeg.
    
    Args:
        video_path: Path to the input video file
        output_path: Optional output path for WAV file. If None, uses temp file.
        
    Returns:
        Path to extracted audio WAV file
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    if output_path is None:
        # Create temp file with .wav extension
        fd, output_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
    
    # Use FFmpeg to extract audio as mono WAV at 22050 Hz (good for analysis)
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # PCM 16-bit
        "-ar", "22050",  # Sample rate
        "-ac", "1",  # Mono
        "-y",  # Overwrite
        str(output_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg failed to extract audio: {e.stderr}") from e
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Please install FFmpeg and ensure it's in your PATH."
        )
    
    return output_path


def load_audio(audio_path: str) -> Tuple[np.ndarray, int]:
    """
    Load audio file into numpy array using soundfile.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Tuple of (audio_data, sample_rate)
    """
    audio, sr = sf.read(audio_path)
    
    # Ensure mono (if stereo, take mean)
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)
    
    # Ensure float32
    audio = audio.astype(np.float32)
    
    return audio, sr


def bandpass_filter(audio: np.ndarray, sr: int, low_freq: float = 500.0, high_freq: float = 4000.0) -> np.ndarray:
    """
    Apply a simple bandpass filter to focus on crowd frequencies.
    
    Crowd cheers and reactions typically fall in the 500Hz-4000Hz range.
    This helps isolate crowd noise from commentary (which has more low-end)
    and general background noise.
    
    Args:
        audio: Audio samples
        sr: Sample rate
        low_freq: Low cutoff frequency (Hz) - higher = more selective
        high_freq: High cutoff frequency (Hz)
        
    Returns:
        Filtered audio
    """
    # Use FFT-based filtering for simplicity (no scipy required)
    n = len(audio)
    
    # Compute FFT
    fft = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    
    # Create bandpass mask
    mask = (freqs >= low_freq) & (freqs <= high_freq)
    
    # Apply filter
    fft_filtered = fft * mask
    
    # Inverse FFT
    filtered = np.fft.irfft(fft_filtered, n)
    
    return filtered.astype(np.float32)


def compute_rms_energy(
    audio: np.ndarray,
    sample_rate: int,
    window_ms: int = 50,
    hop_ms: int = 25
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute RMS energy envelope of audio signal using pure numpy.
    
    Args:
        audio: Audio samples as numpy array
        sample_rate: Sample rate of audio
        window_ms: Window size in milliseconds
        hop_ms: Hop size in milliseconds
        
    Returns:
        Tuple of (energy_values, time_stamps)
    """
    # Convert ms to samples
    window_samples = int(sample_rate * window_ms / 1000)
    hop_samples = int(sample_rate * hop_ms / 1000)
    
    # Compute number of frames
    n_samples = len(audio)
    n_frames = 1 + (n_samples - window_samples) // hop_samples
    
    if n_frames <= 0:
        # Audio too short, return single frame
        rms = np.array([np.sqrt(np.mean(audio**2))])
        times = np.array([0.0])
        return rms, times
    
    # Compute RMS for each frame
    rms = np.zeros(n_frames)
    for i in range(n_frames):
        start = i * hop_samples
        end = start + window_samples
        frame = audio[start:end]
        rms[i] = np.sqrt(np.mean(frame**2))
    
    # Generate corresponding timestamps
    times = np.arange(n_frames) * hop_samples / sample_rate
    
    return rms, times


def compute_energy_derivative(energy: np.ndarray, times: np.ndarray) -> np.ndarray:
    """
    Compute rate of change of energy to detect sudden spikes.
    
    Crowd reactions are characterized by sudden increases in volume,
    not gradual changes. This helps distinguish crowd reactions from
    gradual audio level changes.
    
    Args:
        energy: RMS energy values
        times: Corresponding timestamps
        
    Returns:
        Derivative (rate of change) of energy
    """
    if len(energy) < 2:
        return np.zeros_like(energy)
    
    # Compute derivative
    dt = times[1] - times[0] if len(times) > 1 else 1.0
    derivative = np.diff(energy) / dt
    
    # Pad to same length
    derivative = np.concatenate([[0], derivative])
    
    # Only keep positive derivatives (volume increases)
    derivative = np.maximum(derivative, 0)
    
    return derivative


def compute_baseline(
    energy: np.ndarray,
    times: np.ndarray,
    window_seconds: float = 10.0,
    percentile: float = 30.0
) -> np.ndarray:
    """
    Compute rolling baseline (moving percentile) for comparison.
    
    Uses a percentile-based approach to establish "normal" audio levels,
    which helps ignore sustained high energy (like constant commentary).
    
    Args:
        energy: RMS energy values
        times: Corresponding timestamps
        window_seconds: Window size for baseline computation (longer = more stable)
        percentile: Percentile to use (lower = more sensitive to spikes)
        
    Returns:
        Baseline values for each energy point
    """
    if len(times) < 2:
        return np.ones_like(energy) * np.median(energy)
    
    # Estimate samples per second from times array
    samples_per_second = 1.0 / (times[1] - times[0]) if len(times) > 1 else 40
    window_samples = int(window_seconds * samples_per_second)
    window_samples = max(window_samples, 3)  # Minimum window size
    
    # Compute rolling percentile as baseline (ignores spikes)
    baseline = np.zeros_like(energy)
    half_window = window_samples // 2
    
    for i in range(len(energy)):
        start = max(0, i - half_window)
        end = min(len(energy), i + half_window + 1)
        baseline[i] = np.percentile(energy[start:end], percentile)
    
    # Ensure baseline is never zero (avoid division issues)
    baseline = np.maximum(baseline, np.percentile(energy, 10))
    
    return baseline


def analyze_video_audio(video_path: str, use_crowd_filter: bool = True, debug: bool = False) -> dict:
    """
    Full pipeline: extract audio from video and compute energy analysis.
    
    Args:
        video_path: Path to video file
        use_crowd_filter: If True, apply bandpass filter for crowd frequencies
        debug: If True, include additional debug information
        
    Returns:
        Dictionary with keys:
        - 'energy': RMS energy values
        - 'times': Corresponding timestamps
        - 'baseline': Baseline energy values
        - 'derivative': Rate of change of energy
        - 'sample_rate': Audio sample rate
        - 'duration': Total duration in seconds
        - 'crowd_energy': Energy from crowd frequency band (if use_crowd_filter)
    """
    # Extract audio to temp file
    audio_path = extract_audio(video_path)
    
    try:
        # Load audio
        audio, sr = load_audio(audio_path)
        
        # Compute full-band energy
        energy, times = compute_rms_energy(audio, sr)
        
        # Compute energy in crowd frequency band
        if use_crowd_filter:
            crowd_audio = bandpass_filter(audio, sr, low_freq=500, high_freq=4000)
            crowd_energy, _ = compute_rms_energy(crowd_audio, sr)
        else:
            crowd_energy = energy
        
        # Compute baseline using crowd energy (more stable)
        baseline = compute_baseline(crowd_energy, times, window_seconds=10.0, percentile=30.0)
        
        # Compute derivative (rate of change) for sudden spike detection
        derivative = compute_energy_derivative(crowd_energy, times)
        
        duration = len(audio) / sr
        
        result = {
            'energy': crowd_energy,  # Use crowd-filtered energy as primary
            'times': times,
            'baseline': baseline,
            'derivative': derivative,
            'sample_rate': sr,
            'duration': duration,
        }
        
        if debug:
            result['full_energy'] = energy
            result['crowd_energy'] = crowd_energy
            result['raw_audio_stats'] = {
                'min': float(np.min(audio)),
                'max': float(np.max(audio)),
                'mean': float(np.mean(audio)),
                'std': float(np.std(audio)),
            }
        
        return result
    finally:
        # Clean up temp file
        if os.path.exists(audio_path):
            os.remove(audio_path)
