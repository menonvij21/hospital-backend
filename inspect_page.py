import requests
from bs4 import BeautifulSoup

url = "https://universalhospitals.com/speciality/rheumatology/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

response = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

# Save HTML to file
with open('inspect_output.html', 'w', encoding='utf-8') as f:
    f.write(response.text)

print("✅ Saved! Now open inspect_output.html in your browser")
print(f"Status Code: {response.status_code}")