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

- Site: http://localhost:8000
- Admin back office: http://localhost:8000/admin/
- Demo owner login: `owner@demo.mv` / `demo12345`

Run the tests: `python manage.py test`

## What's included

**Public site**
- Home: island search, featured islands, browse by experience, featured stays & operators, atolls.
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
- "Suggest an island" for islands not yet in the system.

**Admin back office (`/admin/`)**
- Manage atolls, islands (all guide content, activities, facts, cover photo), activity types, amenities.
- Moderation queue for listings: bulk **Approve / Reject / Suspend** actions; owners are emailed automatically.
  Mark listings as *verified* or *featured*.
- View all enquiries, users/business profiles and island suggestions.

## Configuration (environment variables)

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required in production |
| `DJANGO_DEBUG` | `0` in production |
| `DJANGO_ALLOWED_HOSTS` | e.g. `islandstay.mv,www.islandstay.mv` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | e.g. `https://islandstay.mv` |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` to send real email (default prints to console) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | SMTP settings |
| `ADMIN_NOTIFY_EMAILS` | Comma-separated emails notified when a new listing is submitted |

## Notes
- Island facts in the seed command are a starting point; transfer times are approximate. Review them in the admin.
- Demo listings (Coral Breeze Inn, etc.) are fictional — delete them before launch.
- For production: PostgreSQL, `collectstatic` behind nginx/WhiteNoise, gunicorn, and media storage (e.g. S3).
