"""
Crowd Clipper - Video Highlights Tool
Standalone launcher for the GUI application.
"""
import sys
import os

# Add the parent directory to the path
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    application_path = os.path.dirname(sys.executable)
else:
    # Running as script
    application_path = os.path.dirname(os.path.abspath(__file__))

# Launch the GUI
from crowd_clipper.gui import CrowdClipperApp

if __name__ == "__main__":
    app = CrowdClipperApp()
    app.mainloop()
