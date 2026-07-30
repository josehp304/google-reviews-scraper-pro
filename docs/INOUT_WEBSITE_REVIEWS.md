# INOUT Website Google Reviews Cache

This scraper can publish reviews into the INOUT website database as:

```sql
settings.key = 'googleReviews'
```

The JSON value matches the website `ReviewsBlock` contract:

```ts
{
  reviews: { q, by, role, rating?, photo?, href? }[],
  fromGoogle: true,
  rating?: number,
  count?: number,
  mapsUri?: string
}
```

## One-Time Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `config.yaml` from `config.sample.yaml` and set the INOUT Google Maps URL:

```yaml
headless: true
sort_by: "newest"
scrape_mode: "update"
max_reviews: 25
download_images: false
use_mongodb: false
backup_to_json: true

businesses:
  - url: "https://maps.app.goo.gl/INOUTSPACES_PLACE_URL"
    custom_params:
      company: "INOUTSPACE"
      source: "Google Maps"

website_reviews:
  settings_key: "googleReviews"
  limit: 5
  min_rating: 4
```

Set the website Neon connection string in the environment:

```bash
export DATABASE_URL="postgresql://..."
```

On PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://..."
```

## Daily Command

Run both commands once per day:

```bash
python start.py scrape --config config.yaml
python start.py publish-google-reviews --config config.yaml
```

To inspect the payload without writing to Neon:

```bash
python start.py publish-google-reviews --config config.yaml --dry-run
```

If multiple places are scraped, lock publishing to INOUT's local `place_id`:

```bash
python start.py db-stats --config config.yaml
python start.py publish-google-reviews --config config.yaml --place-id PLACE_ID
```

You can also save it in `config.yaml`:

```yaml
website_reviews:
  place_id: "PLACE_ID"
  settings_key: "googleReviews"
  limit: 5
  min_rating: 4
```

## Scheduling

Windows Task Scheduler action:

```powershell
powershell.exe -ExecutionPolicy Bypass -File C:\my_code\google-reviews-scraper-pro\scripts\daily_inout_reviews.ps1
```

Linux cron example, daily at 03:15:

```cron
15 3 * * * cd /path/to/google-reviews-scraper-pro && /usr/bin/python3 start.py scrape --config config.yaml && /usr/bin/python3 start.py publish-google-reviews --config config.yaml
```

The website should read `settings.googleReviews` before falling through to the
Places API and CMS testimonial fallback.

Because this scraper writes directly to Neon, it will not call the website's
`revalidateTag("cms")`. Read this one key outside the long-lived CMS cache, or
give the review read a cache window shorter than the daily scraper cadence.

## Website Read Path

In the website repo, update `lib/google-reviews.ts:getReviews()` so the first
source is the CMS/settings database:

```ts
const cached = settings.googleReviews;
if (cached?.fromGoogle && cached.reviews?.length) return cached;
```

Keep the existing fallback chain after that:

```txt
settings.googleReviews -> Places API -> CMS voices -> shipped defaults
```
