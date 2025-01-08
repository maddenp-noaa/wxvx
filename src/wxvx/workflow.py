"""
Workflow logic.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import parsl
from parsl.config import Config
from parsl.executors import ThreadPoolExecutor

configs = {
    "threads": Config(
        executors=[ThreadPoolExecutor(max_threads=4)],
        initialize_logging=False,
    )
}


@contextmanager
def run(workdir: Path, loader: str) -> Generator:
    config = configs[loader]
    config.run_dir = str(workdir)
    parsl.load(config)
    yield
    parsl.dfk().cleanup()
