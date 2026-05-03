import requests
from bs4 import BeautifulSoup
import json
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

specialty_urls = [
    {"name": "Rheumatology", "url": "https://universalhospitals.com/speciality/rheumatology/"},
    {"name": "Orthopedic Surgery & Sports Medicine", "url": "https://universalhospitals.com/speciality/orthopaedic-surgery-sports-medicine-2/"},
    {"name": "General & Laparoscopic Surgery", "url": "https://universalhospitals.com/speciality/general-laparoscopic-surgery/"},
    {"name": "Urology", "url": "https://universalhospitals.com/speciality/urology/"},
    {"name": "Dietetics", "url": "https://universalhospitals.com/speciality/dietetics/"},
    {"name": "24-Hours Laboratory", "url": "https://universalhospitals.com/speciality/24-hours-laboratory/"},
    {"name": "24-Hours Pharmacy", "url": "https://universalhospitals.com/speciality/24-hours-pharmacy/"},
    {"name": "Radiology", "url": "https://universalhospitals.com/speciality/24-hour-radiology/"},
    {"name": "24-Hour Emergency", "url": "https://universalhospitals.com/speciality/24-hour-emergency/"},
    {"name": "Intensive Care Unit", "url": "https://universalhospitals.com/speciality/intensive-care-unit/"},
    {"name": "Anaesthesiology", "url": "https://universalhospitals.com/speciality/anaesthesiology/"},
    {"name": "Cardiology", "url": "https://universalhospitals.com/speciality/cardiology/"},
    {"name": "Cardiothoracic & Vascular Surgery", "url": "https://universalhospitals.com/speciality/cardiothoracic-vascular-surgery/"},
    {"name": "Dentistry", "url": "https://universalhospitals.com/speciality/dentistery-implantology-aesthetic-dentistry/"},
    {"name": "Dermatology & Cosmetology", "url": "https://universalhospitals.com/speciality/dermatology-cosmetology/"},
    {"name": "Ear, Nose & Throat", "url": "https://universalhospitals.com/speciality/ear-nose-throat/"},
    {"name": "Gastroenterology", "url": "https://universalhospitals.com/speciality/gastroenterology/"},
    {"name": "Gastrointestinal Surgery & Obesity Surgery", "url": "https://universalhospitals.com/speciality/gastrointestinal-surgery-obesity-surgery/"},
    {"name": "General Medicine", "url": "https://universalhospitals.com/speciality/general-medicine/"},
    {"name": "Internal Medicine", "url": "https://universalhospitals.com/speciality/internal-medicine/"},
    {"name": "Interventional Radiology", "url": "https://universalhospitals.com/speciality/interventional-radiology/"},
    {"name": "Neonatology", "url": "https://universalhospitals.com/speciality/neonatology/"},
    {"name": "Nephrology", "url": "https://universalhospitals.com/speciality/nephrology/"},
    {"name": "Neurology", "url": "https://universalhospitals.com/speciality/neurology/"},
    {"name": "Neurosurgery", "url": "https://universalhospitals.com/speciality/neurosurgery/"},
    {"name": "Obstetrics & Gynecology", "url": "https://universalhospitals.com/speciality/obstetrics-gynaecology/"},
    {"name": "Ophthalmology", "url": "https://universalhospitals.com/speciality/opthalmology/"},
    {"name": "Paediatrics", "url": "https://universalhospitals.com/speciality/paediatrics/"},
    {"name": "Paediatric Surgery", "url": "https://universalhospitals.com/speciality/paediatric-surgery/"},
    {"name": "Physical Medicine & Rehabilitation", "url": "https://universalhospitals.com/speciality/physical-medicine-rehabilitation/"},
    {"name": "Plastic & Reconstructive Surgery", "url": "https://universalhospitals.com/speciality/plastic-reconstructive-surgery/"},
    {"name": "Psychiatry & Psychology", "url": "https://universalhospitals.com/speciality/psychiatry-psychology/"},
    {"name": "Pulmonary & Sleep Medicine", "url": "https://universalhospitals.com/speciality/pulmonary-sleep-medicine/"},
]

