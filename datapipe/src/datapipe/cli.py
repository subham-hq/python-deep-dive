import argparse
import json
from pathlib import Path
from typing import cast

from datapipe.models import Record
from datapipe.pipeline import Normalize, Pipeline, Scale
from datapipe.steps import RequiredName, RequirePositiveValue

def load_record(path: Path) -> list[Record]:
    with path.open("r", encoding="utf-8") as f:
        return cast(list[Record], json.load(f))

def main() -> None:
    parser = argparse.ArgumentParser(description="Run records through the data pipeline.")
    parser.add_argument("path", type=Path, help="Path to a JSON file of records")
    args = parser.parse_args()

    records = load_record(args.path)
    pipeline = Pipeline[Record]([
        RequiredName(),
        RequirePositiveValue(),
        Normalize(),
        Scale(1.1),
    ])

    for result in pipeline.run(records):
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()