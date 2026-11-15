"""Opt-in reuse of the pinned public downloader, with all assets outside Git."""
import argparse
import importlib.util
from pathlib import Path
import shutil

SOURCE = Path(__file__).resolve().parents[1] / 'local-generation-smoke'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('/tmp/rag-local-assets'))
    args = parser.parse_args()
    destination = args.directory.resolve()
    if not destination.is_relative_to('/tmp'):
        raise ValueError('this experiment keeps downloads under /tmp only')
    destination.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('pinned_prepare', SOURCE / 'prepare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = destination
    shutil.copy2(SOURCE / 'sources.json', destination / 'sources.json')
    module.main()


if __name__ == '__main__':
    main()
