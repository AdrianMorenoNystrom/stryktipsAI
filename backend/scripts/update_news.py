import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.demo import demo_coupon
from app.news.config import NewsConfig
from app.news.service import NewsService
from app.schemas import Coupon


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect coupon-scoped news without changing probabilities")
    parser.add_argument("--coupon", default="CURRENT", help="CURRENT, DEMO, or path to a coupon JSON file")
    parser.add_argument("--provider", choices=["rss", "brave", "tavily"])
    parser.add_argument("--extraction", choices=["rules", "openai"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = NewsConfig()
    if args.provider:
        config.provider = args.provider
    if args.extraction:
        config.extraction = args.extraction
    service = NewsService(config)
    source = service.repo.current_coupon() if args.coupon == "CURRENT" else demo_coupon() if args.coupon == "DEMO" else json.loads(Path(args.coupon).read_text(encoding="utf-8"))
    if source is None:
        raise SystemExit("Ingen sparad kupong. Analysera en kupong i appen eller välj --coupon DEMO.")
    report = service.update(Coupon.model_validate(source))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report.get("failed_requests") and not report.get("matches_updated"):
        raise SystemExit(1)