def scrape_specialty(specialty):
    try:
        response = requests.get(specialty['url'], headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Get specialty description
        description = ""
        desc_div = soup.find('div', class_=lambda x: x and any(
            word in x.lower() for word in ['content', 'description', 'about', 'text', 'detail']
        ))
        if desc_div:
            description = desc_div.get_text(strip=True)

        # Get all paragraphs for description
        if not description:
            paragraphs = soup.find_all('p')
            description = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])

        # Find all doctor links
        doctor_links = []
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            if '/doctor/' in href or '/doctors/' in href or '/physician/' in href:
                doctor_links.append({
                    'name': link.get_text(strip=True),
                    'url': href if href.startswith('http') else 'https://universalhospitals.com' + href
                })

        # Find doctor names from headings near images
        doctors = []
        
        # Look for doctor cards - try multiple patterns
        # Pattern 1: article tags
        articles = soup.find_all('article')
        for article in articles:
            name = article.find(['h2', 'h3', 'h4', 'h5'])
            img = article.find('img')
            designation = article.find('p')
            doctors.append({
                'name': name.get_text(strip=True) if name else '',
                'designation': designation.get_text(strip=True) if designation else '',
                'image': img.get('src', '') if img else '',
            })

        # Pattern 2: Look for any element with doctor name patterns
        if not doctors:
            all_headings = soup.find_all(['h2', 'h3', 'h4', 'h5'])
            for heading in all_headings:
                text = heading.get_text(strip=True)
                if text.startswith('Dr.') or text.startswith('Prof.'):
                    # Get sibling or parent info
                    parent = heading.parent
                    designation = ''
                    img_src = ''
                    
                    # Look for designation in siblings
                    next_elem = heading.find_next_sibling()
                    if next_elem:
                        designation = next_elem.get_text(strip=True)
                    
                    # Look for image
                    img = parent.find('img')
                    if img:
                        img_src = img.get('src', '')
                    
                    doctors.append({
                        'name': text,
                        'designation': designation,
                        'image': img_src,
                    })

        # Get all text content for AI agent
        full_text = soup.get_text(separator=' ', strip=True)

        return {
            'specialty': specialty['name'],
            'url': specialty['url'],
            'description': description[:1000],  # First 1000 chars
            'doctors': doctors,
            'doctor_links': doctor_links,
            'full_text': full_text[:3000],  # First 3000 chars for AI context
        }

    except Exception as e:
        print(f"❌ Error scraping {specialty['name']}: {e}")
        return None

# Scrape all specialties
print("🚀 Starting to scrape all specialties...\n")
all_data = []

for i, specialty in enumerate(specialty_urls):
    print(f"[{i+1}/{len(specialty_urls)}] Scraping: {specialty['name']}")
    data = scrape_specialty(specialty)
    if data:
        all_data.append(data)
        print(f"  ✅ Done - Found {len(data['doctors'])} doctors, {len(data['doctor_links'])} doctor links")
    time.sleep(2)

# Save to JSON
with open('hospital_data.json', 'w', encoding='utf-8') as f:
    json.dump(all_data, f, indent=2, ensure_ascii=False)

print(f"\n✅ Scraping complete!")
print(f"📁 Saved to hospital_data.json")
print(f"📊 Total specialties scraped: {len(all_data)}")

# Show summary
print("\n=== SUMMARY ===")
for data in all_data:
    print(f"\n{data['specialty']}:")
    print(f"  Doctors found: {len(data['doctors'])}")
    print(f"  Doctor links: {len(data['doctor_links'])}")
    if data['doctors']:
        for doc in data['doctors']:
            print(f"    - {doc['name']} | {doc['designation']}")