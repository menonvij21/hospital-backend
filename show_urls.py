import requests
from bs4 import BeautifulSoup
from collections import OrderedDict

def get_unique_urls():
    url = "https://universalhospitals.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Adjust selector based on your actual HTML structure
    links = soup.select('a[href*="/speciality/"]')
    
    # Deduplicate: keep first occurrence of each URL
    unique = OrderedDict()
    for link in links:
        href = link.get('href')
        if href and href not in unique:
            unique[href] = {
                'url': href,
                'text': link.get_text(strip=True)
            }
    
    return list(unique.values())

def main():
    specialties = get_unique_urls()
    
    print(f"Total unique specialty URLs found: {len(specialties)}\n")
    
    # Display
    for i, item in enumerate(specialties, 1):
        print(f"{i}. {item['text']}")
        print(f"   URL: {item['url']}\n")
    
    # Save to file
    with open('unique_specialties.txt', 'w', encoding='utf-8') as f:
        for item in specialties:
            f.write(f"{item['url']}\n")
    
    print("✓ Saved to unique_specialties.txt")

if __name__ == "__main__":
    main()