"""
Main CLI interface for Crowd Audio Clip Detector.

Usage:
    python -m crowd_clipper.main VIDEO_PATH [OPTIONS]
"""

import argparse
import sys
from pathlib import Path

from .audio_analyzer import analyze_video_audio
from .spike_detector import detect_spikes, merge_nearby_spikes, filter_spikes
from .clip_extractor import create_clips, export_all_clips
from .highlights_compiler import compile_highlights, generate_youtube_metadata


def print_banner():
    """Print tool banner."""
    print("\n" + "=" * 60)
    print("  [*] Crowd Audio Clip Detector")
    print("  Automatically find exciting moments in videos")
    print("=" * 60 + "\n")


def progress_callback(current: int, total: int):
    """Print export progress."""
    print(f"  Exporting clip {current}/{total}...")


def main():
    parser = argparse.ArgumentParser(
        description="Automatically detect and clip exciting moments based on crowd audio."
    )
    
    parser.add_argument(
        "video",
        type=str,
        help="Path to input video file"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./clips",
        help="Output directory for clips (default: ./clips)"
    )
    
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=1.5,
        help="Spike detection threshold multiplier (default: 2.0)"
    )
    
    parser.add_argument(
        "--pre-roll",
        type=float,
        default=5.0,
        help="Seconds before spike to start clip (default: 5.0)"
    )
    
    parser.add_argument(
        "--post-roll",
        type=float,
        default=3.0,
        help="Seconds after spike to end clip (default: 3.0)"
    )
    
    parser.add_argument(
        "--min-duration",
        type=float,
        default=5.0,
        help="Minimum clip duration in seconds (default: 5)"
    )
    
    parser.add_argument(
        "--max-duration",
        type=float,
        default=15.0,
        help="Maximum clip duration in seconds (default: 15)"
    )
    
    parser.add_argument(
        "--max-clips", "-n",
        type=int,
        default=99999,
        help="Maximum number of clips to extract (default: unlimited)"
    )
    
    parser.add_argument(
        "--min-spike-duration",
        type=float,
        default=0.5,
        help="Minimum spike duration to consider (default: 0.5s)"
    )
    
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=0.0,
        help="Merge spikes within this gap in seconds (default: 0 = no merge)"
    )
    
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Re-encode clips for precise cuts (slower)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed information"
    )
    
    # YouTube Highlights options
    parser.add_argument(
        "--highlights",
        action="store_true",
        help="Create a highlights compilation video from all clips (YouTube-ready)"
    )
    
    parser.add_argument(
        "--transition",
        type=float,
        default=0.5,
        help="Transition duration between clips in seconds (default: 0.5)"
    )
    
    parser.add_argument(
        "--no-transitions",
        action="store_true",
        help="Disable transitions in highlights video (faster)"
    )
    
    parser.add_argument(
        "--segment-duration",
        type=float,
        default=5.0,
        help="Duration of peak moment to extract from each clip for highlights (default: 5s)"
    )
    
    args = parser.parse_args()
    
    # Validate input
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    print_banner()
    
    # Step 1: Analyze audio
    print(f"[>] Analyzing: {video_path.name}")
    print("  Extracting and analyzing audio...")
    
    try:
        analysis = analyze_video_audio(str(video_path))
    except Exception as e:
        print(f"\nError analyzing video: {e}")
        sys.exit(1)
    
    print(f"  Duration: {analysis['duration']:.1f} seconds")
    
    # Step 2: Detect spikes
    print("\n[>] Detecting crowd reactions...")
    
    spikes = detect_spikes(
        analysis['energy'],
        analysis['times'],
        analysis['baseline'],
        threshold_multiplier=args.threshold,
        min_duration=args.min_spike_duration,
        derivative=analysis.get('derivative')
    )
    
    print(f"  Found {len(spikes)} initial spikes")
    
    # Merge nearby spikes
    spikes = merge_nearby_spikes(spikes, min_gap_seconds=args.merge_gap)
    print(f"  After merging: {len(spikes)} events")
    
    # Filter and rank
    spikes = filter_spikes(
        spikes,
        min_duration=args.min_spike_duration,
        max_count=args.max_clips * 2  # Get extra for overlap filtering
    )
    print(f"  Top moments: {len(spikes)}")
    
    if not spikes:
        print("\n[!] No exciting moments detected. Try lowering --threshold.")
        sys.exit(0)
    
    # Step 3: Create clips
    print("\n[>] Creating clips...")
    
    clips = create_clips(
        spikes,
        analysis['energy'],
        analysis['times'],
        analysis['baseline'],
        pre_roll=args.pre_roll,
        post_roll=args.post_roll,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        max_clips=args.max_clips
    )
    
    print(f"  Will create {len(clips)} clips:")
    
    for clip in clips:
        duration = clip.end_time - clip.start_time
        print(f"    • {clip.start_time:.1f}s - {clip.end_time:.1f}s ({duration:.1f}s) | Score: {clip.spike.score:.1f}")
    
    # Step 4: Export clips
    print(f"\n[>] Exporting to: {args.output_dir}")
    
    exported = export_all_clips(
        str(video_path),
        clips,
        args.output_dir,
        reencode=args.reencode,
        progress_callback=progress_callback
    )
    
    # Summary
    print("\n" + "=" * 60)
    print(f"[OK] Done! Exported {len(exported)} clips to {args.output_dir}")
    print("=" * 60 + "\n")
    
    if args.verbose:
        print("Exported files:")
        for path in exported:
            print(f"  • {path}")
    
    # Step 5: Create highlights compilation if requested
    if args.highlights and exported:
        print("\n" + "=" * 60)
        print("  [*] YouTube Highlights Compilation")
        print("=" * 60)
        
        highlights_path = compile_highlights(
            exported,
            args.output_dir,
            video_path.name,
            use_transitions=not args.no_transitions,
            transition_duration=args.transition,
            segment_duration=args.segment_duration
        )
        
        if highlights_path:
            print(f"\n[OK] Highlights video created: {highlights_path}")
            
            # Generate YouTube metadata suggestions
            metadata = generate_youtube_metadata(
                highlights_path,
                len(exported),
                video_path.name
            )
            
            print("\n" + "-" * 40)
            print("  YouTube Upload Suggestions:")
            print("-" * 40)
            print(f"  Title: {metadata['title']}")
            print(f"  Tags: {', '.join(metadata['tags'])}")
            print("\n  (See console output for full description)")
            
            if args.verbose:
                print("\n  Description:")
                print(metadata['description'])
        else:
            print("\n[!] Failed to create highlights video")


if __name__ == "__main__":
    main()
