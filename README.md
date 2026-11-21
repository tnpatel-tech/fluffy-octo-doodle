# WattWise Payback

Zero-dependency Python 3 static site generator that turns the [OpenEI Utility Rate Database (URDB)](https://data.openei.org/submissions/5) into fast, SEO-indexed local electricity, EV charging, and solar payback calculator pages hosted for **$0/month** on Cloudflare Pages.

## 1. Preview Locally Right Now ($0, No API Key Needed)
```bash
cd /Users/tajpatel/Documents/utility-payback
python3 scripts/fetch_urdb.py --seed
python3 scripts/build_zip_map.py
python3 scripts/build_site.py
python3 -m http.server 8080 --directory dist
```
Open `http://localhost:8080` in your browser and test ZIP codes such as `36467`, `94103`, or `30303`.

## 2. Deploy & Automate Weekly Updates ($0 Stack)
1. Push this folder to a free public GitHub repository.
2. Grab your free credentials:
   - Free **OpenEI API key** from [OpenEI Web Services](https://openei.org/services/)
   - Free **Cloudflare Account ID** and **Cloudflare API Token** (*Cloudflare Pages: Edit* permission)
3. Add 3 GitHub Repository Secrets (`Settings -> Secrets and variables -> Actions`):
   - `OPENEI_API_KEY`
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
4. Set your live `site_url` in `data/config.json` once Cloudflare Pages assigns your domain.
5. Trigger **Weekly OpenEI URDB Sync & Cloudflare Pages Deploy** once from the GitHub **Actions** tab. After that, it refreshes rates and redeploys automatically every Monday at 06:00 UTC.
6. Submit `<your-live-domain>/sitemap.xml` to Google Search Console.

## 3. Configure Partner Links & Featured Local Listings
Update `data/config.json` with your partner URLs (`solar_quote_url`, `ev_charger_url`, and `featured_listing_url`) and add featured local installers to `data/sponsors.json`.
