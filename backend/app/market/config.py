from dataclasses import dataclass, field
import os

SPORT_KEYS = {'E0': 'soccer_epl', 'E1': 'soccer_efl_champ', 'E2': 'soccer_england_league1'}


@dataclass
class MarketConfig:
    api_key: str = field(default_factory=lambda: os.getenv('ODDS_API_KEY', ''), repr=False)
    regions: str = field(default_factory=lambda: os.getenv('ODDS_REGIONS', 'uk'))
    minimum_bookmakers: int = field(default_factory=lambda: int(os.getenv('MIN_BOOKMAKERS_FOR_CONSENSUS', '3')))
    fresh_seconds: int = 1800
    cached_max_seconds: int = 21600
    bookmaker_max_age_seconds: int = 21600
    kickoff_tolerance_seconds: int = 900
    request_cache_seconds: int = 300
    timeout: int = 20
    exclude_bookmakers: tuple = ('betfair_ex_eu', 'betfair_ex_uk', 'betfair_ex_au', 'betfair_ex_us', 'matchbook')

    def __post_init__(self):
        if self.minimum_bookmakers < 2:
            raise ValueError('Consensus requires at least two bookmakers')
