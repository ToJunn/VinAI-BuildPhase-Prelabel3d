import re
from pathlib import Path


def to_wsl(path):
    text = str(Path(path).resolve()).replace('\\', '/')
    if not re.match(r'^[A-Za-z]:/', text):
        raise ValueError('WSL mapping requires an absolute Windows drive path')
    return f'/mnt/{text[0].lower()}/{text[3:]}'


def to_windows(path):
    match = re.fullmatch(r'/mnt/([a-z])/(.*)', str(path))
    if not match:
        raise ValueError('WSL interpreter must reside under a mounted Windows drive in this MVP')
    return Path(f'{match[1].upper()}:/{match[2]}')
