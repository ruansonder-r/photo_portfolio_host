## Drive → GCS Mirroring and Image Delivery

This app can serve high‑resolution images from Google Cloud Storage (GCS) while keeping your current workflow of adding/removing albums by creating folders in Google Drive.

You can postpone the GCS setup. If GCS isn’t configured, the app will continue using Google Drive high‑quality links in production and local files in development.

### What stays the same
- You keep managing albums by creating/removing folders in Google Drive.
- The app lists folders/files via the Google Drive API at runtime (prod) or syncs locally in dev.

### What changes when GCS is enabled
- A scheduled Google Cloud Storage Transfer Service (STS) job mirrors Drive folders into a GCS bucket.
- Public images are served from a public GCS URL (or via CDN).
- Private images are served via short‑lived signed GCS URLs.

---

## Your current defaults in settings
- `GCS_PUBLIC_PREFIX=ruansonder-r_public_portfolio` (adjust if your STS copies a different top‑level path)
- `GCS_PRIVATE_PREFIX=Private_Albums`
- Fallback: when GCS envs are missing, the app uses high‑quality Drive links automatically.

---

## Required services
1) Google Cloud Storage (two buckets recommended)
   - Public bucket for `Public_Portfolio` (public read)
   - Private bucket for `Private_Albums` (private objects)
2) Storage Transfer Service (Drive → GCS mirroring)

---

## Setup steps (when billing allows)

### 1) Create buckets
- Public bucket example: `my-portfolio-public`
- Private bucket example: `my-portfolio-private`

Public bucket access:
- Easiest: enable uniform bucket‑level access, allow public reads for objects (grant `allUsers: Storage Object Viewer`).
- Test a future URL format: `https://storage.googleapis.com/my-portfolio-public/ruansonder-r_public_portfolio/public/<file>`

### 2) Mirror Drive → GCS with Storage Transfer Service
- Google Cloud Console → Storage Transfer Service → Create transfer.
- Source: Google Drive. Authorize the Drive account that owns your folders.
- Select root folder for public: `Public_Portfolio` (includes `public` and any gallery subfolders).
- Destination: your public bucket. Destination path: leave at root to retain top‑level folder. This yields objects like:
  - `ruansonder-r_public_portfolio/public/<file>` (if you later rename or need a different top folder, adjust `GCS_PUBLIC_PREFIX` accordingly)
- Options:
  - Overwrite when modified
  - Optionally delete in destination when deleted in source
- Schedule: daily/hourly as needed.

Repeat for private (optional now or later):
- Source: `Private_Albums`
- Destination: `my-portfolio-private`
- Keep folder structure in objects: `Private_Albums/<album_folder>/<file>`

### 3) Add environment variables
Set these where you deploy (e.g., Vercel project env settings):

```
# Public images
GCS_PUBLIC_BASE_URL=https://storage.googleapis.com/my-portfolio-public
GCS_PUBLIC_PREFIX=ruansonder-r_public_portfolio

# Private images (only if/when you enable private delivery via signed URLs)
GCS_PRIVATE_BUCKET=my-portfolio-private
GCS_PRIVATE_PREFIX=Private_Albums
GCS_SIGNED_URL_HOURS=6

# Service account JSON (only needed for signed URLs to the private bucket)
GCP_SERVICE_ACCOUNT_JSON={
  "type": "service_account",
  ...
}
```

Notes:
- `GCS_PUBLIC_PREFIX` must match the top folder actually present in your bucket. If STS keeps the Drive folder name `Public_Portfolio` as the top‑level, set this to `Public_Portfolio` instead of `ruansonder-r_public_portfolio`.
- If you later front with Cloud CDN/Cloudflare, set `GCS_PUBLIC_BASE_URL` to your CDN domain instead.

### 4) Dependencies and deploy
- Ensure dependencies are installed:

```
pip install -r requirements.txt
```

- Deploy normally. No migrations required.

### 5) Verify
- Wait for the first STS transfer to complete.
- Confirm objects exist in your buckets:
  - Public: `ruansonder-r_public_portfolio/public/<file>` and `ruansonder-r_public_portfolio/<gallery>/<file>`
  - Private: `Private_Albums/<album_folder>/<file>`
- Load public pages; images should come from `GCS_PUBLIC_BASE_URL`.
- For private albums, links should be time‑limited signed URLs if private envs are set; otherwise Drive links are used.

---

## How URL selection works in code
- Production, public:
  - If `GCS_PUBLIC_BASE_URL` is set → build `GCS_PUBLIC_BASE_URL/GCS_PUBLIC_PREFIX/{folder}/{file}`
  - Else → fallback to high‑quality Google Drive link
- Production, private:
  - If `GCS_PRIVATE_BUCKET` + `GCP_SERVICE_ACCOUNT_JSON` set → generate signed URL for `GCS_PRIVATE_PREFIX/{folder}/{file}`
  - Else → fallback to high‑quality Google Drive link
- Development:
  - Uses local filesystem downloads when available (see `LOCAL_IMAGE_STORAGE.md`).

---

## Path mapping examples
- Carousel (public folder):
  - Drive: `Public_Portfolio/public/<file>`
  - GCS object: `ruansonder-r_public_portfolio/public/<file>`
  - URL: `https://storage.googleapis.com/<public-bucket>/ruansonder-r_public_portfolio/public/<file>`

- Public gallery: `Public_Portfolio/<gallery>/<file>` → `ruansonder-r_public_portfolio/<gallery>/<file>`
- Private album: `Private_Albums/<album>/<file>` → signed URL for `gs://<private-bucket>/Private_Albums/<album>/<file>`

If STS preserves `Public_Portfolio` as the top‑level, set `GCS_PUBLIC_PREFIX=Public_Portfolio` and the URLs will become `.../Public_Portfolio/<folder>/<file>`.

---

## Optional improvements
- CDN in front of GCS for caching and custom domains.
- Responsive images: pre‑generate sizes as `-400w/-800w/-1600w` or use CDN resizing (Cloudflare).

---

## Troubleshooting
- GCS 403 for public images: bucket/objects not publicly readable or using wrong base URL.
- 404 from GCS: prefix mismatch; check `GCS_PUBLIC_PREFIX` vs actual bucket paths.
- Private signed URL failures: service account lacks `storage.objects.get` on the private bucket or JSON not set.
- Still seeing Drive URLs: missing `GCS_*` envs; fallback is expected until you configure GCS.


