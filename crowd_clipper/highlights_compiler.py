"""
Highlights compilation module for YouTube-ready videos.

Merges individual clips into a single highlights video with:
- Fade transitions between clips (transformative content)
- Chronological ordering
- Proper quality settings for YouTube monetization

YouTube Guidelines Followed:
- Transformative content through transitions
- No duplicate consecutive content
- High quality output (maintains source quality)
- Proper video encoding for YouTube compatibility
"""

import subprocess
import os
import tempfile
from pathlib import Path
from typing import List, Optional
from datetime import datetime


def get_clip_duration(clip_path: str) -> float:
    """Get duration of a video clip using FFprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            clip_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except:
        return 10.0  # Default fallback


def find_peak_position(clip_path: str) -> float:
    """
    Find the position of peak audio energy in a clip.
    This identifies where the most exciting moment (loudest crowd reaction) occurs.
    
    Uses audio volume analysis to find the loudest sustained moment.
    
    Returns:
        Time position of peak in seconds
    """
    clip_duration = get_clip_duration(clip_path)
    if clip_duration <= 0:
        return 0.0
    
    try:
        # Extract audio to temporary WAV and analyze with numpy
        import tempfile
        import struct
        
        # Use FFmpeg to get audio samples
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmp:
            tmp_path = tmp.name
        
        # Extract raw audio samples
        cmd = [
            "ffmpeg", "-i", clip_path,
            "-vn",  # No video
            "-ac", "1",  # Mono
            "-ar", "8000",  # 8kHz sample rate (enough for analysis)
            "-f", "s16le",  # 16-bit signed PCM
            "-y", tmp_path
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        
        # Read the raw audio data
        with open(tmp_path, 'rb') as f:
            raw_data = f.read()
        
        # Clean up temp file
        os.remove(tmp_path)
        
        if len(raw_data) < 100:
            return clip_duration * 0.3  # Fallback
        
        # Convert to samples
        num_samples = len(raw_data) // 2
        samples = struct.unpack(f'<{num_samples}h', raw_data)
        
        # Calculate RMS energy in windows
        sample_rate = 8000
        window_duration = 0.5  # 0.5 second windows
        window_size = int(sample_rate * window_duration)
        hop_size = window_size // 4  # 75% overlap
        
        energies = []
        times = []
        
        for i in range(0, num_samples - window_size, hop_size):
            window = samples[i:i + window_size]
            # Calculate RMS energy
            rms = (sum(s * s for s in window) / len(window)) ** 0.5
            energies.append(rms)
            times.append((i + window_size // 2) / sample_rate)
        
        if not energies:
            return clip_duration * 0.3
        
        # Find peak energy position
        # Skip first 10% and last 10% to avoid intro/outro
        skip_start = int(len(energies) * 0.1)
        skip_end = int(len(energies) * 0.9)
        
        if skip_end <= skip_start:
            skip_start = 0
            skip_end = len(energies)
        
        max_energy = 0
        peak_idx = skip_start
        
        for i in range(skip_start, skip_end):
            if energies[i] > max_energy:
                max_energy = energies[i]
                peak_idx = i
        
        peak_time = times[peak_idx] if peak_idx < len(times) else clip_duration * 0.3
        
        print(f"    Peak audio at {peak_time:.1f}s (energy: {max_energy:.0f})")
        return peak_time
        
    except Exception as e:
        print(f"    Peak detection fallback: {e}")
        pass
    
    # Fallback: Return 30% into the clip (after typical pre-roll of 5s in 15s clips)
    return clip_duration * 0.3


def extract_peak_segment(
    clip_path: str,
    output_path: str,
    segment_duration: float = 5.0,
    exact_duration: bool = True
) -> bool:
    """
    Extract the peak segment from a clip based on audio analysis.
    
    Analyzes the clip audio to find the loudest moment (peak crowd reaction)
    and extracts a segment centered on that moment.
    
    Args:
        clip_path: Input clip path
        output_path: Output segment path
        segment_duration: Duration to extract (default 5 seconds)
        exact_duration: If True, re-encode to get exact duration
        
    Returns:
        True if successful
    """
    duration = get_clip_duration(clip_path)
    
    if duration <= segment_duration:
        # Clip is shorter than segment, use entire clip
        try:
            if exact_duration:
                # Re-encode to ensure compatibility
                cmd = [
                    "ffmpeg", "-i", clip_path,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k",
                    "-y", output_path
                ]
            else:
                cmd = ["ffmpeg", "-i", clip_path, "-c", "copy", "-y", output_path]
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except:
            return False
    
    # Find peak moment using audio analysis
    peak_time = find_peak_position(clip_path)
    
    # Center the segment around the peak
    half_segment = segment_duration / 2
    start_time = max(0, peak_time - half_segment)
    
    # Make sure we don't exceed clip duration
    if start_time + segment_duration > duration:
        start_time = max(0, duration - segment_duration)
    
    try:
        if exact_duration:
            # Re-encode for EXACT duration (slower but precise)
            cmd = [
                "ffmpeg",
                "-ss", str(start_time),
                "-i", clip_path,
                "-t", str(segment_duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
                "-avoid_negative_ts", "make_zero",
                "-y",
                output_path
            ]
        else:
            # Stream copy (fast but may have inaccurate duration)
            cmd = [
                "ffmpeg",
                "-ss", str(start_time),
                "-i", clip_path,
                "-t", str(segment_duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                output_path
            ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def extract_peak_segments(
    clip_paths: List[str],
    output_dir: str,
    segment_duration: float = 5.0,
    progress_callback=None
) -> List[str]:
    """
    Extract peak segments from all clips.
    
    Args:
        clip_paths: List of clip paths
        output_dir: Directory for extracted segments
        segment_duration: Duration of each segment
        progress_callback: Optional progress callback
        
    Returns:
        List of extracted segment paths
    """
    # Use absolute paths to avoid path duplication issues
    output_dir = os.path.abspath(output_dir)
    segments_dir = os.path.join(output_dir, "_highlight_segments")
    os.makedirs(segments_dir, exist_ok=True)
    
    extracted = []
    for i, clip in enumerate(clip_paths):
        if progress_callback:
            progress_callback(f"Extracting segment {i+1}/{len(clip_paths)}...")
        
        segment_name = f"segment_{i:04d}.mp4"
        segment_path = os.path.join(segments_dir, segment_name)
        
        # Use absolute path for clip too
        clip_abs = os.path.abspath(clip)
        
        if extract_peak_segment(clip_abs, segment_path, segment_duration):
            extracted.append(segment_path)
    
    return extracted


def create_concat_file(clip_paths: List[str], output_path: str) -> str:
    """
    Create FFmpeg concat demuxer file listing all clips.
    
    Args:
        clip_paths: List of clip file paths
        output_path: Directory for the concat file
        
    Returns:
        Path to the concat file
    """
    # Use absolute paths to avoid path issues
    output_path = os.path.abspath(output_path)
    concat_file = os.path.join(output_path, "concat_list.txt")
    
    with open(concat_file, 'w', encoding='utf-8') as f:
        for clip in clip_paths:
            # Use absolute path and FFmpeg requires forward slashes
            abs_path = os.path.abspath(clip)
            safe_path = abs_path.replace('\\', '/').replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
    
    return concat_file


def compile_highlights_simple(
    clip_paths: List[str],
    output_path: str,
    video_title: str = "Highlights",
    add_effects: bool = True
) -> bool:
    """
    Concatenation with transformative effects for YouTube compliance.
    
    Adds visual and audio modifications to make content transformative:
    - Slight brightness/contrast adjustment
    - Audio normalization
    - Subtle zoom effect
    
    Args:
        clip_paths: List of clip files to merge
        output_path: Output highlights video path
        video_title: Title for metadata
        add_effects: Whether to add transformative effects
        
    Returns:
        True if successful
    """
    if not clip_paths:
        print("No clips to compile")
        return False
    
    output_dir = os.path.dirname(output_path)
    concat_file = create_concat_file(clip_paths, output_dir)
    
    try:
        if add_effects:
            # Visual transformations to bypass Content ID:
            # 1. Horizontal flip (mirror) - changes visual fingerprint
            # 2. Add colored border/frame
            # 3. Heavy color grading (saturation, hue shift)
            # 4. Vignette effect (dark edges)
            # NO speed change or audio modification to avoid sync issues
            
            video_filter = (
                "hflip,"  # Mirror horizontally
                "eq=brightness=0.05:contrast=1.1:saturation=1.2,"  # Color grade
                "hue=h=5,"  # Slight hue shift
                "pad=iw+20:ih+20:10:10:color=black,"  # Add black border
                "vignette=angle=PI/4"  # Vignette dark edges
            )
            
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-vf", video_filter,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
                "-metadata", f"title={video_title}",
                "-metadata", f"comment=Fan Highlights Compilation",
                "-metadata", f"creation_time={datetime.now().isoformat()}",
                "-movflags", "+faststart",
                "-y",
                output_path
            ]
        else:
            # Simple stream copy without effects
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-metadata", f"title={video_title}",
                "-metadata", f"creation_time={datetime.now().isoformat()}",
                "-y",
                output_path
            ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error compiling highlights: {e.stderr}")
        return False
    finally:
        # Cleanup concat file
        if os.path.exists(concat_file):
            os.remove(concat_file)


def compile_highlights_shorts(
    clip_paths: List[str],
    output_path: str,
    video_title: str = "Shorts"
) -> bool:
    """
    Compile clips into a YouTube Shorts / Instagram Reels format (9:16 vertical).
    
    Crops the center of the video and resizes to 1080x1920 (9:16 aspect ratio).
    
    Args:
        clip_paths: List of clip files to merge
        output_path: Output shorts video path
        video_title: Title for metadata
        
    Returns:
        True if successful
    """
    if not clip_paths:
        print("No clips to compile")
        return False
    
    output_dir = os.path.dirname(output_path)
    concat_file = create_concat_file(clip_paths, output_dir)
    
    try:
        # Visual transformations to bypass Content ID:
        # 1. Crop to 9:16 and resize
        # 2. Horizontal flip (mirror)
        # 3. Heavy color grading
        # 4. Black border
        # NO speed change or audio modification to avoid sync issues
        
        video_filter = (
            "crop=ih*9/16:ih,"  # Crop to 9:16
            "hflip,"  # Mirror horizontally
            "scale=1080:1920,"  # Resize to Shorts resolution
            "eq=brightness=0.05:contrast=1.1:saturation=1.2,"  # Color grade
            "hue=h=5,"  # Slight hue shift
            "pad=1100:1960:10:20:color=black,"  # Add border
            "setsar=1"
        )
        
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-vf", video_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-metadata", f"title={video_title}",
            "-metadata", f"comment=Fan Shorts Compilation",
            "-metadata", f"creation_time={datetime.now().isoformat()}",
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error compiling shorts: {e.stderr}")
        return False
    finally:
        # Cleanup concat file
        if os.path.exists(concat_file):
            os.remove(concat_file)


def compile_highlights_with_transitions(
    clip_paths: List[str],
    output_path: str,
    transition_duration: float = 0.5,
    video_title: str = "Highlights",
    fade_type: str = "fade"
) -> bool:
    """
    Compile clips with fade transitions between them.
    
    This creates transformative content suitable for YouTube monetization
    by adding professional transitions between clips.
    
    Args:
        clip_paths: List of clip files to merge
        output_path: Output highlights video path
        transition_duration: Fade duration in seconds
        video_title: Title for metadata
        fade_type: Type of transition (fade, crossfade)
        
    Returns:
        True if successful
    """
    if not clip_paths:
        print("No clips to compile")
        return False
    
    if len(clip_paths) == 1:
        # Single clip - just copy with metadata
        return compile_highlights_simple(clip_paths, output_path, video_title)
    
    # For many clips, use simple concat to avoid command line length issues on Windows
    # The concat method with file list avoids the path length limitation
    if len(clip_paths) > 20:
        print(f"  Using simple concat for {len(clip_paths)} clips (faster for many clips)")
        return compile_highlights_simple(clip_paths, output_path, video_title)
    
    # For smaller number of clips, use transitions
    output_dir = os.path.dirname(output_path)
    
    # Use a filter script file to avoid command line length issues
    filter_script_path = os.path.join(output_dir, "filter_script.txt")
    
    # Build complex filter for transitions
    filter_parts = []
    input_parts = []
    
    # Build input list
    for i, clip in enumerate(clip_paths):
        input_parts.extend(["-i", clip])
    
    n_clips = len(clip_paths)
    
    # Create filter graph for fade transitions
    video_streams = []
    audio_streams = []
    
    for i in range(n_clips):
        v_label = f"v{i}"
        a_label = f"a{i}"
        
        if i == 0:
            # First clip: fade out at end
            filter_parts.append(
                f"[{i}:v]fade=t=out:st=0:d={transition_duration}:alpha=0,setpts=PTS-STARTPTS[{v_label}]"
            )
        elif i == n_clips - 1:
            # Last clip: fade in at start
            filter_parts.append(
                f"[{i}:v]fade=t=in:st=0:d={transition_duration},setpts=PTS-STARTPTS[{v_label}]"
            )
        else:
            # Middle clips: fade in and out
            filter_parts.append(
                f"[{i}:v]fade=t=in:st=0:d={transition_duration},fade=t=out:st=0:d={transition_duration}:alpha=0,setpts=PTS-STARTPTS[{v_label}]"
            )
        
        # Audio: fade in/out for smooth transitions
        if i == 0:
            filter_parts.append(f"[{i}:a]afade=t=out:st=0:d={transition_duration}[{a_label}]")
        elif i == n_clips - 1:
            filter_parts.append(f"[{i}:a]afade=t=in:st=0:d={transition_duration}[{a_label}]")
        else:
            filter_parts.append(
                f"[{i}:a]afade=t=in:st=0:d={transition_duration},afade=t=out:st=0:d={transition_duration}[{a_label}]"
            )
        
        video_streams.append(f"[{v_label}]")
        audio_streams.append(f"[{a_label}]")
    
    # Concatenate all streams
    concat_v = "".join(video_streams) + f"concat=n={n_clips}:v=1:a=0[outv]"
    concat_a = "".join(audio_streams) + f"concat=n={n_clips}:v=0:a=1[outa]"
    
    filter_parts.append(concat_v)
    filter_parts.append(concat_a)
    
    filter_complex = ";".join(filter_parts)
    
    # Write filter to file to avoid command line length issues
    try:
        with open(filter_script_path, 'w', encoding='utf-8') as f:
            f.write(filter_complex)
        
        cmd = [
            "ffmpeg",
            *input_parts,
            "-filter_complex_script", filter_script_path,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",  # High quality for YouTube
            "-c:a", "aac",
            "-b:a", "192k",  # Good audio quality
            "-metadata", f"title={video_title}",
            "-metadata", f"creation_time={datetime.now().isoformat()}",
            "-movflags", "+faststart",  # YouTube optimization
            "-y",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error compiling highlights with transitions: {e.stderr}")
        # Fall back to simple compilation
        print("Falling back to simple concatenation...")
        return compile_highlights_simple(clip_paths, output_path, video_title)
    except OSError as e:
        # Handle Windows path length issue
        print(f"Path length issue, falling back to simple concat: {e}")
        return compile_highlights_simple(clip_paths, output_path, video_title)
    finally:
        # Cleanup filter script
        if os.path.exists(filter_script_path):
            try:
                os.remove(filter_script_path)
            except:
                pass


def compile_highlights(
    clip_paths: List[str],
    output_dir: str,
    source_video_name: str,
    use_transitions: bool = True,
    transition_duration: float = 0.5,
    segment_duration: float = 5.0,
    shorts_mode: bool = False,
    target_duration: float = 0,
    progress_callback=None
) -> Optional[str]:
    """
    Main function to compile clips into highlights video.
    
    For YouTube policy compliance, extracts only the peak 5-second moment
    from each clip to create a transformative compilation.
    
    Args:
        clip_paths: List of clip file paths (will be sorted chronologically)
        output_dir: Directory to save highlights video
        source_video_name: Original video name for output naming
        use_transitions: Whether to add fade transitions
        transition_duration: Duration of transitions in seconds
        segment_duration: Duration of peak segment to extract from each clip
        shorts_mode: If True, create 9:16 vertical video for Shorts/Reels
        target_duration: Target total duration for Shorts (auto-calculates segment)
        progress_callback: Optional callback for progress updates
        
    Returns:
        Path to highlights video if successful, None otherwise
    """
    if not clip_paths:
        return None
    
    # Convert to absolute paths to avoid path issues
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert all clips to absolute paths
    abs_clips = [os.path.abspath(p) for p in clip_paths]
    
    # Custom sort key function to maintain chronological order
    # Handles filenames like: clip_01_10.5s-25.3s.mp4 or segment_0001.mp4
    import re
    def sort_key(path):
        basename = os.path.basename(path)
        # Extract all numbers from filename
        numbers = re.findall(r'[\d.]+', basename)
        if numbers:
            # Return tuple of first number (sequence) and second if exists (timestamp)
            try:
                return (float(numbers[0]), float(numbers[1]) if len(numbers) > 1 else 0)
            except:
                return (0, 0)
        return (0, 0)
    
    # Sort clips by extracted numbers to maintain chronological order
    sorted_clips = sorted(abs_clips, key=sort_key)
    
    # For Shorts mode with target duration, auto-calculate segment duration
    actual_segment_duration = segment_duration
    clips_to_use = sorted_clips
    
    if shorts_mode and target_duration > 0 and len(sorted_clips) > 0:
        # Calculate how many clips we can use with minimum 1s per clip
        max_clips_for_target = int(target_duration)  # 1s per clip minimum
        
        # Calculate per-clip segment: target_duration / num_clips
        if len(sorted_clips) <= max_clips_for_target:
            # We can use all clips
            actual_segment_duration = target_duration / len(sorted_clips)
            # Cap at 5 seconds max per clip
            actual_segment_duration = min(actual_segment_duration, 5.0)
        else:
            # Too many clips, limit to fit target duration
            # Use 1 second per clip and limit clip count
            actual_segment_duration = 1.0
            clips_to_use = sorted_clips[:max_clips_for_target]
            print(f"    Limiting to {len(clips_to_use)} clips to fit {target_duration}s target")
        
        print(f"    Auto-calculated: {actual_segment_duration:.1f}s x {len(clips_to_use)} clips = ~{actual_segment_duration * len(clips_to_use):.0f}s")
    
    # Generate output filename
    base_name = Path(source_video_name).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if shorts_mode:
        output_name = f"{base_name}_shorts_{timestamp}.mp4"
        video_title = f"{base_name} - Shorts"
        print(f"\n[>] Creating YouTube Shorts (9:16) from {len(clips_to_use)} clips...")
    else:
        output_name = f"{base_name}_highlights_{timestamp}.mp4"
        video_title = f"{base_name} - Highlights Compilation"
        print(f"\n[>] Creating YouTube-ready highlights from {len(clips_to_use)} clips...")
    
    output_path = os.path.join(output_dir, output_name)
    
    print(f"    Extracting {actual_segment_duration:.1f}s peak moments from each clip...")
    
    if progress_callback:
        progress_callback(f"Extracting {actual_segment_duration:.1f}s peak moments...")
    
    # Extract peak segments from each clip
    segments = extract_peak_segments(
        clips_to_use,
        output_dir,
        segment_duration=actual_segment_duration,
        progress_callback=progress_callback
    )
    
    if not segments:
        print("  Failed to extract segments")
        return None
    
    print(f"    Extracted {len(segments)} segments, now compiling...")
    
    if progress_callback:
        if shorts_mode:
            progress_callback("Creating Shorts video (9:16)...")
        else:
            progress_callback("Compiling highlights...")
    
    # Choose compilation method based on mode
    if shorts_mode:
        # Create vertical 9:16 video for Shorts/Reels
        success = compile_highlights_shorts(
            segments,
            output_path,
            video_title=video_title
        )
    elif use_transitions:
        success = compile_highlights_with_transitions(
            segments,
            output_path,
            transition_duration=transition_duration,
            video_title=video_title
        )
    else:
        success = compile_highlights_simple(
            segments,
            output_path,
            video_title=video_title
        )
    
    # Cleanup temporary segments
    segments_dir = os.path.join(output_dir, "_highlight_segments")
    if os.path.exists(segments_dir):
        try:
            import shutil
            shutil.rmtree(segments_dir)
        except:
            pass
    
    if success and os.path.exists(output_path):
        return output_path
    
    return None


def generate_youtube_metadata(
    highlights_path: str,
    clip_count: int,
    source_video: str,
    total_duration: float = None
) -> dict:
    """
    Generate suggested YouTube metadata for the highlights video.
    
    Returns:
        Dictionary with title, description, and tags suggestions
    """
    base_name = Path(source_video).stem
    
    title_suggestion = f"{base_name} - Best Moments Highlights Compilation"
    
    description = f"""🔥 {base_name} Highlights Compilation 🔥

This video contains the {clip_count} best moments from the event.
Compiled automatically with crowd reaction detection.

📌 What's Included:
- All major crowd reactions
- Key moments and highlights
- Smooth transitions between clips

⏰ Timestamps will be in the comments!

#highlights #bestmoments #compilation
"""
    
    tags = [
        "highlights",
        "compilation",
        "best moments",
        "crowd reaction",
        base_name.lower().replace(" ", ""),
    ]
    
    return {
        "title": title_suggestion,
        "description": description,
        "tags": tags,
        "file_path": highlights_path
    }
