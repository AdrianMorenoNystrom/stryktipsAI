"""Local-only diagnostics over real, timestamped optimizer inputs; no historical replay."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ARTIFACTS, BUDGET_PRESETS, OPTIMIZER_WEIGHTS
from app.storage import iso, now_utc
from app.stryktipset.service import DrawService, choose_current

SIGNS = ('1', 'X', '2', '1X', '12', 'X2', '1X2')


def eligible(run, close):
    at = datetime.fromisoformat(run['created_at'])
    if at >= close or len(run['inputs']) != 13:
        return False
    for item in run['inputs'].values():
        if item['crowd']['provider'] != 'svenska-spel':
            return False
        for kind in ('crowd', 'market'):
            if any(datetime.fromisoformat(item[kind][key]) > at for key in
                   ('recorded_at', 'retrieved_at', 'source_updated_at') if item[kind].get(key)):
                return False
    return True


def report(service):
    runs, excluded = {}, 0
    for draw in service.repo.draws():
        for run in service.repo.systems(draw.draw_number):
            if not eligible(run, draw.sales_close_at):
                excluded += 1
                continue
            system = run['analysis']['system']
            # Repeated UI analyses are not independent samples.
            runs[(draw.draw_number, system['budget'], system['mode'])] = run
    distribution = Counter({sign: 0 for sign in SIGNS})
    conditions = []
    for (number, budget, profile), run in sorted(runs.items()):
        system = run['analysis']['system']
        signs = [''.join(s) for s in system['selections']]
        distribution.update(signs)
        conditions.append({'draw_number': number, 'budget': budget, 'profile': profile,
            'snapshot_id': run['id'], 'created_at': run['created_at'], 'selections': signs,
            'row_count': system['rowCount'], 'cost': system['cost'],
            'budget_utilization': system['cost'] / budget,
            'draw_coverage': sum('X' in sign for sign in signs) / 13,
            'estimated_all_correct_probability': system['metrics']['allCorrectProbability']})
    distinct = len({k[0] for k in runs})
    return {'generated_at': iso(now_utc()), 'data': 'observed Svenska Spel crowd; saved pre-close analyses',
        'selection_policy': 'latest saved run per draw/budget/profile; no historical reconstruction',
        'unique_draws': distinct, 'conditions': len(conditions), 'excluded_runs': excluded,
        'selection_distribution': dict(distribution),
        'mean_draw_coverage': sum(r['draw_coverage'] for r in conditions) / len(conditions) if conditions else None,
        'mean_budget_utilization': sum(r['budget_utilization'] for r in conditions) / len(conditions) if conditions else None,
        'completed_draws_with_pre_close_system': sum(service.repo.result(n) is not None for n in {k[0] for k in runs}),
        'performance_conclusion': 'Descriptive only. No claim of optimizer performance or payout profitability; independent completed pre-close samples are required.',
        'rows': conditions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze-current', action='store_true', help='Save 12 new analyses from already archived current inputs; no HTTP')
    parser.add_argument('--output', type=Path, default=ARTIFACTS / 'optimizer_real_crowd_diagnostics.json')
    args = parser.parse_args()
    service = DrawService()
    if args.analyze_current:
        draw = choose_current(service.repo.draws(), now_utc())
        if not draw:
            raise SystemExit('No open archived draw; run update_stryktipset.py first.')
        for budget in BUDGET_PRESETS:
            for profile in OPTIMIZER_WEIGHTS:
                service.analyze_live(draw.draw_number, budget, profile)
    result = report(service)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
