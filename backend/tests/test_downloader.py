import hashlib
import json
import httpx
from scripts import download_football_data as importer


def test_download_preserves_original_and_survives_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "DATA", tmp_path)
    first = b"Date,HomeTeam,AwayTeam,FTR\n01/08/2020,Arsenal,Everton,H\n"
    second = first + b"08/08/2020,Everton,Arsenal,D\n"
    payload = [first]
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if "E2.csv" in str(request.url): return httpx.Response(404)
        return httpx.Response(200, content=payload[0])
    monkeypatch.setattr(importer.httpx, "HTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    result = importer.download(2020, 2020, ("E0", "E2"))
    assert len(result["downloaded"]) == len(result["failed"]) == 1
    original = tmp_path / "raw" / "2020-21" / "E0.csv"
    checksum = hashlib.sha256(original.read_bytes()).hexdigest()
    cached = importer.download(2020, 2020, ("E0",))
    assert cached["cached"] == ["2020-21/E0"]
    assert len(calls) == 2
    payload[0] = second
    importer.download(2020, 2020, ("E0",), refresh=True)
    assert hashlib.sha256(original.read_bytes()).hexdigest() == checksum
    manifest = json.loads((tmp_path / "raw" / "manifest.json").read_text())
    assert (tmp_path / "raw" / manifest["2020-21/E0"]["path"]).read_bytes() == second
