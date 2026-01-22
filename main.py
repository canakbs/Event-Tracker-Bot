import time
import requests
import os
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# ==========================================
# ⚙️ AYARLAR
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # Kendi chat ID'niz

# Daha önce gönderilen linkleri tutmak için basit dosya sistemi
KAYIT_DOSYASI = "gonderilen_linkler.txt"

# ==========================================
# 🛠 YARDIMCI FONKSİYONLAR
# ==========================================
def rastgele_bekle(min_s=3, max_s=7):
    """İnsan gibi davranmak için rastgele bekleme"""
    sure = random.uniform(min_s, max_s)
    print(f"   ⏳ {sure:.2f} saniye bekleniyor...")
    time.sleep(sure)

def get_stealth_driver():
    """Bot yakalanmasını engelleyen özel sürücü ayarları"""
    ua = UserAgent()
    user_agent = ua.random

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={user_agent}")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

# ==========================================
# 📱 TELEGRAM FONKSİYONLARI
# ==========================================
def telegram_gonder(site, baslik, tarih, link, gorsel_url=None):
    """Telegram'a bildirim gönder"""
    print(f"\n📨 [{site}] Bildirimi Hazırlanıyor... {baslik}")
    
    caption = (
        f"🚀 <b>{site}</b>\n\n"
        f"📌 <b>{baslik}</b>\n"
        f"🗓 {tarih}\n\n"
        f"🔗 <a href='{link}'>BAŞVURU YAP</a>"
    )

    try:
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        if gorsel_url and len(gorsel_url) > 10:
            payload['photo'] = gorsel_url
            method = "sendPhoto"
        else:
            payload['text'] = caption
            method = "sendMessage"

        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
            data=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"   ✅ Telegram'a gönderildi!")
            return True
        else:
            print(f"   ❌ Hata: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Telegram hatası: {e}")
        return False

# ==========================================
# 💾 LİNK KAYIT FONKSİYONLARI
# ==========================================
def kayitli_linkleri_yukle():
    """Daha önce gönderilen linkleri dosyadan oku"""
    if os.path.exists(KAYIT_DOSYASI):
        with open(KAYIT_DOSYASI, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines()]
    return []

def link_kaydet(link):
    """Yeni linki dosyaya kaydet"""
    with open(KAYIT_DOSYASI, 'a', encoding='utf-8') as f:
        f.write(link + '\n')

# ==========================================
# 🕷️ SCRAPING FONKSİYONLARI
# ==========================================

def scrape_coderspace(driver, mevcut):
    print("\n🔍 Coderspace Taranıyor...")
    yeni_bulunan = 0
    
    try:
        driver.get("https://coderspace.io/etkinlikler")
        rastgele_bekle(5, 8)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        kartlar = soup.find_all("div", class_="event-card")

        for kart in kartlar[:8]:
            try:
                baslik_tag = kart.find("h5").find("a")
                if not baslik_tag:
                    continue
                
                href = baslik_tag.get('href', '')
                link = "https://coderspace.io" + href if not href.startswith("http") else href
                baslik = baslik_tag.text.strip()

                if link in mevcut:
                    continue

                disabled_btn = kart.find("a", class_="primary-button--disabled")
                if disabled_btn:
                    print(f"   ℹ️ Pas geçildi (Başvuru kapalı): {baslik}")
                    continue

                img_tag = kart.find("div", class_="event-card-image").find("img")
                gorsel = None
                if img_tag:
                    if img_tag.get('srcset'):
                        gorsel = img_tag.get('srcset').split(" ")[0] 
                    else:
                        gorsel = img_tag.get('src')

                tarihler = []
                info_list = kart.find("ul", class_="event-card-info")
                if info_list:
                    items = info_list.find_all("li")
                    for item in items:
                        label = item.find("span").text.strip() if item.find("span") else ""
                        val = item.find("strong").text.strip() if item.find("strong") else ""
                        if label and val:
                            tarihler.append(f"{label}: {val}")
                
                tarih_str = " | ".join(tarihler) if tarihler else "Detaylar Sitede"

                tur_tag = kart.find("span", class_="event-card-type")
                if tur_tag:
                    tarih_str = f"[{tur_tag.text.strip()}] {tarih_str}"

                if telegram_gonder("Coderspace", baslik, tarih_str, link, gorsel):
                    link_kaydet(link)
                    mevcut.append(link)
                    yeni_bulunan += 1

            except Exception as e:
                print(f"   ⚠️ Coderspace kart hatası: {e}")

        print(f"   ✅ Coderspace: {yeni_bulunan} yeni etkinlik bulundu")

    except Exception as e:
        print(f"🔥 Coderspace Genel Hata: {e}")

