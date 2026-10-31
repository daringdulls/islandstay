"""AI assist for the back office: research an island or a business on the web and draft its details.

Claude searches and reads web pages (Anthropic's server-side web search / fetch tools), then returns the
fields through a strict tool so the shape is always valid. Nothing is saved: the editor reviews each
suggestion and applies it to the form. Needs ANTHROPIC_API_KEY.
"""
import logging
import os

log = logging.getLogger(__name__)
MODEL = os.environ.get("AI_ASSIST_MODEL", "claude-opus-5-5")

# field name -> (kind, guidance). kind: text | lines | int | decimal | bool | choice
ISLAND_FIELDS = {
    "tagline": ("text", "One-line hook, under 90 characters, specific to this island (e.g. 'Whale shark trips from a friendly fishing island')."),
    "overview": ("text", "2-3 short paragraphs introducing the island for a traveller: location, size, character, what daily life is like."),
    "famous_for": ("lines", "What the island is known for, one item per line, 3-6 items."),
    "what_to_expect": ("lines", "Practical expectations for visitors, one per line, 3-6 items."),
    "getting_there": ("text", "How to reach it from Velana International Airport / Malé: ferry, speedboat, domestic flight, times."),
    "best_time_to_visit": ("text", "Short, e.g. 'December to April (dry season); whale sharks all year'."),
    "transfer_types": ("text", "Comma separated from: speedboat, ferry, seaplane, domestic_flight, road."),
    "transfer_time": ("text", "Typical fastest transfer from the airport, e.g. '≈1 hr 30 min by speedboat'."),
    "distance_from_airport_km": ("int", "Approximate straight-line distance from Velana International Airport in km."),
    "population": ("int", "Latest census population."),
    "population_year": ("int", "Year of that population figure."),
    "area_km2": ("decimal", "Land area in square kilometres."),
    "latitude": ("decimal", "Latitude in decimal degrees."),
    "longitude": ("decimal", "Longitude in decimal degrees."),
    "nearest_airport": ("text", "Nearest airport name with code, e.g. 'Maamigili (VAM)'."),
    "nearest_airport_km": ("int", "Distance to that airport in km."),
    "has_bikini_beach": ("bool", "Does the island have a designated bikini (tourist) beach?"),
    "has_atm": ("bool", "Is there an ATM?"),
    "has_hospital": ("bool", "Is there a health centre, clinic or hospital?"),
    "has_pharmacy": ("bool", "Is there a pharmacy?"),
    "has_police": ("bool", "Is there a police station?"),
    "has_supermarket": ("bool", "Are there shops or a supermarket?"),
    "has_4g": ("bool", "Is there 4G mobile data?"),
    "facilities_notes": ("lines", "Other facilities (mosques, sports ground, water sports centre…), one per line."),
    "local_rules": ("lines", "Rules visitors must follow on this local island (dress code, alcohol, drones, Friday prayers…), one per line."),
    "accessibility": ("lines", "Notes for visitors with reduced mobility or families with prams, one per line."),
    "wikipedia_title": ("text", "Exact English Wikipedia article title for the island, if one exists."),
}

LISTING_FIELDS = {
    "island_name": ("text", "Name of the Maldivian island where the business is."),
    "short_description": ("text", "One sentence under 180 characters for listing cards."),
    "description": ("text", "2-3 short paragraphs describing the business for travellers: rooms or services, setting, what's included."),
    "room_count": ("int", "Number of rooms (stays only)."),
    "max_guests": ("int", "Maximum guests (stays only)."),
    "star_rating": ("int", "Official star rating 1-5, only if officially rated."),
    "distance_to_beach_m": ("int", "Walking distance to the nearest beach in metres."),
    "check_in_time": ("text", "e.g. '14:00'."),
    "check_out_time": ("text", "e.g. '12:00'."),
    "house_rules": ("lines", "House rules, one per line."),
    "contact_name": ("text", "Owner or manager name, only if publicly listed."),
    "contact_email": ("text", "Public booking email."),
    "contact_phone": ("text", "Public phone in international format, e.g. +960 777 1234."),
    "whatsapp": ("text", "Public WhatsApp number in international format."),
    "website": ("text", "Official website URL."),
    "facebook": ("text", "Facebook page URL."),
    "instagram": ("text", "Instagram profile URL."),
    "address": ("text", "Street address / ward on the island."),
    "cuisine": ("text", "Restaurants only: e.g. 'Maldivian, seafood'."),
    "opening_hours": ("text", "Restaurants and services: e.g. 'Daily 7:00–23:00'."),
    "serves_breakfast": ("bool", "Restaurants: serves breakfast?"),
    "delivery": ("bool", "Restaurants: delivers to guest houses?"),
}

