"""
Professional GUI for Crowd Clipper Pro.

Modern dark-themed application for extracting exciting moments from videos
and creating YouTube-ready highlights compilations.

Two modes:
1. Full Processing - Analyze video and extract clips
2. Highlights Only - Create compilation from existing clips
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
from pathlib import Path
from typing import Optional, List
import glob


class CrowdClipperApp(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("🎬 Crowd Clipper Pro")
        self.geometry("700x750")
        self.minsize(650, 700)
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Variables - DoubleVar for sliders, StringVar for entry-only fields
        self.video_path = ctk.StringVar()
        self.clips_folder = ctk.StringVar()
        self.output_dir = ctk.StringVar(value="./clips")
        # Slider variables (need DoubleVar)
        self.threshold = ctk.DoubleVar(value=1.3)
        self.pre_roll = ctk.DoubleVar(value=5.0)
        self.post_roll = ctk.DoubleVar(value=3.0)
        self.min_duration = ctk.DoubleVar(value=5.0)
        self.max_duration = ctk.DoubleVar(value=60.0)
        self.create_highlights = ctk.BooleanVar(value=True)
        self.use_transitions = ctk.BooleanVar(value=True)
        # Entry-only fields (can use StringVar for flexibility)
        self.transition_duration = ctk.StringVar(value="0.5")
        self.segment_duration = ctk.StringVar(value="5.0")
        self.video_format = ctk.StringVar(value="long")  # "long" (16:9) or "shorts" (9:16)
        self.shorts_target_duration = ctk.StringVar(value="60.0")  # Target Shorts length in seconds
        
        self.processing = False
        self.current_mode = "full"  # "full" or "highlights"
        
        # Build UI
        self._create_ui()
    
    def _get_float(self, var, default=0.0):
        """Safely get float value from StringVar with default fallback."""
        try:
            val = var.get().strip()
            return float(val) if val else default
        except (ValueError, AttributeError):
            return default
    
    def _create_ui(self):
        """Create the main UI layout."""
        # Main container with padding
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        self._create_header()
        
        # Mode selector tabs
        self._create_mode_tabs()
        
        # Content frame (changes based on mode) - Scrollable to fit all content
        self.content_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.content_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        # Show full processing mode by default
        self._show_full_mode()
    
    def _create_header(self):
        """Create application header."""
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        title = ctk.CTkLabel(
            header_frame,
            text="🎬 Crowd Clipper Pro",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title.pack(side="left")
        
        subtitle = ctk.CTkLabel(
            header_frame,
            text="Extract exciting moments & create highlights",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        subtitle.pack(side="left", padx=(15, 0), pady=(8, 0))
    
    def _create_mode_tabs(self):
        """Create mode selection tabs."""
        tabs_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        tabs_frame.pack(fill="x")
        
        self.full_mode_btn = ctk.CTkButton(
            tabs_frame,
            text="📹 Full Processing",
            command=self._show_full_mode,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.full_mode_btn.pack(side="left", padx=(0, 10))
        
        self.highlights_mode_btn = ctk.CTkButton(
            tabs_frame,
            text="✨ Highlights Only",
            command=self._show_highlights_mode,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="gray30",
            hover_color="gray40"
        )
        self.highlights_mode_btn.pack(side="left")
    
    def _show_full_mode(self):
        """Show full processing mode UI."""
        self.current_mode = "full"
        
        # Update tab buttons
        self.full_mode_btn.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self.highlights_mode_btn.configure(fg_color="gray30")
        
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Video Input Section
        self._create_video_input_section()
        
        # Settings Section
        self._create_settings_section()
        
        # Output Section
        self._create_output_section()
        
        # Highlights Options
        self._create_highlights_options()
        
        # Progress Section
        self._create_progress_section()
        
        # Action Buttons
        self._create_action_buttons()
    
    def _show_highlights_mode(self):
        """Show highlights-only mode UI."""
        self.current_mode = "highlights"
        
        # Update tab buttons
        self.full_mode_btn.configure(fg_color="gray30")
        self.highlights_mode_btn.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Clips Folder Selection
        self._create_clips_folder_section()
        
        # Highlights Options
        self._create_highlights_options()
        
        # Progress Section
        self._create_progress_section()
        
        # Action Buttons
        self._create_action_buttons()
    
    def _create_video_input_section(self):
        """Create video input section."""
        section = ctk.CTkFrame(self.content_frame)
        section.pack(fill="x", pady=(0, 10))
        
        label = ctk.CTkLabel(
            section,
            text="📹 Video Input",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        input_frame = ctk.CTkFrame(section, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.video_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.video_path,
            placeholder_text="Select video file...",
            height=40
        )
        self.video_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        browse_btn = ctk.CTkButton(
            input_frame,
            text="📂 Browse",
            command=self._browse_video,
            width=100,
            height=40
        )
        browse_btn.pack(side="right")
        
        # Video info label
        self.video_info_label = ctk.CTkLabel(
            section,
            text="No video selected",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.video_info_label.pack(anchor="w", padx=15, pady=(0, 10))
    
    def _create_clips_folder_section(self):
        """Create clips folder selection section."""
        section = ctk.CTkFrame(self.content_frame)
        section.pack(fill="x", pady=(0, 10))
        
        label = ctk.CTkLabel(
            section,
            text="📁 Clips Folder",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        desc = ctk.CTkLabel(
            section,
            text="Select a folder containing existing video clips to merge into highlights",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        desc.pack(anchor="w", padx=15, pady=(0, 5))
        
        input_frame = ctk.CTkFrame(section, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.clips_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.clips_folder,
            placeholder_text="Select clips folder...",
            height=40
        )
        self.clips_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        browse_btn = ctk.CTkButton(
            input_frame,
            text="📂 Browse",
            command=self._browse_clips_folder,
            width=100,
            height=40
        )
        browse_btn.pack(side="right")
        
        # Clips info label
        self.clips_info_label = ctk.CTkLabel(
            section,
            text="No folder selected",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.clips_info_label.pack(anchor="w", padx=15, pady=(0, 10))
    
    def _create_settings_section(self):
        """Create settings section with sliders."""
        section = ctk.CTkFrame(self.content_frame)
        section.pack(fill="x", pady=(0, 10))
        
        label = ctk.CTkLabel(
            section,
            text="⚙️ Detection Settings",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        label.pack(anchor="w", padx=15, pady=(10, 10))
        
        # Threshold slider
        self._create_slider_row(
            section, "Threshold:", self.threshold,
            0.5, 3.0, "Sensitivity (lower = more clips)"
        )
        
        # Pre-roll slider
        self._create_slider_row(
            section, "Pre-roll:", self.pre_roll,
            1.0, 10.0, "Seconds before event"
        )
        
        # Post-roll slider
        self._create_slider_row(
            section, "Post-roll:", self.post_roll,
            1.0, 10.0, "Seconds after event"
        )
        
        # Duration settings
        duration_frame = ctk.CTkFrame(section, fg_color="transparent")
        duration_frame.pack(fill="x", padx=15, pady=(5, 10))
        
        ctk.CTkLabel(duration_frame, text="Min Duration:").pack(side="left")
        ctk.CTkEntry(
            duration_frame, textvariable=self.min_duration, width=60
        ).pack(side="left", padx=(5, 20))
        
        ctk.CTkLabel(duration_frame, text="Max Duration:").pack(side="left")
        ctk.CTkEntry(
            duration_frame, textvariable=self.max_duration, width=60
        ).pack(side="left", padx=(5, 0))
        
        ctk.CTkLabel(
            duration_frame, text="seconds", text_color="gray"
        ).pack(side="left", padx=(10, 0))
    
    def _create_slider_row(self, parent, label_text, variable, min_val, max_val, tooltip):
        """Create a slider row with label and value display."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=3)
        
        label = ctk.CTkLabel(frame, text=label_text, width=80, anchor="w")
        label.pack(side="left")
        
        slider = ctk.CTkSlider(
            frame,
            from_=min_val,
            to=max_val,
            variable=variable,
            width=200
        )
        slider.pack(side="left", padx=10)
        
        value_label = ctk.CTkLabel(
            frame,
            textvariable=variable,
            width=40
        )
        value_label.pack(side="left")
        
        tip_label = ctk.CTkLabel(
            frame,
            text=tooltip,
            text_color="gray",
            font=ctk.CTkFont(size=10)
        )
        tip_label.pack(side="left", padx=(15, 0))
    
    def _create_output_section(self):
        """Create output directory section."""
        section = ctk.CTkFrame(self.content_frame)
        section.pack(fill="x", pady=(0, 10))
        
        label = ctk.CTkLabel(
            section,
            text="📁 Output Directory",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        input_frame = ctk.CTkFrame(section, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        output_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.output_dir,
            height=35
        )
        output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        browse_btn = ctk.CTkButton(
            input_frame,
            text="📂",
            command=self._browse_output,
            width=50,
            height=35
        )
        browse_btn.pack(side="right")
    
    def _create_highlights_options(self):
        """Create highlights compilation options."""
        section = ctk.CTkFrame(self.content_frame)
        section.pack(fill="x", pady=(0, 10))
        
        label = ctk.CTkLabel(
            section,
            text="✨ YouTube Highlights",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        # First row: checkboxes and format selection
        options_frame = ctk.CTkFrame(section, fg_color="transparent")
        options_frame.pack(fill="x", padx=15, pady=(0, 5))
        
        if self.current_mode == "full":
            highlights_check = ctk.CTkCheckBox(
                options_frame,
                text="Create highlights",
                variable=self.create_highlights
            )
            highlights_check.pack(side="left", padx=(0, 10))
        
        transitions_check = ctk.CTkCheckBox(
            options_frame,
            text="Fade",
            variable=self.use_transitions
        )
        transitions_check.pack(side="left", padx=(0, 15))
        
        # Format selection with radio buttons
        format_label = ctk.CTkLabel(
            options_frame,
            text="Format:",
            font=ctk.CTkFont(weight="bold")
        )
        format_label.pack(side="left", padx=(10, 5))
        
        long_radio = ctk.CTkRadioButton(
            options_frame,
            text="Long",
            variable=self.video_format,
            value="long"
        )
        long_radio.pack(side="left", padx=(0, 10))
        
        shorts_radio = ctk.CTkRadioButton(
            options_frame,
            text="Shorts",
            variable=self.video_format,
            value="shorts",
            text_color="#FF0000"  # YouTube red
        )
        shorts_radio.pack(side="left", padx=(0, 10))
        
        # Shorts target duration
        ctk.CTkLabel(options_frame, text=":", text_color="#FF0000").pack(side="left")
        ctk.CTkEntry(
            options_frame,
            textvariable=self.shorts_target_duration,
            width=40,
            border_color="#FF0000"
        ).pack(side="left", padx=(3, 3))
        ctk.CTkLabel(options_frame, text="s", text_color="gray").pack(side="left")
        
        # Second row for durations (Long mode settings)
        duration_frame = ctk.CTkFrame(section, fg_color="transparent")
        duration_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        ctk.CTkLabel(duration_frame, text="Transition:").pack(side="left")
        ctk.CTkEntry(
            duration_frame,
            textvariable=self.transition_duration,
            width=40
        ).pack(side="left", padx=(3, 15))
        
        ctk.CTkLabel(duration_frame, text="Segment (Long):").pack(side="left")
        ctk.CTkEntry(
            duration_frame,
            textvariable=self.segment_duration,
            width=40
        ).pack(side="left", padx=(3, 3))
        ctk.CTkLabel(duration_frame, text="s", text_color="gray").pack(side="left")
    
    def _create_progress_section(self):
        """Create progress tracking section with real-time details."""
        section = ctk.CTkFrame(self.content_frame)
        section.pack(fill="x", pady=(0, 10))
        
        label = ctk.CTkLabel(
            section,
            text="📊 Real-Time Progress",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        label.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Current step
        self.step_label = ctk.CTkLabel(
            section,
            text="Step: Ready",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3B8ED0"
        )
        self.step_label.pack(anchor="w", padx=15, pady=(0, 3))
        
        # Status detail
        self.status_label = ctk.CTkLabel(
            section,
            text="Waiting to start...",
            font=ctk.CTkFont(size=11)
        )
        self.status_label.pack(anchor="w", padx=15, pady=(0, 5))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(section, height=15)
        self.progress_bar.pack(padx=15, pady=(0, 5), fill="x")
        self.progress_bar.set(0)
        
        # Stats row
        stats_frame = ctk.CTkFrame(section, fg_color="transparent")
        stats_frame.pack(fill="x", padx=15, pady=(0, 5))
        
        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="Clips: 0 | Exported: 0",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.stats_label.pack(side="left")
        
        self.time_label = ctk.CTkLabel(
            stats_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.time_label.pack(side="right")
        
        # Current file being processed
        self.current_file_label = ctk.CTkLabel(
            section,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.current_file_label.pack(anchor="w", padx=15, pady=(0, 10))
    
    def _create_action_buttons(self):
        """Create action buttons."""
        buttons_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=(10, 0))
        
        self.start_btn = ctk.CTkButton(
            buttons_frame,
            text="🚀 Start Processing",
            command=self._start_processing,
            width=200,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2ECC71",
            hover_color="#27AE60"
        )
        self.start_btn.pack(side="left", padx=(0, 10))
        
        open_btn = ctk.CTkButton(
            buttons_frame,
            text="📂 Open Output",
            command=self._open_output,
            width=150,
            height=45,
            font=ctk.CTkFont(size=14),
            fg_color="gray30",
            hover_color="gray40"
        )
        open_btn.pack(side="left")
    
    # === Event Handlers ===
    
    def _browse_video(self):
        """Browse for video file."""
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.video_path.set(path)
            self._update_video_info(path)
    
    def _browse_clips_folder(self):
        """Browse for clips folder."""
        path = filedialog.askdirectory(title="Select Clips Folder")
        if path:
            self.clips_folder.set(path)
            self._update_clips_info(path)
    
    def _browse_output(self):
        """Browse for output directory."""
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir.set(path)
    
    def _update_video_info(self, path: str):
        """Update video info display."""
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            name = os.path.basename(path)
            self.video_info_label.configure(
                text=f"📄 {name} | {size_mb:.1f} MB"
            )
        except Exception:
            self.video_info_label.configure(text="Unable to read video info")
    
    def _update_clips_info(self, path: str):
        """Update clips folder info."""
        try:
            clips = glob.glob(os.path.join(path, "*.mp4"))
            clips.extend(glob.glob(os.path.join(path, "*.mkv")))
            clips.extend(glob.glob(os.path.join(path, "*.avi")))
            self.clips_info_label.configure(
                text=f"📁 Found {len(clips)} video clips"
            )
        except Exception:
            self.clips_info_label.configure(text="Unable to read folder")
    
    def _open_output(self):
        """Open output directory."""
        output = os.path.abspath(self.output_dir.get())
        if os.path.exists(output):
            os.startfile(output)
        else:
            # Create the directory if it doesn't exist
            os.makedirs(output, exist_ok=True)
            os.startfile(output)
    
    def _start_processing(self):
        """Start processing in background thread."""
        if self.processing:
            return
        
        if self.current_mode == "full":
            video = self.video_path.get()
            if not video or not os.path.exists(video):
                messagebox.showerror("Error", "Please select a valid video file")
                return
        else:
            clips_dir = self.clips_folder.get()
            if not clips_dir or not os.path.exists(clips_dir):
                messagebox.showerror("Error", "Please select a valid clips folder")
                return
        
        self.processing = True
        self.start_btn.configure(state="disabled", text="⏳ Processing...")
        
        # Run in background thread
        thread = threading.Thread(target=self._run_processing, daemon=True)
        thread.start()
    
    def _run_processing(self):
        """Run the actual processing (in background thread)."""
        import time
        self.start_time = time.time()
        
        try:
            if self.current_mode == "full":
                self._run_full_processing()
            else:
                self._run_highlights_only()
        except Exception as e:
            self._update_step("❌ Error")
            self._update_status(f"Error: {str(e)}")
        finally:
            self.processing = False
            self.after(0, lambda: self.start_btn.configure(
                state="normal", text="🚀 Start Processing"
            ))
    
    def _run_full_processing(self):
        """Run full video processing with real-time updates."""
        import time
        from .audio_analyzer import analyze_video_audio
        from .spike_detector import detect_spikes, merge_nearby_spikes, filter_spikes
        from .clip_extractor import create_clips, export_all_clips
        from .highlights_compiler import compile_highlights
        
        video_path = self.video_path.get()
        output_dir = self.output_dir.get()
        
        # Step 1: Analyze audio
        self._update_step("1/5 Analyzing Audio")
        self._update_status("Extracting and analyzing audio frequencies...")
        self._update_current_file(f"📄 {os.path.basename(video_path)}")
        self._update_progress(0.05)
        self._update_time(time.time() - self.start_time)
        
        analysis = analyze_video_audio(video_path)
        self._update_time(time.time() - self.start_time)
        
        # Step 2: Detect spikes
        self._update_step("2/5 Detecting Moments")
        self._update_status("Finding crowd reactions and exciting moments...")
        self._update_progress(0.2)
        self._update_time(time.time() - self.start_time)
        
        spikes = detect_spikes(
            analysis['energy'],
            analysis['times'],
            analysis['baseline'],
            threshold_multiplier=self.threshold.get(),
            min_duration=0.5,
            derivative=analysis.get('derivative')
        )
        
        spikes = filter_spikes(spikes, min_duration=0.5, max_count=99999)
        self._update_stats(f"Moments: {len(spikes)} | Exported: 0")
        self._update_time(time.time() - self.start_time)
        
        if not spikes:
            self._update_step("⚠️ No Moments Found")
            self._update_status("No exciting moments found. Try lowering threshold.")
            self._update_progress(1.0)
            return
        
        # Step 3: Create clips
        self._update_step("3/5 Creating Clips")
        self._update_status(f"Preparing {len(spikes)} clip boundaries...")
        self._update_progress(0.3)
        self._update_time(time.time() - self.start_time)
        
        clips = create_clips(
            spikes,
            analysis['energy'],
            analysis['times'],
            analysis['baseline'],
            pre_roll=self.pre_roll.get(),
            post_roll=self.post_roll.get(),
            min_duration=self.min_duration.get(),
            max_duration=self.max_duration.get(),
            max_clips=99999
        )
        
        # Step 4: Export clips
        self._update_step("4/5 Exporting Clips")
        self._update_status("Extracting video segments...")
        self._update_time(time.time() - self.start_time)
        
        def progress_cb(current, total):
            progress = 0.35 + (current / total) * 0.45
            self._update_progress(progress)
            self._update_stats(f"Clips: {len(clips)} | Exporting: {current}/{total}")
            self._update_current_file(f"📹 Clip {current}/{total}")
            self._update_time(time.time() - self.start_time)
        
        exported = export_all_clips(
            video_path,
            clips,
            output_dir,
            reencode=False,
            progress_callback=progress_cb
        )
        
        # Step 5: Create highlights
        if self.create_highlights.get() and exported:
            is_shorts = self.video_format.get() == "shorts"
            if is_shorts:
                self._update_step("5/5 Creating Shorts (9:16)")
                self._update_status(f"Creating {self._get_float(self.shorts_target_duration, 60.0)}s Shorts video...")
            else:
                self._update_step("5/5 Creating Highlights")
                self._update_status(f"Extracting {self._get_float(self.segment_duration, 5.0)}s peak moments...")
            self._update_progress(0.85)
            self._update_time(time.time() - self.start_time)
            
            highlights_path = compile_highlights(
                exported,
                output_dir,
                os.path.basename(video_path),
                use_transitions=self.use_transitions.get(),
                transition_duration=self._get_float(self.transition_duration, 0.5),
                segment_duration=self._get_float(self.segment_duration, 5.0),
                shorts_mode=is_shorts,
                target_duration=self._get_float(self.shorts_target_duration, 60.0) if is_shorts else 0
            )
            
            self._update_time(time.time() - self.start_time)
            
            if highlights_path:
                self._update_step("✅ Complete")
                self._update_status(f"Done! {len(exported)} clips + highlights video created")
                self._update_current_file(f"📁 {os.path.basename(highlights_path)}")
            else:
                self._update_step("✅ Partial Complete")
                self._update_status(f"Done! {len(exported)} clips (highlights failed)")
        else:
            self._update_step("✅ Complete")
            self._update_status(f"Done! Exported {len(exported)} clips")
        
        self._update_progress(1.0)
        self._update_stats(f"Clips: {len(clips)} | Exported: {len(exported)}")
    
    def _run_highlights_only(self):
        """Run highlights compilation only with real-time updates."""
        import time
        from .highlights_compiler import compile_highlights
        
        clips_dir = self.clips_folder.get()
        
        # Step 1: Find all video clips
        self._update_step("1/2 Finding Clips")
        self._update_status("Scanning folder for video files...")
        self._update_progress(0.1)
        self._update_time(time.time() - self.start_time)
        
        clips = []
        for ext in ['*.mp4', '*.mkv', '*.avi', '*.mov']:
            clips.extend(glob.glob(os.path.join(clips_dir, ext)))
        
        if not clips:
            self._update_step("⚠️ No Clips Found")
            self._update_status("No video clips found in folder")
            self._update_progress(1.0)
            return
        
        clips = sorted(clips)
        self._update_stats(f"Clips: {len(clips)} | Processing...")
        self._update_current_file(f"📁 {os.path.basename(clips_dir)}")
        self._update_time(time.time() - self.start_time)
        
        # Step 2: Create highlights
        is_shorts = self.video_format.get() == "shorts"
        if is_shorts:
            self._update_step("2/2 Creating Shorts (9:16)")
            self._update_status(f"Creating {self._get_float(self.shorts_target_duration, 60.0)}s Shorts from {len(clips)} clips...")
        else:
            self._update_step("2/2 Creating Highlights")
            self._update_status(f"Extracting {self._get_float(self.segment_duration, 5.0)}s from each clip...")
        self._update_progress(0.3)
        self._update_time(time.time() - self.start_time)
        
        highlights_path = compile_highlights(
            clips,
            clips_dir,
            "compilation",
            use_transitions=self.use_transitions.get(),
            transition_duration=self._get_float(self.transition_duration, 0.5),
            segment_duration=self._get_float(self.segment_duration, 5.0),
            shorts_mode=is_shorts,
            target_duration=self._get_float(self.shorts_target_duration, 60.0) if is_shorts else 0
        )
        
        self._update_time(time.time() - self.start_time)
        
        if highlights_path:
            self._update_step("✅ Complete")
            if is_shorts:
                self._update_status(f"Done! Created Shorts video from {len(clips)} clips")
            else:
                self._update_status(f"Done! Created highlights from {len(clips)} clips")
            self._update_current_file(f"📁 {os.path.basename(highlights_path)}")
        else:
            self._update_step("❌ Failed")
            self._update_status("Failed to create video")
        
        self._update_progress(1.0)
    
    def _update_status(self, text: str):
        """Update status label (thread-safe)."""
        self.after(0, lambda: self.status_label.configure(text=text))
    
    def _update_step(self, text: str):
        """Update step label (thread-safe)."""
        self.after(0, lambda: self.step_label.configure(text=f"Step: {text}"))
    
    def _update_progress(self, value: float):
        """Update progress bar (thread-safe)."""
        self.after(0, lambda: self.progress_bar.set(value))
    
    def _update_stats(self, text: str):
        """Update stats label (thread-safe)."""
        self.after(0, lambda: self.stats_label.configure(text=text))
    
    def _update_time(self, elapsed: float):
        """Update time label (thread-safe)."""
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        self.after(0, lambda: self.time_label.configure(text=f"⏱️ {mins:02d}:{secs:02d}"))
    
    def _update_current_file(self, text: str):
        """Update current file label (thread-safe)."""
        self.after(0, lambda: self.current_file_label.configure(text=text))


def main():
    """Launch the GUI application."""
    app = CrowdClipperApp()
    app.mainloop()


if __name__ == "__main__":
    main()
