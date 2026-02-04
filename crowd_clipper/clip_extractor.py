"""
Clip extraction module.

Handles determining clip boundaries and exporting video segments.
"""

import subprocess
import os
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from .spike_detector import Spike


@dataclass
class Clip:
    """Represents a video clip to extract."""
    start_time: float   # Start time in seconds
    end_time: float     # End time in seconds
    spike: Spike        # The spike this clip is based on
    filename: str = ""  # Output filename


def find_clip_boundaries(
    spike: Spike,
    energy: np.ndarray,
    times: np.ndarray,
    baseline: np.ndarray,
    pre_roll: float = 5.0,
    post_roll: float = 3.0,
    min_duration: float = 5.0,
    max_duration: float = 15.0,
    tail_threshold: float = 0.7
) -> Tuple[float, float]:
    """
    Determine optimal clip start and end times around a spike.
    
    Args:
        spike: The detected spike
        energy: Full energy array
        times: Corresponding timestamps
        baseline: Baseline energy values
        pre_roll: Seconds to include before spike (captures setup)
        post_roll: Seconds to extend after the natural end
        min_duration: Minimum clip duration
        max_duration: Maximum clip duration
        tail_threshold: Energy must drop below baseline * this to end clip
        
    Returns:
        Tuple of (start_time, end_time)
    """
    # Start: pre_roll seconds before the spike, but not before 0
    start_time = max(0, spike.start_time - pre_roll)
    
    # Find where energy drops back to near-baseline after spike
    # Look for sustained drop, not just a brief dip
    natural_end = _find_natural_end(
        spike, energy, times, baseline, tail_threshold
    )
    
    # Add post_roll seconds after the natural end
    video_end = times[-1] if len(times) > 0 else natural_end
    end_time = min(natural_end + post_roll, video_end)
    
    # Enforce duration limits
    duration = end_time - start_time
    
    if duration < min_duration:
        # Extend symmetrically if possible
        extra_needed = min_duration - duration
        end_time = min(end_time + extra_needed, times[-1] if len(times) > 0 else end_time)
        duration = end_time - start_time
        
        if duration < min_duration:
            # Still short, try extending start back
            start_time = max(0, start_time - (min_duration - duration))
    
    if duration > max_duration:
        # Trim to max, keeping the peak moment centered-ish
        peak_offset = spike.peak_time - start_time
        
        if peak_offset < max_duration * 0.3:
            # Peak is near start, keep more after
            end_time = start_time + max_duration
        elif peak_offset > max_duration * 0.7:
            # Peak is near end, keep more before
            start_time = end_time - max_duration
        else:
            # Center around peak
            half_dur = max_duration / 2
            center = spike.peak_time
            start_time = max(0, center - half_dur)
            end_time = start_time + max_duration
    
    return start_time, end_time


def _find_natural_end(
    spike: Spike,
    energy: np.ndarray,
    times: np.ndarray,
    baseline: np.ndarray,
    tail_threshold: float
) -> float:
    """Find where the excitement naturally dies down after a spike."""
    if len(times) == 0:
        return spike.end_time
    
    # Start looking from the spike end
    start_idx = np.searchsorted(times, spike.end_time)
    
    # Look for sustained drop below threshold
    threshold = baseline[min(start_idx, len(baseline)-1)] * tail_threshold
    consecutive_below = 0
    required_consecutive = 5  # Need ~125ms of quiet (at 25ms hop)
    
    for i in range(start_idx, len(energy)):
        if energy[i] < threshold:
            consecutive_below += 1
            if consecutive_below >= required_consecutive:
                return times[i]
        else:
            consecutive_below = 0
    
    # If no clear end found, use a bit after spike end
    return min(spike.end_time + 2.0, times[-1] if len(times) > 0 else spike.end_time)


def create_clips(
    spikes: List[Spike],
    energy: np.ndarray,
    times: np.ndarray,
    baseline: np.ndarray,
    pre_roll: float = 5.0,
    post_roll: float = 3.0,
    min_duration: float = 5.0,
    max_duration: float = 15.0,
    max_clips: int = 10
) -> List[Clip]:
    """
    Create clip definitions from detected spikes.
    
    Args:
        spikes: List of spikes (should be pre-sorted by score)
        energy, times, baseline: Audio analysis data
        pre_roll, post_roll, min_duration, max_duration: Clip parameters
        max_clips: Maximum number of clips to create
        
    Returns:
        List of Clip objects ready for export
    """
    clips = []
    used_ranges = []  # Track used time ranges to avoid overlap
    
    for spike in spikes:
        if len(clips) >= max_clips:
            break
        
        start, end = find_clip_boundaries(
            spike, energy, times, baseline,
            pre_roll, post_roll, min_duration, max_duration
        )
        
        # Check for overlap with existing clips
        overlaps = False
        for used_start, used_end in used_ranges:
            if not (end <= used_start or start >= used_end):
                overlaps = True
                break
        
        if not overlaps:
            clips.append(Clip(
                start_time=start,
                end_time=end,
                spike=spike
            ))
            used_ranges.append((start, end))
    
    # Sort by time order
    clips.sort(key=lambda c: c.start_time)
    
    # Assign filenames
    for i, clip in enumerate(clips):
        clip.filename = f"clip_{i+1:02d}_{clip.start_time:.1f}s-{clip.end_time:.1f}s.mp4"
    
    return clips


def export_clip(
    video_path: str,
    start_time: float,
    end_time: float,
    output_path: str,
    reencode: bool = False
) -> bool:
    """
    Export a video clip using FFmpeg.
    
    Args:
        video_path: Input video path
        start_time: Start time in seconds
        end_time: End time in seconds
        output_path: Output file path
        reencode: If True, re-encode (slower but more accurate cuts)
        
    Returns:
        True if successful
    """
    duration = end_time - start_time
    
    if reencode:
        # Re-encode for precise cuts (slower)
        cmd = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            str(output_path)
        ]
    else:
        # Stream copy for fast extraction (may have slight inaccuracy)
        cmd = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path)
        ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error exporting clip: {e.stderr}")
        return False
    except FileNotFoundError:
        print("FFmpeg not found. Please ensure FFmpeg is installed.")
        return False


def export_all_clips(
    video_path: str,
    clips: List[Clip],
    output_dir: str,
    reencode: bool = False,
    progress_callback=None
) -> List[str]:
    """
    Export all clips to the output directory.
    
    Args:
        video_path: Input video path
        clips: List of clips to export
        output_dir: Output directory path
        reencode: Whether to re-encode (slower but more accurate)
        progress_callback: Optional callback(current, total) for progress
        
    Returns:
        List of successfully exported file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    exported = []
    
    for i, clip in enumerate(clips):
        output_path = output_dir / clip.filename
        
        if progress_callback:
            progress_callback(i + 1, len(clips))
        
        success = export_clip(
            video_path,
            clip.start_time,
            clip.end_time,
            str(output_path),
            reencode
        )
        
        if success:
            exported.append(str(output_path))
    
    return exported
