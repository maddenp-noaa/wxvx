import logging
from pathlib import Path
from typing import Optional

import requests


def fetch(taskname: str, url: str, path: Path, headers: Optional[dict[str, str]] = None) -> bool:
    suffix = " %s" % headers.get("Range", "") if headers else ""
    logging.info("%s: Fetching %s%s", taskname, url, suffix)
    response = requests.get(url, allow_redirects=True, timeout=3, headers=headers or {})
    expected = 206 if headers and "Range" in headers.keys() else 200
    if response.status_code == expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(response.content)
            logging.info("%s: Wrote %s", taskname, path)
        return True
    return False


def status(url: str) -> int:
    return requests.head(url, timeout=3).status_code
