import requests
from bs4 import BeautifulSoup

URL = "https://www.nyurban.com/?page_id=400&filter_id=1&gametypeid=1"
TARGET_DAY = "Fri, Feb 06"  # example day to check

def check_availability():
    response = requests.get(URL)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    page_text = soup.get_text()
    if TARGET_DAY in page_text and "Available" in page_text:
        print(f"✅ Spot available for {TARGET_DAY}!")
        # Here you can trigger email/sms/webhook
    else:
        print(f"❌ Still not available for {TARGET_DAY}...")

if __name__ == "__main__":
    check_availability()
