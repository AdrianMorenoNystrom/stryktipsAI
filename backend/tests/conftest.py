import pytest


@pytest.fixture(autouse=True)
def isolate_live_storage(tmp_path,monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('ODDS_API_KEY',raising=False)
    monkeypatch.setenv('ENVIRONMENT','test')
    monkeypatch.setenv('STRYKTIPS_LIVE_DIR',str(tmp_path/'stryktipset'))
    monkeypatch.setenv('STRYKTIPS_LIVE_ENABLED','false')
