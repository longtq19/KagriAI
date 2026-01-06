import requests

sitemaps = [
    "https://kagri.vn/sitemap.xml",
    "https://kagri.vn/sitemap_index.xml",
    "https://kagri.vn/product-sitemap.xml",
    "https://kagri.vn/wp-sitemap.xml"
]

for url in sitemaps:
    try:
        resp = requests.get(url, timeout=10)
        print(f"{url}: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Found valid sitemap: {url}")
            print(resp.text[:500])
    except Exception as e:
        print(f"Error checking {url}: {e}")
