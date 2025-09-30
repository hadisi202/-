import subprocess
import sys


def speak(text: str):
    """Speak the given Chinese text using Windows PowerShell TTS.

    Falls back silently if not on Windows or PowerShell fails.
    """
    if not text:
        return

    # Only attempt on Windows
    if sys.platform != 'win32':
        return

    # Use .NET System.Speech.Synthesis via PowerShell without opening a window
    # Avoid blocking the UI thread by not waiting for completion.
    ps_command = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        # Use default voice; can customize rate/volume here if needed
        f"$s.Rate = 0; $s.Volume = 100; $s.Speak('{text}');"
    )

    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
    except Exception:
        # Silently ignore to avoid breaking main workflow
        pass