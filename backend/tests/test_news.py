from datetime import datetime, timedelta, timezone
import json
import httpx
import pytest
from pydantic import ValidationError
from app.demo import demo_coupon
from app.news.config import NewsConfig
from app.news.entities import canonical_url, digest, publisher_info
from app.news.events import active_signals, record_signal
from app.news.extraction import OpenAIExtractor, RulesExtractor, validate_evidence
from app.news.providers import SearchResult, ProviderError, parse_time
from app.news.repository import NewsRepository
from app.news.schemas import Extraction, ExtractedSignal, NewsArticle
from app.news.service import NewsService
from app.schemas import Coupon, MatchInput
from app.services.match_identity import match_id
from ml.predict import PredictionService

AT = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def article(url="https://bbc.co.uk/sport/one", text="Arsenal defender John Smith is ruled out with an ankle injury.", published=AT - timedelta(hours=2)):
    publisher, tier = publisher_info(url)
    return NewsArticle(id=digest(canonical_url(url)), version_id=digest(url + text), title=text, url=canonical_url(url),
        publisher=publisher, published_at=published, retrieved_at=AT, snippet="", source_tier=tier,
        detected_team_ids=["arsenal"], query='"Arsenal" injury', raw_path="raw/test.raw", content_hash=digest(text))


def signal(kind="PLAYER_OUT", text="Arsenal defender John Smith is ruled out with an ankle injury.", status="reported"):
    return ExtractedSignal(type=kind, team="Arsenal", player="John Smith", direction="negative" if kind == "PLAYER_OUT" else "positive",
        certainty=.95, status=status, summary=text, evidence=text, occurred_at=None)


class FakeProvider:
    def __init__(self, articles): self.articles, self.calls = articles, 0
    def search(self, query, from_time, to_time):
        self.calls += 1
        return [SearchResult(self.articles, json.dumps(self.articles).encode(), "mock")]


def test_url_dedupe_and_entity_aliases(tmp_path):
    assert canonical_url("https://www.bbc.co.uk/sport/one/?utm_source=x#section") == canonical_url("http://bbc.co.uk/sport/one?at_medium=RSS")
    assert publisher_info("https://bbc.co.uk.evil.test/one")[1] == 4
    repo = NewsRepository(tmp_path)
    a = article()
    assert repo.save_article(a)
    assert not repo.save_article(a)
    assert repo.counts()["articles"] == repo.counts()["article_versions"] == 1
    initial = repo.player("J. Smith", "arsenal")
    full = repo.player("John Smith", "arsenal")
    assert initial.player_id == full.player_id == repo.player("J Smith", "arsenal").player_id
    assert repo.player("Jonathan Smith", "arsenal").player_id != full.player_id


def test_rules_and_evidence_never_invent_signals():
    extractor = RulesExtractor()
    extracted = extractor.extract(article(), ["Arsenal"])
    assert len(extracted.signals) == 1
    assert extracted.signals[0].player == "John Smith"
    for text in ("Arsenal return to Italy for a Champions League game.", "Arsenal are the best club in the world.",
                 "Arsenal defender John Smith could be ruled out.", "Arsenal Women defender Jane Smith is ruled out."):
        assert extractor.extract(article(text=text), ["Arsenal"]).signals == []
    anonymous = article(text="Reading winger back after a lengthy injury.")
    output = extractor.extract(anonymous, ["Reading"])
    assert output.signals[0].player is None and output.signals[0].type == "PLAYER_RETURN"
    invented = signal(text="Arsenal defender Bob Jones is out.")
    assert validate_evidence(Extraction(signals=[invented]), article(), ["Arsenal"]).signals == []


