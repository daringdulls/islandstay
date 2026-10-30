# IslandStay Maldives — local island OTA

A directory-style online travel platform for the Maldives. Every local island has its own guide page
(what it's famous for, what to expect, activities, getting there), and guest houses, hotels, resorts and
local service providers list themselves **under an island**. Travellers send booking/service requests
**directly to the owner** — no availability calendar, no payments.

Built with Django (Python) + SQLite (swap to PostgreSQL for production).

## Quick start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_maldives --demo      # atolls, 22 islands, activities, amenities + demo listings
python manage.py createsuperuser
python manage.py runserver
```

Optional, once your network can reach Wikipedia: add a freely licensed cover photo to every island,
with the photographer and licence recorded and shown on the site:

```bash
python manage.py fetch_island_photos
```

- Site: http://localhost:8000
- Admin back office: http://localhost:8000/admin/
- Demo owner login: `owner@demo.mv` / `demo12345`

Run the tests: `python manage.py test`

## What's included

The site is organised around six things a visitor needs on each island:

| Feature | Where |
|---|---|
| **Stays** — guest houses, hotels, villas, resorts | `/stays/`, island page → Stays |
| **Experiences** — snorkeling, excursions, diving, fishing | `/experiences/`, island page → Experiences |
| **Transport** — public ferries, speedboats, domestic flights, seaplanes | `/transport/`, island page → Transport |
| **Food** — restaurants & cafés (cuisine, hours, delivery) | `/food/`, island page → Food |
| **Island guides** — facilities (ATM, clinic, pharmacy, police, shops, 4G), regulations, accessibility, nearest airport | island page → Island guide |
| **Verified hosts** — owners upload a licence, admins grant the badge | dashboard → Get verified; admin → Verification filter |

**Public site**
- Home: "Where are you going?" island search that jumps straight to the chosen section of that island
  (e.g. Dhangethi → Transport), the six feature tiles, featured islands, browse by experience, featured stays & operators, atolls.
- `/islands/` — all islands, filter by atoll, activity, bikini beach; sort by distance / most stays.
- `/islands/<island>/` — island guide: overview, *famous for*, *what to expect*, quick facts (transfer time,
  population, bikini beach, ATM, health centre), things to do, places to stay (filter by type),
  experiences & services, getting there, best time to visit, nearby islands.
- `/atolls/` — atolls north → south, each with its islands.
- `/stays/` and `/experiences/` — cross-island search with filters (atoll, island, type, guests, price, amenity, activity).
- Listing page with rooms/packages, amenities, indicative "from" prices, contact details,
  WhatsApp button and the **booking request form** (dates, guests, room, transfer help, message).
- After sending, the guest gets a reference (e.g. `IS-7KQ2MD`) and a copy by email.

**Business owners**
- Sign up → add a listing (stay or service) tied to an island → status *Pending review*.
- Dashboard: listings with status, request counts, edit, photo gallery upload.
- Requests inbox: each request emailed to the owner (Reply-To = guest) and tracked as
  New / Replied / Confirmed / Declined / Closed with private notes; one-click email / WhatsApp reply.
- Transfer operators add their routes (to any island, with schedule and fare); routes appear in that island's Transport section with a Request button.
- "Get verified": upload a tourism licence / business registration for the Verified host badge.
- "Suggest an island" for islands not yet in the system.

**Admin back office (`/admin/`)**
- Manage atolls, islands (all guide content, activities, facts, cover photo), activity types, amenities.
- Transport routes per island (public ferry / flight info maintained by admins, or linked to an operator listing).
- Verification queue: filter listings by "Requested — awaiting review", view the uploaded document, bulk "Mark as Verified host".
- Moderation queue for listings: bulk **Approve / Reject / Suspend** actions; owners are emailed automatically.
  Mark listings as *verified* or *featured*.
- View all enquiries, users/business profiles and island suggestions.

## Deploying to Render

The repository includes a Render Blueprint (`render.yaml`) that creates the website and a Postgres database.

1. Sign in at https://render.com with your GitHub account.
2. Click **New +** then **Blueprint**, and choose the `islandstay` repository.
3. Fill in **ADMIN_EMAIL** and **ADMIN_PASSWORD** (your admin login). The email fields can stay empty for now.
4. Click **Apply**. The first build takes a few minutes. Your site is then at `https://islandstay.onrender.com`
   (or similar), with the admin at `/admin/`.

On every start, `start.sh` applies database updates, loads the island guides if the database is empty,
creates your admin account if it doesn't exist, and downloads missing island photos from Wikimedia Commons
in the background. Add `SEED_DEMO=1` as an environment variable before the first start to include the demo businesses.

The Blueprint uses Render's free plans, which are fine for trying the site:
- The free web service sleeps after 15 minutes without visitors; the next visit takes about a minute.
- The free database expires after 30 days. Upgrade it to a paid plan in Render before then to keep your data.
- Uploaded photos are lost when the service restarts. For real use, upgrade the web service to **Starter**,
  add a **Disk** mounted at `/var/data`, and set the environment variable `MEDIA_ROOT=/var/data/media`.

To send booking requests by email, fill in `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and
`DEFAULT_FROM_EMAIL` with your email provider's SMTP details (for example Brevo, Resend, or a Gmail app password).

To use your own domain, add it under the web service's **Settings** then **Custom Domains**, and add it
to the `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` environment variables
(e.g. `islandstay.mv` and `https://islandstay.mv`).

## Configuration (environment variables)

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required in production |
| `DJANGO_DEBUG` | `0` in production |
| `DATABASE_URL` | Postgres connection string (set automatically on Render). Defaults to a local SQLite file |
| `DJANGO_ALLOWED_HOSTS` | e.g. `islandstay.mv,www.islandstay.mv` (the Render address is allowed automatically) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Admin account created on first start |
| `MEDIA_ROOT` | Where uploaded photos are stored, e.g. `/var/data/media` on a Render disk |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | e.g. `https://islandstay.mv` |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` to send real email (default prints to console) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | SMTP settings |
| `ADMIN_NOTIFY_EMAILS` | Comma-separated emails notified when a new listing is submitted |
| `SHOW_PRICES` | `1` to show indicative "from" prices. Off by default: prices, price filters and price fields are hidden |

## Design

The look borrows from nautical charts: buff land, pale shoal water, depth contours and monospaced chart
annotations (atoll code, distance from Malé, census population). Islands without a photo get a drawn chart
cover instead of a placeholder. Fonts: Instrument Serif, Public Sans and JetBrains Mono (Google Fonts).
Icons: Lucide (ISC licence), bundled in `static/img/icons.svg` and used with `{% load ui %}{% icon "name" %}`.

## Island facts and photos

Island population figures come from the 2022 Maldives Population and Housing Census, with areas,
distances and history from each island's Wikipedia article. Every island page lists its sources.
Island photos come from Wikimedia Commons via `fetch_island_photos` (or the "Fetch cover photo" action in
the admin); the author, licence and source link are stored and shown with the photo.

## Notes
- Island facts, facilities and transport routes in the seed command are a starting point: times, schedules and
  facility flags are approximate. Review them in the admin before launch.
- Demo listings (Coral Breeze Inn, etc.) are fictional — delete them before launch.
- For production: PostgreSQL, `collectstatic` behind nginx/WhiteNoise, gunicorn, and media storage (e.g. S3).
