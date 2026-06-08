"""Quick start for the Overleaf-style LaTeX Editor.
Usage: python overleaf.py
"""
from __future__ import annotations
import sys, os

def main():
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:]):
            if arg == "--port" and i + 1 < len(sys.argv[1:]):
                os.environ["OVERLEAF_PORT"] = sys.argv[2 + i]
            if arg == "--host":
                os.environ["OVERLEAF_HOST"] = sys.argv[2 + i]
    from ui.overleaf.server import main as server_main
    print("=" * 50)
    print("  TeX Agent Overleaf - LaTeX Editor with AI Support")
    print("=" * 50)
    server_main()

if __name__ == "__main__":
    main()
