import re
import urllib.parse

BOT_RE = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview|facebookexternalhit|monitor|curl|python|wget", re.I)

COUNTRIES = {
    "MV": "Maldives", "IN": "India", "LK": "Sri Lanka", "GB": "United Kingdom", "US": "United States", "DE": "Germany",
    "IT": "Italy", "FR": "France", "RU": "Russia", "CN": "China", "JP": "Japan", "KR": "South Korea", "ES": "Spain",
    "NL": "Netherlands", "CH": "Switzerland", "AT": "Austria", "BE": "Belgium", "PL": "Poland", "CZ": "Czechia",
    "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland", "IE": "Ireland", "PT": "Portugal", "GR": "Greece",
    "UA": "Ukraine", "KZ": "Kazakhstan", "TR": "Türkiye", "IL": "Israel", "AE": "United Arab Emirates", "SA": "Saudi Arabia",
    "QA": "Qatar", "OM": "Oman", "KW": "Kuwait", "BH": "Bahrain", "PK": "Pakistan", "BD": "Bangladesh", "NP": "Nepal",
    "MY": "Malaysia", "SG": "Singapore", "TH": "Thailand", "ID": "Indonesia", "PH": "Philippines", "VN": "Vietnam",
    "AU": "Australia", "NZ": "New Zealand", "CA": "Canada", "BR": "Brazil", "MX": "Mexico", "AR": "Argentina",
    "ZA": "South Africa", "EG": "Egypt", "KE": "Kenya", "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria",
    "SK": "Slovakia", "SI": "Slovenia", "HR": "Croatia", "RS": "Serbia", "LT": "Lithuania", "LV": "Latvia", "EE": "Estonia",
    "HK": "Hong Kong", "TW": "Taiwan",
}


def country_name(code):
    return COUNTRIES.get((code or "").upper(), code or "Unknown")


def parse_ua(ua):
    ua = ua or ""
    if "iPad" in ua or "Tablet" in ua or ("Android" in ua and "Mobile" not in ua):
        device = "Tablet"
    elif re.search(r"Mobi|iPhone|Android", ua):
        device = "Mobile"
    else:
        device = "Desktop"
    for pat, name in [(r"Instagram", "Instagram app"), (r"FBAN|FBAV", "Facebook app"), (r"TikTok|musical_ly", "TikTok app"),
                      (r"Edg/", "Edge"), (r"OPR/|Opera", "Opera"), (r"SamsungBrowser", "Samsung Internet"),
                      (r"CriOS|Chrome/", "Chrome"), (r"FxiOS|Firefox/", "Firefox"), (r"Safari/", "Safari")]:
        if re.search(pat, ua):
            browser = name
            break
    else:
        browser = "Other"
    if re.search(r"iPhone|iPad|iPod", ua):
        os_name = "iOS"
    elif "Android" in ua:
        os_name = "Android"
    elif "Windows" in ua:
        os_name = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Other"
    return device, browser, os_name


SOURCES = [
    ("google.", "Google"), ("bing.", "Bing"), ("duckduckgo.", "DuckDuckGo"), ("yahoo.", "Yahoo"), ("yandex.", "Yandex"),
    ("baidu.", "Baidu"), ("instagram.", "Instagram"), ("facebook.", "Facebook"), ("fb.", "Facebook"), ("t.co", "X / Twitter"),
    ("twitter.", "X / Twitter"), ("x.com", "X / Twitter"), ("tiktok.", "TikTok"), ("whatsapp.", "WhatsApp"),
    ("linkedin.", "LinkedIn"), ("lnkd.in", "LinkedIn"), ("youtube.", "YouTube"), ("pinterest.", "Pinterest"),
    ("reddit.", "Reddit"), ("chatgpt.com", "ChatGPT"), ("openai.", "ChatGPT"), ("perplexity.", "Perplexity"),
    ("claude.ai", "Claude"), ("gemini.google", "Gemini"), ("tripadvisor.", "Tripadvisor"), ("vercel.app", "Direct"),
]


def classify_source(referrer, utm_source="", own_host=""):
    if utm_source:
        return utm_source.strip()[:60].title() if utm_source.islower() else utm_source.strip()[:60]
    if not referrer:
        return "Direct"
    host = (urllib.parse.urlparse(referrer).hostname or "").lower()
    if not host or (own_host and host == own_host.lower()):
        return ""  # moving within the site
    for needle, name in SOURCES:
        if needle in host:
            return name
    return host.removeprefix("www.")[:60]


def geo(request):
    """Country / region / city from Vercel's edge headers (no IP addresses are stored)."""
    h = request.headers
    city = urllib.parse.unquote(h.get("x-vercel-ip-city", ""))
    return (h.get("x-vercel-ip-country", "")[:2].upper(), urllib.parse.unquote(h.get("x-vercel-ip-country-region", ""))[:60], city[:80])


def is_bot(request):
    return bool(BOT_RE.search(request.headers.get("user-agent", "")))


def request_snapshot(request):
    """Details recorded with a booking request: device, location and how the guest found the site."""
    from .models import Visitor

    device, browser, os_name = parse_ua(request.headers.get("user-agent", ""))
    country, region, city = geo(request)
    data = {"device": device, "browser": browser, "os": os_name, "country": country, "city": city,
            "language": request.headers.get("accept-language", "").split(",")[0][:20]}
    if request.COOKIES.get("is_consent") == "all":
        try:
            visitor = Visitor.objects.get(pk=request.COOKIES.get("is_vid", ""))
        except Exception:
            visitor = None
        if visitor:
            data.update(visitor=visitor, source=visitor.first_source, landing_path=visitor.landing_path,
                        campaign=visitor.first_campaign)
            if not country:
                data["country"], data["city"] = visitor.country, visitor.city
    return data
