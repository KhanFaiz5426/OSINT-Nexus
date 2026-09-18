import cairosvg
from PIL import Image
import io

svg_content = """<svg width="1024" height="1024" viewBox="192 192 640 640" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bladeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#33E6FF"/>
      <stop offset="100%" stop-color="#3457E8"/>
    </linearGradient>
    <linearGradient id="nodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#33E6FF"/>
      <stop offset="100%" stop-color="#3457E8"/>
    </linearGradient>
  </defs>
  <!-- Structural hex frame: the network -->
  <polygon points="512,212 771.8,362 771.8,662 512,812 252.2,662 252.2,362"
           fill="none" stroke="#101A2E" stroke-width="15" stroke-linejoin="miter"/>
  <!-- Six source nodes feeding the nexus -->
  <g fill="url(#nodeGrad)">
    <circle cx="512" cy="212" r="20"/>
    <circle cx="771.8" cy="362" r="20"/>
    <circle cx="771.8" cy="662" r="20"/>
    <circle cx="512" cy="812" r="20"/>
    <circle cx="252.2" cy="662" r="20"/>
    <circle cx="252.2" cy="362" r="20"/>
  </g>
  <!-- Open aperture: six blades converging, center left transparent ("open" source) -->
  <g fill="url(#bladeGrad)">
    <polygon points="444.6,345.1 579.4,345.1 512,452"/>
    <polygon points="622.8,370.15 690.2,486.92 563.96,482"/>
    <polygon points="690.2,537.08 622.8,653.82 563.96,542"/>
    <polygon points="579.4,678.9 444.6,678.9 512,572"/>
    <polygon points="401.2,653.82 333.8,537.08 460.04,542"/>
    <polygon points="333.8,486.92 401.2,370.18 460.04,482"/>
  </g>
</svg>"""

png_data = cairosvg.svg2png(bytestring=svg_content.encode('utf-8'), output_width=256, output_height=256)
img = Image.open(io.BytesIO(png_data))
img.save("app/icon.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Icon updated successfully.")
