"""Download the public source data into data/raw/.

Both sources are pinned to a fixed version, so a rerun always produces the same inputs:

1. Kaggle "Real time Advertiser's Auction" (saurav9786/real-time-advertisers-auction, v1):
   daily ad delivery of several websites owned by one publisher, June 2019.
   Public dataset, no Kaggle account needed.
2. Numenta Anomaly Benchmark (MIT license): hourly CPC/CPM series of three ad exchanges
   and the hand-labelled anomaly windows for them.

Usage:
    python scripts/download_data.py              # everything
    python scripts/download_data.py --only nab   # one source
    python scripts/download_data.py --force      # re-download existing files
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "raw"

AUCTION_HANDLE = "saurav9786/real-time-advertisers-auction/versions/1"
AUCTION_FILE = "Dataset.csv"
AUCTION_DIR = RAW_DIR / "real_time_auction"

NAB_COMMIT = "ea702d75cc2258d9d7dd35ca8e5e2539d71f3140"
NAB_BASE_URL = f"https://raw.githubusercontent.com/numenta/NAB/{NAB_COMMIT}"
NAB_SERIES = [f"exchange-{n}_{metric}_results.csv" for n in (2, 3, 4) for metric in ("cpc", "cpm")]
NAB_DIR = RAW_DIR / "nab"


def _should_skip(target: Path, force: bool) -> bool:
    if target.exists() and not force:
        print(f"skip  {target.relative_to(PROJECT_DIR)} (already downloaded)")
        return True
    return False


def download_auction(force: bool) -> None:
    target = AUCTION_DIR / AUCTION_FILE
    if _should_skip(target, force):
        return

    import kagglehub

    AUCTION_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        # Downloading the whole dataset (a single file) lets kagglehub unpack it;
        # a single-file download can arrive as a zip archive under the CSV's name.
        dataset_dir = Path(kagglehub.dataset_download(AUCTION_HANDLE, output_dir=tmp, force_download=force))
        downloaded = dataset_dir / AUCTION_FILE
        if zipfile.is_zipfile(downloaded):
            with zipfile.ZipFile(downloaded) as archive, archive.open(AUCTION_FILE) as source, target.open("wb") as out:
                shutil.copyfileobj(source, out)
        else:
            shutil.copyfile(downloaded, target)
    print(f"done  {target.relative_to(PROJECT_DIR)}")


def download_nab(force: bool) -> None:
    files = {f"data/realAdExchange/{name}": NAB_DIR / "realAdExchange" / name for name in NAB_SERIES}
    files["labels/combined_windows.json"] = NAB_DIR / "combined_windows.json"

    for remote_path, target in files.items():
        if _should_skip(target, force):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(f"{NAB_BASE_URL}/{remote_path}", timeout=60) as response:
            target.write_bytes(response.read())
        print(f"done  {target.relative_to(PROJECT_DIR)}")


SOURCES = {"auction": download_auction, "nab": download_nab}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=SOURCES, help="download a single source")
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = parser.parse_args()

    for name, download in SOURCES.items():
        if args.only in (None, name):
            download(args.force)


if __name__ == "__main__":
    main()