SYSTEM = """You research places in the Maldives for Island Stay, a guide to local inhabited islands where travellers \
message guest houses, excursion operators and cafés directly.

Use web search and web fetch to find reliable, current information: official websites, the business's own social \
pages, booking sites, Wikipedia, the Maldives Bureau of Statistics census, government and tourism sources. \
Cross-check facts that matter to travellers (transfers, facilities, rules, contact details).

When you have enough, call submit_details exactly once with every field.
- Only state what your sources support. If you can't confirm a value, leave it as an empty string (or "unknown" for yes/no).
- Never invent phone numbers, emails, prices or star ratings.
- Numbers as plain digits ("936", "2.4"), no units.
- Lists: one item per line, no bullets.
- Write in British English for a traveller: warm, direct and practical. Sentence case. No emoji.
- Avoid the words paradise, hidden gem, luxury escape and unforgettable; describe the specific thing instead.
- Explain a Dhivehi word the first time you use it (e.g. dhoni, a traditional boat).
- List every source URL you relied on in sources."""


def _schema(fields):
    props = {}
    for name, (kind, guide) in fields.items():
        if kind == "bool":
            props[name] = {"type": "string", "enum": ["yes", "no", "unknown"], "description": guide}
        else:
            props[name] = {"type": "string", "description": guide + (" Digits only, or empty." if kind in ("int", "decimal") else " Empty if unknown.")}
    props["sources"] = {"type": "array", "items": {"type": "string"}, "description": "URLs of the sources used."}
    props["notes"] = {"type": "string", "description": "Anything the editor should double-check, or conflicting information. Empty if none."}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


class AssistError(Exception):
    pass


def research(kind, name, context=""):
    """kind: 'island' or 'listing'. Returns {"fields": {...}, "sources": [...], "notes": str}."""
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise AssistError("AI assist needs an Anthropic API key. In Vercel add ANTHROPIC_API_KEY under Settings, "
                          "Environment Variables, then redeploy.")
    from .models import ActivityType

    fields = dict(ISLAND_FIELDS if kind == "island" else LISTING_FIELDS)
    names = ", ".join(ActivityType.objects.order_by("name").values_list("name", flat=True))
    fields["activities" if kind == "island" else "activity_types"] = (
        "lines", f"Activities possible on or around it, one per line, chosen only from this list: {names}.")
    submit = {"name": "submit_details", "description": "Submit the researched details for the editor to review.",
              "strict": True, "input_schema": _schema(fields)}
    what = "the local island" if kind == "island" else "the business (guest house, hotel, excursion operator, dive centre, transfer service or restaurant)"
    prompt = (f"Research {what} “{name}” in the Maldives{f' ({context})' if context else ''} and draft its Island Stay "
              f"details. Then call submit_details.")
    messages = [{"role": "user", "content": prompt}]
    client = anthropic.Anthropic(timeout=240.0, max_retries=1)
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 4}, submit]

    nudged = False
    plain = False  # switched on if the account rejects the optional fallback beta or strict tools
    for _ in range(7):
        try:
            if plain:
                response = client.messages.create(
                    model=MODEL, max_tokens=16000, system=SYSTEM, messages=messages, tools=tools,
                    tool_choice={"type": "auto"}, output_config={"effort": "medium"})
            else:
                response = client.beta.messages.create(
                    model=MODEL, max_tokens=16000, system=SYSTEM, messages=messages, tools=tools,
                    tool_choice={"type": "auto"}, output_config={"effort": "medium"},
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                )
        except anthropic.AuthenticationError:
            raise AssistError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in Vercel (no spaces, starts with sk-ant-).")
        except anthropic.PermissionDeniedError as exc:
            raise AssistError(f"The Anthropic account isn't allowed to do this: {_api_message(exc)}")
        except anthropic.RateLimitError:
            raise AssistError("The AI service is busy (rate limit). Try again in a minute.")
        except anthropic.BadRequestError as exc:
            msg = _api_message(exc)
            log.warning("AI assist 400: %s", msg)
            low = msg.lower()
            if "credit" in low or "billing" in low or "balance" in low:
                raise AssistError("Your Anthropic account has no credit. Add credit at platform.claude.com, "
                                  "Settings, Billing, then try again (it can take a few minutes to activate).")
            if not plain:
                # Optional features (fallback beta, strict tools) may not be enabled for this account: retry without them.
                plain = True
                tools = [dict(t, strict=False) if t.get("name") == "submit_details" else t for t in tools]
                tools[-1].pop("strict", None)
                continue
            raise AssistError(f"The AI service rejected the request: {msg}")
        except anthropic.APIStatusError as exc:
            log.exception("AI assist failed")
            raise AssistError(f"The AI service returned an error ({exc.status_code}): {_api_message(exc)}")
        except anthropic.APIConnectionError:
            raise AssistError("Couldn't reach the AI service. Try again shortly.")

        if response.stop_reason == "refusal":
            raise AssistError("The AI declined this request. Try a more specific name.")
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_details":
                data = dict(block.input)
                return {"fields": {k: str(data.get(k, "") or "") for k in fields}, "sources": data.get("sources") or [],
                        "notes": data.get("notes", "")}
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            continue  # server-side search loop paused: resend and it resumes
        if nudged:
            break
        messages.append({"role": "user", "content": "Please call submit_details now with what you found."})
        nudged = True
    raise AssistError("The AI couldn't finish the research. Try again, or add more detail to the name.")


def _api_message(exc):
    """The human-readable reason from an Anthropic API error."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if err.get("message"):
            return str(err["message"])[:300]
    return str(getattr(exc, "message", exc))[:300]
