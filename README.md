# OnlyVance28.com

Automated JD Vance news aggregator. Fetches headlines daily from Google News RSS, generates a clean static site.

## How it works

1. `build.py` fetches Google News RSS feeds for JD Vance-related queries
2. Parses headlines, sources, dates — no article content is copied (copyright-safe)
3. Generates a static HTML page in `/docs`
4. GitHub Actions runs this daily at 06:00 UTC
5. GitHub Pages serves `/docs` as the live site

## Setup

### 1. Create GitHub repo
```bash
git init
git remote add origin https://github.com/YOUR_USERNAME/onlyvance28.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

### 2. Enable GitHub Pages
- Go to repo Settings → Pages
- Source: "Deploy from a branch"
- Branch: `main`, folder: `/docs`
- Save

### 3. Custom domain
- In repo Settings → Pages → Custom domain: `onlyvance28.com`
- Add these DNS records at your domain registrar:
  - `A` record → `185.199.108.153`
  - `A` record → `185.199.109.153`
  - `A` record → `185.199.110.153`
  - `A` record → `185.199.111.153`
  - `CNAME` for `www` → `YOUR_USERNAME.github.io`

### 4. Run manually (first time)
```bash
pip install feedparser
python build.py
```
Then commit & push the generated `docs/` folder.

## Configuration

Edit `build.py` to change:
- `QUERIES` — search terms (add/remove as needed)
- `MAX_ARTICLES` — how many articles to show (default: 60)
- Schedule in `.github/workflows/daily-build.yml`

## Cost

$0. GitHub Actions free tier covers this easily. GitHub Pages is free. Domain is the only cost.

## Legal

This site only displays headlines and links back to original sources. No article content is reproduced. Similar to how Google News itself operates.
