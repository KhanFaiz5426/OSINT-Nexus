import pymupdf
from PIL import Image
import io

svg_content = """<svg width="1024" height="1024" viewBox="162 162 700 700" xmlns="http://www.w3.org/2000/svg">
  <!-- Background to make it a full app icon -->
  <rect x="162" y="162" width="700" height="700" rx="150" fill="#0B1120"/>
  <!-- Structural hex frame: the network -->
  <polygon points="512,212 771.8,362 771.8,662 512,812 252.2,662 252.2,362"
           fill="none" stroke="#475569" stroke-width="15" stroke-linejoin="miter"/>
  <!-- Six source nodes feeding the nexus -->
  <g fill="#33E6FF">
    <circle cx="512" cy="212" r="20"/>
    <circle cx="771.8" cy="362" r="20"/>
    <circle cx="771.8" cy="662" r="20"/>
    <circle cx="512" cy="812" r="20"/>
    <circle cx="252.2" cy="662" r="20"/>
    <circle cx="252.2" cy="362" r="20"/>
  </g>
  <!-- Open aperture: six blades converging, center left transparent ("open" source) -->
  <g fill="#3B82F6">
    <polygon points="444.6,345.1 579.4,345.1 512,452"/>
    <polygon points="622.8,370.15 690.2,486.92 563.96,482"/>
    <polygon points="690.2,537.08 622.8,653.82 563.96,542"/>
    <polygon points="579.4,678.9 444.6,678.9 512,572"/>
    <polygon points="401.2,653.82 333.8,537.08 460.04,542"/>
    <polygon points="333.8,486.92 401.2,370.18 460.04,482"/>
  </g>
</svg>"""

try:
    doc = pymupdf.open(stream=svg_content.encode("utf-8"), filetype="svg")
    page = doc[0]
    pix = page.get_pixmap(alpha=True, matrix=pymupdf.Matrix(256/1024, 256/1024))
    png_data = pix.tobytes("png")

    img = Image.open(io.BytesIO(png_data))
    img.save("app/icon.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Icon updated successfully.")
except Exception as e:
    print(f"Error: {e}")
