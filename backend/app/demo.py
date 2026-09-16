"""Fictional fixtures, prices and crowd; probabilities always come from the predictor."""
from datetime import date, timedelta


def demo_coupon() -> dict:
    today = date.today()
    saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
    fixtures = [
        ("Arsenal", "Everton", "E0", [1.55, 4.4, 6.4], [72, 18, 10]),
        ("Fulham", "Brighton", "E0", [2.55, 3.4, 2.8], [43, 29, 28]),
        ("Leeds", "Chelsea", "E0", [4.2, 3.8, 1.85], [20, 24, 56]),
        ("Coventry", "Burnley", "E1", [2.25, 3.3, 3.2], [38, 31, 31]),
        ("Liverpool", "Newcastle", "E0", [1.65, 4.2, 5.2], [78, 14, 8]),
        ("Manchester United", "Aston Villa", "E0", [2.1, 3.6, 3.5], [57, 24, 19]),
        ("West Ham", "Crystal Palace", "E0", [2.6, 3.1, 2.9], [39, 32, 29]),
        ("Norwich", "Watford", "E1", [2.15, 3.4, 3.4], [42, 28, 30]),
        ("West Brom", "QPR", "E1", [1.8, 3.5, 4.7], [54, 28, 18]),
        ("Preston", "Stoke", "E1", [2.6, 3.0, 3.0], [32, 35, 33]),
        ("Sheffield United", "Blackburn", "E1", [1.95, 3.4, 4.1], [59, 24, 17]),
        ("Bolton", "Reading", "E2", [1.9, 3.6, 4.0], [46, 29, 25]),
        ("Sunderland", "Hull", "E1", [2.0, 3.4, 3.8], [47, 27, 26]),
    ]
    return {"id": "demo-13", "week": saturday.isocalendar().week, "date": str(saturday), "demo": True,
            "matches": [{"number": i, "homeTeam": h, "awayTeam": a, "league": league, "date": str(saturday),
                         "marketOdds": dict(zip(("home", "draw", "away"), odds)),
                         "crowd": dict(zip(("home", "draw", "away"), crowd)),
                         "oddsSnapshot": {"source": "demo"}, "crowdSnapshot": {"source": "demo"}}
                        for i, (h, a, league, odds, crowd) in enumerate(fixtures, 1)]}
