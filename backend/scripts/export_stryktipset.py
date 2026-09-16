"""Export a consistent SQLite read snapshot to separate JSONL datasets, without joining results to inputs."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.storage import iso, now_utc
from app.stryktipset.config import DrawConfig
from app.stryktipset.repository import DrawRepository


def main():
    config = DrawConfig()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=config.root / 'exports' / now_utc().strftime('%Y%m%dT%H%M%S%fZ'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = DrawRepository(config.root)
    tables = tuple(repo.counts())
    manifest = {'exported_at': iso(now_utc()), 'database': str(repo.path), 'counts': {},
                'temporal_policy': 'Filter recorded/retrieved/source timestamps <= cutoff; results and payouts remain separate.'}
    with repo.connection() as con:
        con.execute('BEGIN')
        for table in tables:
            count = 0
            with (args.output / f'{table}.jsonl').open('w', encoding='utf-8') as stream:
                for row in con.execute(f'SELECT * FROM {table}'):
                    record = dict(row)
                    if 'payload' in record:
                        record['payload'] = json.loads(record['payload'])
                    stream.write(json.dumps(record, ensure_ascii=False) + '\n')
                    count += 1
            manifest['counts'][table] = count
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