def test_strict_llm_output_mocked_no_network_or_probability_fields():
    requests = []
    def handle(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["text"]["format"]["strict"] is True
        assert payload["store"] is False
        return httpx.Response(200, json={"status":"completed", "output":[{"content":[{"type":"output_text", "text":Extraction(signals=[signal()]).model_dump_json()}]}]})
    config = NewsConfig(llm_key="test-only", llm_model="test-model", extraction="openai", request_interval=0)
    extractor = OpenAIExtractor(config, httpx.Client(transport=httpx.MockTransport(handle)))
    assert len(extractor.extract(article(), ["Arsenal"]).signals) == 1
    assert "home_win_delta" not in requests[0]["text"]["format"]["schema"]["$defs"]["ExtractedSignal"]["properties"]
    payload = signal().model_dump()
    payload["home_win_delta"] = -.03
    with pytest.raises(ValidationError):
        ExtractedSignal.model_validate(payload)
    assert "test-only" not in repr(config)


def test_story_grouping_precedence_and_immutable_time_history(tmp_path):
    repo = NewsRepository(tmp_path)
    config = NewsConfig(root=tmp_path)
    fixture = "fixture"
    first = article()
    second = article(url="https://skysports.com/football/one", text="Arsenal defender John Smith is ruled out with injury.")
    for a in (first, second):
        repo.save_article(a)
        assert record_signal(repo, config, a, signal(text=a.title), fixture, AT, "test")
    state = active_signals(repo, config, fixture, AT)
    assert len(state) == 1 and state[0]["source_count"] == 2
    repo.save_snapshot(fixture, AT, {"snapshot_time": AT.isoformat(), "signals": state})
    later = AT + timedelta(hours=3)
    official = article(url="https://arsenal.com/news/update", text="Arsenal defender John Smith returned to training.", published=later)
    official.retrieved_at = later
    repo.save_article(official)
    record_signal(repo, config, official, signal("PLAYER_RETURN", official.title, "confirmed"), fixture, later, "test")
    current = active_signals(repo, config, fixture, later)
    assert len(current) == 1 and current[0]["type"] == "PLAYER_RETURN" and current[0]["status_label"] == "Bekräftad"
    assert current[0]["has_conflicting_reports"]
    assert active_signals(repo, config, fixture, AT)[0]["type"] == "PLAYER_OUT"
    assert repo.snapshot(fixture, AT)["signals"][0]["type"] == "PLAYER_OUT"
    assert len(repo.observations(fixture, later)) == 3


def test_late_retrieval_is_not_backdated_and_syndication_is_not_independent(tmp_path):
    repo = NewsRepository(tmp_path)
    config = NewsConfig(root=tmp_path)
    a = article()
    for url in ("https://bbc.co.uk/one", "https://skysports.com/two"):
        a = article(url=url)
        record_signal(repo, config, a, signal(), "m", AT + timedelta(hours=3), "test")
    assert not active_signals(repo, config, "m", AT)
    state = active_signals(repo, config, "m", AT + timedelta(hours=3))
    assert state[0]["independent_source_count"] == 1


def test_full_update_idempotency_snapshots_and_probability_isolation(tmp_path):
    source = article()
    raw = {"title":source.title,"url":str(source.url),"published_at":source.published_at.isoformat(),"snippet":"","content":""}
    provider = FakeProvider([raw, {**raw, "url":str(source.url) + '?utm_source=duplicate'}])
    config = NewsConfig(provider="rss", root=tmp_path, request_interval=0)
    service = NewsService(config, provider=provider, extractor=RulesExtractor())
    coupon = Coupon.model_validate(demo_coupon())
    for match in coupon.matches: match.date = (AT + timedelta(days=3)).date()
    match = coupon.matches[0]
    predictor = PredictionService()
    before_prob = predictor.predict(match)["model"]
    first = service.update(coupon, AT)
    counts = service.repo.counts()
    second = service.update(coupon, AT)
    assert service.repo.counts() == counts
    assert first["unique_articles"] == 1 and second["articles_created"] == 0
    assert counts["events"] == 1 and counts["observations"] == 1
    assert service.view(match_id(match), AT)["signals"][0]["type"] == "PLAYER_OUT"
    assert before_prob == predictor.predict(match)["model"]
    assert first["matches_updated"] == 13
    assert service.repo.current_coupon()["id"] == coupon.id


def test_provider_failure_preserves_saved_snapshot_and_missing_keys_do_not_block(tmp_path):
    service = NewsService(NewsConfig(root=tmp_path, provider=""))
    coupon = Coupon.model_validate(demo_coupon())
    assert service.update(coupon, AT)["configured"] is False
    assert PredictionService().predict(coupon.matches[0])["model"]
    repo = service.repo
    identifier = match_id(coupon.matches[0])
    saved = {"snapshot_time":AT.isoformat(), "signals":[]}
    repo.save_snapshot(identifier, AT, saved)
    class BrokenProvider:
        def search(self, *args): raise ProviderError("Unavailable")
    failing = NewsService(NewsConfig(root=tmp_path, provider="rss"), provider=BrokenProvider())
    report = failing.update(coupon, AT + timedelta(hours=1))
    assert report["failed_requests"]
    assert repo.snapshot(identifier, AT + timedelta(hours=1)) == saved
    assert failing.view(identifier, AT + timedelta(hours=1))["error"]


def test_date_only_and_unknown_timestamps_are_not_fabricated():
    assert parse_time("2026-09-09") is None
    assert parse_time("yesterday") is None
    assert parse_time("Wed, 09 Sep 2026 14:00:00 BST").hour == 13


def test_partial_feed_failure_keeps_good_signals_and_reports_incomplete_coverage(tmp_path):
    a = article()
    provider = FakeProvider([{"title":a.title, "url":str(a.url), "published_at":a.published_at.isoformat()}])
    provider.failures = ["RSS feed unavailable"]
    service = NewsService(NewsConfig(root=tmp_path, provider="rss"), provider=provider, extractor=RulesExtractor())
    coupon = Coupon.model_validate(demo_coupon())
    for match in coupon.matches: match.date = (AT + timedelta(days=3)).date()
    report = service.update(coupon, AT)
    view = service.view(match_id(coupon.matches[0]), AT)
    assert report["matches_updated"] == 13
    assert len(view["signals"]) == 1 and view["error"]


@pytest.mark.parametrize("body", [
    {"status":"incomplete", "output":[]},
    {"status":"completed", "output":[{"content":[{"type":"refusal", "refusal":"Unable"}]}]},
    {"status":"completed", "output":[{"content":[{"type":"output_text", "text":"not json"}]}]},
])
def test_invalid_llm_responses_are_rejected(body):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    extractor = OpenAIExtractor(NewsConfig(llm_key="mock", llm_model="mock", request_interval=0), client)
    with pytest.raises((ValueError, ProviderError)):
        extractor.extract(article(), ["Arsenal"])


def test_provider_rate_limit_retries_without_real_requests(monkeypatch):
    from app.news.providers import BraveProvider, TavilyProvider
    monkeypatch.setattr("app.news.providers.time.sleep", lambda _: None)
    for cls in (BraveProvider, TavilyProvider):
        calls = []
        def handle(request):
            calls.append(request)
            return httpx.Response(429, headers={"Retry-After":"0"}) if len(calls) < 3 else httpx.Response(200, json={"results":[]})
        provider = cls(NewsConfig(api_key="mock", request_interval=0), httpx.Client(transport=httpx.MockTransport(handle)))
        assert provider.search("Arsenal injury", AT - timedelta(days=7), AT)[0].articles == []
        assert len(calls) == 3


def test_manual_coupon_reversion_is_a_new_snapshot(tmp_path):
    repo = NewsRepository(tmp_path)
    first = demo_coupon()
    second = json.loads(json.dumps(first))
    second["matches"][0]["marketOdds"]["home"] = 1.83
    repo.save_coupon(first, AT)
    repo.save_coupon(first, AT + timedelta(minutes=1))
    repo.save_coupon(second, AT + timedelta(minutes=2))
    repo.save_coupon(first, AT + timedelta(minutes=3))
    assert len(repo.coupon_history(first["id"])) == 3
    assert repo.current_coupon() == first


def test_news_view_preserves_exact_evidence_version_after_article_edit(tmp_path):
    service = NewsService(NewsConfig(root=tmp_path))
    repo = service.repo
    old = article()
    repo.save_article(old)
    repo.link_article("m", old.version_id, AT)
    record_signal(repo, service.config, old, signal(), "m", AT, "test")
    repo.save_snapshot("m", AT, {"snapshot_time":AT.isoformat(), "signals":active_signals(repo, service.config, "m", AT)})
    newer = article(text="Arsenal published an updated article.")
    newer.retrieved_at = AT + timedelta(hours=1)
    repo.save_article(newer)
    repo.link_article("m", newer.version_id, newer.retrieved_at)
    view = service.view("m", newer.retrieved_at)
    assert {s["version_id"] for s in view["sources"]} == {old.version_id, newer.version_id}
    assert view["signals"][0]["source_article_ids"] == [old.version_id]
