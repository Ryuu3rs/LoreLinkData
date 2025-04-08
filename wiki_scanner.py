import requests
from bs4 import BeautifulSoup
import json
import time
import re

BASE_URL = "https://wiki.wanderinginn.com"
START_URL = f"{BASE_URL}/The_Wandering_Inn_Wiki:Browse_the_Wiki"
OUTPUT_FILE = "wiki-terms.json"

visited_categories = set()
terms = {}
redirects = {}

def log(msg):
    print(msg)

def fetch_soup(url):
    try:
        time.sleep(1)
        res = requests.get(url)
        res.raise_for_status()
        return BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        log(f"❌ Failed to fetch {url}: {e}")
        return None

def parse_browse_page():
    log("🔍 Loading Browse the Wiki page...")
    soup = fetch_soup(START_URL)
    if not soup:
        return []

    links = soup.select("a[href^='/Category:']")
    categories = []

    for link in links:
        name = link.text.strip()
        href = link['href']
        if name and href.startswith("/Category:"):
            categories.append((name, BASE_URL + href))

    log(f"✅ Found {len(categories)} root categories.")
    return categories


def parse_category(url, category_path):
    if url in visited_categories:
        return
    visited_categories.add(url)

    log(f"📂 Scanning category: {category_path} ({url})")
    soup = fetch_soup(url)
    if not soup:
        return

    # Subcategories
    subcat_section = soup.find("div", {"id": "mw-subcategories"})
    if subcat_section:
        for link in subcat_section.select("a"):
            subcat_name = link.text.strip()
            subcat_url = BASE_URL + link['href']
            parse_category(subcat_url, f"{category_path} > {subcat_name}")

    # Real pages
    page_section = soup.find("div", {"id": "mw-pages"})
    if page_section:
        for link in page_section.select("a"):
            page_title = link.text.strip()
            page_url = BASE_URL + link['href']
            handle_page_entry(page_title, page_url, category_path)

def handle_page_entry(name, url, category_path):
    if name in terms or name in redirects:
        return

    soup = fetch_soup(url)
    if not soup:
        return

    content = soup.find("div", {"id": "mw-content-text"})

    # Check for redirect
    redirect_match = content.find("div", class_="redirectMsg")
    if redirect_match:
        redirect_link = content.find("a")
        if redirect_link:
            target_name = redirect_link.text.strip()
            if target_name not in terms:
                # Queue the target to be fetched if not already
                handle_page_entry(target_name, BASE_URL + redirect_link['href'], category_path)
            # Register alias
            if target_name in terms:
                terms[target_name].setdefault("aliases", []).append(name)
                redirects[name] = target_name
                log(f"🔁 Redirect: {name} ➝ {target_name} (added as alias)")
        return

    # Summary: First visible <p>
    summary = ""
    for p in content.find_all("p", recursive=True):
        text = p.get_text(strip=True)
        if text:
            summary = re.sub(r'\[\d+\]', '', text)  # remove references like [1]
            break

    terms[name] = {
        "link": url,
        "category": category_path,
        "summary": summary,
        "aliases": []
    }

    log(f"   ➕ {name} [{category_path}]")

def main():
    log("📘 Starting full scan with summaries and alias detection...")
    main_categories = parse_browse_page()

    if not main_categories:
        log("❌ Could not load main categories.")
        return

    for name, url in main_categories:
        parse_category(url, name)

    log(f"💾 Saving {len(terms)} entries to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(terms, f, indent=2, ensure_ascii=False)

    log("✅ Scan complete.")

if __name__ == "__main__":
    main()
