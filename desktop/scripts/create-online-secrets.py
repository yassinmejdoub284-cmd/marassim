"""Generate private deployment values locally. Never print credentials."""
import argparse,base64,secrets
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
parser=argparse.ArgumentParser();parser.add_argument('--output',default='.env.online.local');args=parser.parse_args()
target=Path(args.output)
if target.exists(): raise SystemExit('Le fichier existe déjà : aucune clé remplacée.')
key=ec.generate_private_key(ec.SECP256R1())
encode=lambda b:base64.urlsafe_b64encode(b).decode().rstrip('=')
private=encode(key.private_numbers().private_value.to_bytes(32,'big'))
public=encode(key.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint))
target.write_text(f'MARASSIM_SYNC_SECRET={secrets.token_urlsafe(48)}\nMARASSIM_SESSION_SECRET={secrets.token_urlsafe(48)}\nVAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={private}\nVAPID_SUBJECT=https://YOUR-PROJECT.vercel.app\nDATABASE_URL=\n',encoding='utf-8')
print('Fichier privé créé. Complétez DATABASE_URL et VAPID_SUBJECT localement, puis copiez les valeurs dans Vercel. Ne publiez pas ce fichier.')
