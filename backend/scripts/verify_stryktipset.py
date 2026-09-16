"""Verify already observed live data and write reproducible Prompt 3 evidence. No external HTTP."""
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.storage import iso, now_utc
from app.stryktipset.service import DrawService, choose_current
from diagnose_real_crowd import report


def main():
    service = DrawService()
    draw = choose_current(service.repo.draws(), now_utc())
    if not draw:
        raise SystemExit('Fetch an open live coupon first.')
    result = service.analyze_live(draw.draw_number, 256, 'optimal')
    assert len(result['matches']) == 13
    assert all(m['model'] == m['market'] and m['source'] == 'market_baseline' for m in result['matches'])
    run = service.repo.latest_system(draw.draw_number, now_utc(), 256, 'optimal')
    assert run['model']['active_model'] == 'market'
    before = service.repo.counts()
    # Cached repeat import: no new HTTP, matches, crowd or result observations.
    for number in (4267, 4969):
        assert service.ingest(number)['cached']
        assert service.update_results(number)['completed']
    assert before == service.repo.counts()
    coverage = {}
    for field in ('metadata', 'matches', 'crowd', 'results', 'payout'):
        supported = []
        for d in service.repo.draws():
            actual = service.repo.result(d.draw_number)
            available = {'metadata': True, 'matches': len(d.matches) == 13,
                'crowd': all(m.crowd is not None for m in d.matches),
                'results': bool(actual and actual['completed']),
                'payout': bool(actual and actual['payouts'])}[field]
            if available:
                supported.append(d)
        oldest = min(supported, key=lambda d: d.draw_date)
        newest = max(supported, key=lambda d: d.draw_date)
        coverage[field] = {'draws_in_local_sample': len(supported), 'earliest_observed_draw': oldest.draw_number,
            'earliest_observed_date': str(oldest.draw_date), 'latest_observed_draw': newest.draw_number}
    observations = service.repo.observations(draw.draw_number)
    diagnostics = report(service)
    output = {'verified_at': iso(now_utc()), 'verification': 'Actual public responses and local pipeline; no submitted bets',
        'draw_number': draw.draw_number, 'date': str(draw.draw_date), 'sales_close_at': iso(draw.sales_close_at),
        'retrieved_at': iso(draw.retrieved_at), 'matches': len(draw.matches),
        'crowd_matches': sum(m.crowd is not None for m in draw.matches),
        'odds_matches': sum(m.market_odds is not None for m in draw.matches),
        'mapping': service.mapping(draw), 'active_model': run['model'],
        'all_model_probabilities_equal_devig_market': True,
        'counts': service.repo.counts(), 'current_draw_observations': len(observations),
        'observation_times': [{'recorded_at': o['recorded_at'], 'retrieved_at': o['retrieved_at']} for o in observations],
        'movement': service.movement(draw.draw_number, now_utc()),
        'optimizer': result['system'], 'analysis_at': result['analyzedAt'],
        'live_matches': [{k: m[k] for k in ('number', 'homeTeam', 'awayTeam', 'league', 'marketOdds', 'crowd', 'market', 'model', 'recommendation')} for m in result['matches']],
        'coverage': coverage, 'coverage_is_sparse_sample_not_continuous_archive': True,
        'sampled_history_ranges': [[4267, 4270], [4958, 4969]],
        'cached_repeat_import_preserved_all_counts': True,
        'historical_pre_close_batches': sum(service.repo.pre_close(d.draw_number) is not None for d in service.repo.draws() if d.sales_close_at < now_utc()),
        'historical_example': service.repo.result(4969),
        'real_crowd_unique_draws': diagnostics['unique_draws'],
        'real_crowd_completed_draws_with_pre_close_system': diagnostics['completed_draws_with_pre_close_system']}
    docs = Path(__file__).resolve().parents[2] / 'docs'
    (docs / 'verification-v3.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    (docs / 'optimizer-real-crowd-v3.json').write_text(json.dumps(diagnostics, indent=2), encoding='utf-8')
    print(json.dumps({k: output[k] for k in ('verified_at', 'retrieved_at', 'counts', 'observation_times', 'optimizer', 'coverage')}, indent=2))


if __name__ == '__main__':
    main()
