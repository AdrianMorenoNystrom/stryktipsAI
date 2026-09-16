import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from app.services.teams import ALIASES, key, normalize_team, team_id

OFFICIAL = {"arsenal.com", "evertonfc.com", "chelseafc.com", "liverpoolfc.com", "manutd.com", "mancity.com",
            "nufc.co.uk", "newcastleunited.com", "tottenhamhotspur.com", "avfc.co.uk", "whufc.com", "cpfc.co.uk",
            "fulhamfc.com", "brightonandhovealbion.com", "leedsunited.com", "safc.com", "hullcitytigers.com",
            "wba.co.uk", "qpr.co.uk", "canaries.co.uk", "watfordfc.com", "ccfc.co.uk", "burnleyfootballclub.com",
            "pnefc.net", "stokecityfc.com", "sufc.co.uk", "rovers.co.uk", "bwfc.co.uk", "readingfc.co.uk",
            "premierleague.com", "efl.com", "thefa.com"}
MAJOR = {"bbc.co.uk", "bbc.com", "skysports.com", "theguardian.com", "reuters.com", "apnews.com"}
LOCAL = {"liverpoolecho.co.uk", "chroniclelive.co.uk", "yorkshireeveningpost.co.uk", "lancs.live", "birminghammail.co.uk"}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid article URL")
    host = parsed.hostname.lower().removeprefix("www.")
    query = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith(("utm_", "at_")) and k.lower() not in ("fbclid", "gclid", "ref", "output")]
    return urlunsplit(("https", host, parsed.path.rstrip("/") or "/", urlencode(sorted(query)), ""))


def publisher_info(url: str) -> tuple[str, int]:
    host = urlsplit(url).hostname or ""
    for tier, domains in ((1, OFFICIAL), (2, MAJOR), (3, LOCAL)):
        for domain in domains:
            if host == domain or host.endswith("." + domain):
                return ("bbc" if domain in ("bbc.co.uk", "bbc.com") else domain), tier
    return host.removeprefix("www."), 4


def mentions(text: str, name: str) -> bool:
    canonical = normalize_team(name)
    aliases = [canonical, *ALIASES.get(canonical, [])]
    return any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, flags=re.I) for alias in aliases)


def detected_teams(text: str, names: list[str]) -> list[str]:
    return sorted({team_id(name) for name in names if mentions(text, name)})


def normalized_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def player_alias_key(name: str) -> str:
    return key(name)


def player_initial_key(name: str) -> str:
    words = re.findall(r"[\wÀ-ÿ]+", name.lower())
    return f"{words[0][0]}{words[-1]}" if len(words) >= 2 else key(name)
