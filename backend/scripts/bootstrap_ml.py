import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_football_data import download
from scripts.normalize_football_data import normalize
from threadpoolctl import threadpool_limits


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-v1", action="store_true", help="Explicitly replace deployment with the original v1 model")
    args = parser.parse_args()
    downloaded = download()
    if not downloaded["downloaded"] and not downloaded["cached"]:
        raise SystemExit("Importen misslyckades för samtliga filer. Se download_report.json.")
    normalized = normalize()
    with threadpool_limits(limits=1):
        if args.legacy_v1:
            from ml.train import train
            from ml.evaluate import evaluate
            trained, evaluated = train(), evaluate()
        else:
            from ml.train_v2 import train_v2
            from ml.export_candidate import export_candidate
            trained = train_v2()
            export_candidate()
            evaluated = trained["evaluation"]["overall"]
    print(json.dumps({"dataset": normalized["leagues"], "import_failures": downloaded["failed"],
                      "training_matches": trained["training_matches"], "test": evaluated}, indent=2))
