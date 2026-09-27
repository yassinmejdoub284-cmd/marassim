"""Package the unchanged source logo into standard application icon canvases."""
import base64
from pathlib import Path
from PIL import Image
root=Path(__file__).resolve().parents[1]
public=root/'public'; public.mkdir(exist_ok=True)
source=root/'assets/marassim-logo.png'
logo=Image.open(source).convert('RGBA')
for size in (256,512):
    canvas=Image.new('RGBA',(size,size),'white')
    # Keep the original mark proportions; reserve a mask-safe border.
    image=logo.copy(); image.thumbnail((int(size*.6),int(size*.6)),Image.Resampling.LANCZOS)
    if size==512: image=logo.resize((312,296),Image.Resampling.LANCZOS)
    canvas.alpha_composite(image,((size-image.width)//2,(size-image.height)//2))
    canvas.convert('RGB').save(public/f'icon-{size}.png')
encoded=base64.b64encode(source.read_bytes()).decode()
(public/'icon.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 512 512"><rect width="512" height="512" rx="72" fill="white"/><image x="100" y="108" width="312" height="296" href="data:image/png;base64,{encoded}"/></svg>',encoding='utf-8')
