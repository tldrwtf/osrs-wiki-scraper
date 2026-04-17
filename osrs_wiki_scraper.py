import os
import time
import json
import re
from collections import defaultdict
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# --- Configuration ---
WIKI_BASE_URL = "https://oldschool.runescape.wiki"
ID_PAGES = {
    "items": "/w/Item_IDs",
    "objects": "/w/Object_IDs",
    "npcs": "/w/NPC_IDs"
}

OUTPUT_DIR = "./data"
RATE_LIMIT_SECONDS = 1.0
# The Wiki requires a descriptive User-Agent with contact info
REQUEST_HEADERS = {
    "User-Agent": "OSRS_Wiki_Scraper_Script - contact@example.com",
    "Accept-Encoding": "gzip"
}


def fetch_and_parse(url):
    """Fetches a URL and returns the BeautifulSoup parsed HTML."""
    print(f"Fetching: {url}")
    response = requests.get(url, headers=REQUEST_HEADERS)
    response.raise_for_status()
    time.sleep(RATE_LIMIT_SECONDS)  # Polite request pacing
    return BeautifulSoup(response.text, 'html.parser')

def extract_ids_from_page(soup, id_to_name, name_to_id):
    """Extracts ID and Name mappings from standard wikitables on the page."""
    tables = soup.find_all('table', class_='wikitable')
    
    for table in tables:
        header_row = table.find('tr')
        if not header_row:
            continue
            
        headers = [th.text.strip().lower() for th in header_row.find_all(['th', 'td'])]
        
        id_idx, name_idx = -1, -1
        for i, header in enumerate(headers):
            if any(x in header for x in ['item', 'npc', 'object', 'name']):
                if 'id' in header:
                    id_idx = i
                else:
                    name_idx = i
            elif 'id' in header:
                id_idx = i
                
        if id_idx == -1 and len(headers) >= 2:
            id_idx = 1
        if name_idx == -1 and len(headers) >= 1:
            name_idx = 0
            
        if id_idx == -1 or name_idx == -1:
            continue
            
        rows = table.find_all('tr')[1:] # Skip header row
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) <= max(id_idx, name_idx):
                continue
                
            name_text = cells[name_idx].get_text(strip=True)
            id_cell = cells[id_idx]
            
            id_link = id_cell.find('a', class_='text')
            if id_link:
                id_text = id_link.get_text(strip=True)
            else:
                id_text = id_cell.get_text(strip=True)
            
            raw_ids = id_text.replace(',', ' ').split()
            
            for raw_id in raw_ids:
                if raw_id.isdigit() and name_text:
                    entity_id = int(raw_id)
                    id_to_name[entity_id] = name_text
                    if entity_id not in name_to_id[name_text]:
                        name_to_id[name_text].append(entity_id)

def scrape_id_category(category_path):
    """Scrapes an ID category, handling potential pagination."""
    id_to_name = {}
    name_to_id = defaultdict(list)
    
    current_url = urljoin(WIKI_BASE_URL, category_path)
    visited_urls = set()
    
    while current_url and current_url not in visited_urls:
        visited_urls.add(current_url)
        try:
            soup = fetch_and_parse(current_url)
            extract_ids_from_page(soup, id_to_name, name_to_id)
            
            next_link = soup.find('a', string=lambda text: text and 'next' in text.lower() and 'page' in text.lower())
            if next_link and next_link.get('href'):
                current_url = urljoin(WIKI_BASE_URL, next_link['href'])
            else:
                current_url = None
                
        except Exception as e:
            print(f"Error processing {current_url}: {e}")
            break
            
    sorted_name_to_id = {name: sorted(ids) for name, ids in name_to_id.items()}
    return {"id_to_name": id_to_name, "name_to_id": sorted_name_to_id}

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    # 1. Scrape IDs
    for category, path in ID_PAGES.items():
        print(f"\n--- Starting ID extraction for {category.upper()} ---")
        data = scrape_id_category(path)
        
        id_to_name_path = os.path.join(OUTPUT_DIR, f"{category}_id_to_name.json")
        with open(id_to_name_path, "w", encoding="utf-8") as f:
            json.dump(data["id_to_name"], f, indent=2, ensure_ascii=False)
            
        name_to_id_path = os.path.join(OUTPUT_DIR, f"{category}_name_to_id.json")
        with open(name_to_id_path, "w", encoding="utf-8") as f:
            json.dump(data["name_to_id"], f, indent=2, ensure_ascii=False)
            
        print(f"Completed {category}: Extracted {len(data['id_to_name'])} unique IDs.")

if __name__ == "__main__":
    main()
