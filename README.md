# Photo Portfolio

Django site for a photographer: a public portfolio, private client albums, and
full-resolution delivery through Cloudinary.

## Why not Google Drive

The site used to serve images straight from Google Drive. That cannot work, and
it is not a configuration mistake — Google enforces it:

```
$ curl -sSI -L "https://drive.google.com/uc?id=<id>&export=download"
cross-origin-resource-policy: same-site      # browsers refuse to render it cross-origin
content-disposition: attachment              # served as a download, not an image

$ curl -H "Referer: https://www.ruansonder-r.com/" -H "Sec-Fetch-Site: cross-site" ...
HTTP 403                                     # hotlinking is blocked outright
```

`curl` without those headers returns 200, which is why the URLs looked fine when
tested by hand while every `<img>` on the live site rendered blank.

On top of that, Drive only ever serves the untouched original. Sampled masters
ran 2–14 MB each; a single page pulled roughly 80 MB.

## How images work now

Masters are uploaded to Cloudinary once and indexed in Postgres. Rendering a
page is **pure SQL** — every URL is built by local string formatting and HMAC
signing, so no external API is called while serving a request.

| | Before | After |
|---|---|---|
| Per-photo transfer | 2–14 MB original | ~47 KB JPEG, ~18 KB AVIF at 800px |
| API calls per page | 1 Drive call per gallery | 0 |
| DB queries per gallery | n/a | 3, regardless of photo count |

Each `<img>` ships a `srcset` of 400/800/1200/1600/2400px renditions with
`f_auto` (AVIF/WebP negotiated per browser) and `q_auto`. The 800px and 1600px
versions are pre-rendered at upload time via Cloudinary *eager* transformations,
so the first visitor never waits on a cold transform.

- **Public galleries** use `upload` delivery — plain cacheable CDN URLs.
- **Client albums** use `authenticated` delivery with signed URLs. The signature
  covers the public_id and transformation, so an album photo cannot be fetched
  by guessing. Album pages are sent `no-store, private`.

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in CLOUDINARY_URL
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

`DATABASE_URL` is optional locally — without it the project uses SQLite.

### Cloudinary

Create an account, then copy the **API Environment variable** from the dashboard
into `.env` as `CLOUDINARY_URL=cloudinary://<key>:<secret>@<cloud>`.

## Getting photos in

Upload straight from your camera exports — nothing passes through Drive, so the
masters keep their full resolution:

```bash
# Public gallery
python manage.py upload_photos ~/Exports/Smith_Wedding --gallery "Smith Wedding"

# Private client album
python manage.py upload_photos ~/Exports/Smith_Wedding --album "Smith Wedding" --date 2025-03-09

# Homepage carousel (hidden gallery, photos flagged as featured)
python manage.py upload_photos ~/Exports/Best_Of --gallery Featured --unpublished --featured

python manage.py upload_photos <dir> --gallery X --dry-run   # preview
python manage.py upload_photos <dir> --gallery X --replace   # re-upload a gallery
```

### One-time import from Drive

Only needed to bring the existing library across. Set `GOOGLE_DRIVE_CREDENTIALS`
(the service-account JSON) first.

```bash
python manage.py migrate_from_drive --dry-run     # show the plan
python manage.py migrate_from_drive --limit 5     # try a handful
python manage.py migrate_from_drive               # everything
```

Mapping: `Public_Portfolio/public/*` → homepage carousel,
`Public_Portfolio/<Name>/*` → public gallery, `Private_Albums/<Name>/*` → client album.

Once this has run, `google-auth` and `google-api-python-client` can be dropped
from `requirements.txt`.

## Client albums

Create one in `/admin/`, upload into it, then share `/album/<uuid>/`. The UUID is
the secret. Untick **is active** to revoke a link immediately, or set
**expires at** for an automatic cutoff — both make the URL return 404.

"Download all" redirects to a Cloudinary-generated ZIP, so a 400 MB album never
passes through the web process.

## Layout

```
core/       storage seam (storage.py), Photo index, ingest, upload commands
portfolio/  public galleries
albums/     private client albums
templates/  base + partials/photo_grid.html + partials/lightbox.html
static/     hand-written CSS/JS (no build step)
```

`core/storage.py` is the only module that imports `cloudinary`. Swapping to
ImageKit, S3 or R2 means writing one class with the same methods.

## Tests

```bash
python manage.py test
```

## Deployment (Vercel)

Static files are served by WhiteNoise from inside the WSGI app, because Vercel's
Python runtime publishes no static directory — that was the cause of the
`/static/*` 404s that left the live site with no CSS or JS at all.

Required environment variables:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | Required when `DEBUG` is off; startup fails loudly without it |
| `DATABASE_URL` | Postgres connection string |
| `CLOUDINARY_URL` | `cloudinary://<key>:<secret>@<cloud>` |
| `DEBUG` | Leave unset (defaults to off) |
| `ALLOWED_HOSTS` | Optional; sensible defaults are built in |