def scrape_anbean(driver, mevcut):
    print("\n🔍 Anbean Taranıyor...")
    yeni_bulunan = 0
    
    try:
        driver.get("https://anbeankampus.co/etkinlikler/")
        rastgele_bekle(5, 8)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        kartlar = soup.find_all("div", class_="mini-eventCard")

        for kart in kartlar[:5]:
            try:
                link_tag = kart.find("a")
                if not link_tag:
                    continue
                
                href = link_tag.get('href', '')
                link = "https://anbeankampus.co" + href if not href.startswith("http") else href
                
                if link in mevcut:
                    continue
                
                baslik_div = kart.find("div", class_="mini-eventCard-titleDescription")
                baslik = baslik_div.find("h6").text.strip() if baslik_div else "Anbean Etkinliği"
                
                img = kart.find("img", class_="mini-eventCard-HeaderImage")
                gorsel = img.get('srcset', '').split(" ")[0] if img and img.get('srcset') else (img.get('src') if img else None)
                
                tarihler = []
                date_items = kart.find_all("div", class_="mini-eventCard-dateItem")
                for item in date_items:
                    spans = item.find_all("span")
                    if len(spans) >= 2:
                        tarihler.append(f"{spans[0].text}: {spans[1].text}")
                
                tarih_str = " | ".join(tarihler) if tarihler else "Sitede kontrol ediniz"

                if telegram_gonder("Anbean", baslik, tarih_str, link, gorsel):
                    link_kaydet(link)
                    mevcut.append(link)
                    yeni_bulunan += 1
                    
            except Exception as e:
                print(f"   ⚠️ Anbean kart hatası: {e}")

        print(f"   ✅ Anbean: {yeni_bulunan} yeni etkinlik bulundu")

    except Exception as e:
        print(f"🔥 Anbean Genel Hata: {e}")

def scrape_youthall(driver, mevcut):
    print("\n🔍 Youthall Taranıyor...")
    yeni_bulunan = 0
    
    try:
        driver.get("https://www.youthall.com/tr/events/")
        rastgele_bekle(5, 9)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        kartlar = soup.find_all("div", class_="events")

        for kart in kartlar[:6]:
            try:
                link_tag = kart.find("a")
                if not link_tag and kart.parent.name == 'a':
                    link_tag = kart.parent
                if not link_tag:
                    continue

                href = link_tag.get('href', '')
                link = "https://www.youthall.com" + href if not href.startswith("http") else href
                
                if link in mevcut:
                    continue
                
                title_div = kart.find("div", class_="events__content__title")
                baslik = title_div.find("h2").text.strip() if title_div else "Youthall Etkinliği"
                
                img_div = kart.find("div", class_="events__img")
                img = img_div.find("img") if img_div else None
                gorsel = img.get('src') if img else None
                if gorsel and not gorsel.startswith("http"):
                    gorsel = "https://www.youthall.com" + gorsel

                details_div = kart.find("div", class_="events__content__details")
                tarih_str = "Detaylar Sitede"
                if details_div:
                    bilgiler = [d.text.strip() for d in details_div.find_all("div") if d.text.strip()]
                    tarih_str = " | ".join(bilgiler)

                if telegram_gonder("Youthall", baslik, tarih_str, link, gorsel):
                    link_kaydet(link)
                    mevcut.append(link)
                    yeni_bulunan += 1
                    
            except Exception as e:
                print(f"   ⚠️ Youthall kart hatası: {e}")

        print(f"   ✅ Youthall: {yeni_bulunan} yeni etkinlik bulundu")

    except Exception as e:
        print(f"🔥 Youthall Genel Hata: {e}")

def scrape_techcareer(driver, mevcut):
    print("\n🔍 Techcareer Taranıyor...")
    yeni_bulunan = 0
    
    try:
        driver.get("https://www.techcareer.net/bootcamp")
        rastgele_bekle(5, 8)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        tum_linkler = soup.find_all("a", href=True)
        bootcamp_linkleri = [a for a in tum_linkler if "/bootcamp/" in a['href'] and len(a['href']) > 25]
        
        unique_links = []
        [unique_links.append(x) for x in bootcamp_linkleri if x['href'] not in [y['href'] for y in unique_links]]

        for tag in unique_links[:5]:
            link = "https://www.techcareer.net" + tag['href']
            if link in mevcut:
                continue

            baslik = "Techcareer Bootcamp"
            parent = tag.find_parent("div")
            if parent:
                h_tags = parent.find_all(["h2", "h3", "h4", "p"])
                for h in h_tags:
                    if len(h.text) > 5:
                        baslik = h.text.strip()
                        break
            
            if baslik == "Techcareer Bootcamp":
                slug = tag['href'].split("/")[-1].replace("-", " ").title()
                baslik = f"{slug} (Bootcamp)"

            if telegram_gonder("Techcareer", baslik, "Başvurular Açık", link, None):
                link_kaydet(link)
                mevcut.append(link)
                yeni_bulunan += 1

        print(f"   ✅ Techcareer: {yeni_bulunan} yeni etkinlik bulundu")

    except Exception as e:
        print(f"⚠️ Techcareer Hatası: {e}")

# ==========================================
# 🎬 ANA PROGRAM
# ==========================================
if __name__ == "__main__":
    print("🚀 ETKİNLİK BOTU BAŞLIYOR...")
    print("📱 Sadece Telegram Bildirimi Modu")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ HATA: TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID bulunamadı!")
        print("GitHub Secrets'i kontrol edin.")
        exit(1)
    
    try:
        # Önceki kayıtları yükle
        mevcut_linkler = kayitli_linkleri_yukle()
        print(f"📂 Daha önce {len(mevcut_linkler)} etkinlik kaydedilmiş")
        
        # Selenium başlat
        driver = get_stealth_driver()
        
        # Tüm siteleri tara
        scrape_anbean(driver, mevcut_linkler)
        scrape_coderspace(driver, mevcut_linkler)
        scrape_youthall(driver, mevcut_linkler)
        scrape_techcareer(driver, mevcut_linkler)
        
        driver.quit()
        print("\n✅ TÜM İŞLEMLER TAMAMLANDI!")
        
    except Exception as e:
        print(f"\n🔥 KRİTİK HATA: {e}")
        exit(1)