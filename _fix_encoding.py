
import pathlib, base64, re

ROOT = pathlib.Path("D:/tex_agent/Tex_Agent")
STATIC = ROOT / "ui" / "overleaf" / "static"

# Chinese text replacements for index.html
cn_index = {
    b"???": b""
}
