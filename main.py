import time
import requests
import gspread
import os
import json
import random
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# ==========================================
# ⚙️ AYARLAR
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ADI = "EtkinlikTakip"

# ==========================================
# 🛠 YARDIMCI FONKSİYONLAR (Gizlilik & Bekleme)
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
    opts.add_argument("--headless") # Arka planda çalıştır
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={user_agent}")
    opts.add_argument("--window-size=1920,1080")
    
    # Selenium izlerini gizle
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    
    # Navigator.webdriver bayrağını JavaScript ile sil
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

# ==========================================
# 📊 GOOGLE SHEETS & TELEGRAM
# ==========================================
def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    else:
        creds_json = json.loads(os.environ.get("G_SHEET_CREDS"))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

def kullanicilari_guncelle(client):
    """Telegram abonelerini çeker"""
    try:
        sheet = client.open(SHEET_ADI).worksheet("Kullanicilar")
        kayitli_id_listesi = sheet.col_values(1)
        
        try:
            # Yeni gelen mesajları kontrol et
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            response = requests.get(url, timeout=10).json()
            
            if "result" in response:
                for update in response["result"]:
                    if "message" in update and "text" in update["message"]:
                        mesaj = update["message"]["text"]
                        chat_id = str(update["message"]["chat"]["id"])
                        kullanici_adi = update["message"]["from"].get("first_name", "Bilinmiyor")
                        
                        if mesaj == "/start" and chat_id not in kayitli_id_listesi:
                            sheet.append_row([chat_id, kullanici_adi, time.strftime("%Y-%m-%d")])
                            kayitli_id_listesi.append(chat_id)
                            print(f"   ➕ Yeni Abone: {kullanici_adi}")
        except: pass
        return kayitli_id_listesi
    except Exception as e:
        print(f"⚠️ Kullanıcı listesi hatası: {e}")
        return []

def link_kaydet(client, link, baslik, site):
    try:
        sheet = client.open(SHEET_ADI).worksheet("Etkinlikler")
        sheet.append_row([link, baslik, site, time.strftime("%Y-%m-%d %H:%M")])
    except: pass

def linkleri_getir(client):
    try:
        sheet = client.open(SHEET_ADI).worksheet("Etkinlikler")
        return sheet.col_values(1)
    except: return []

def herkese_gonder(abone_listesi, site, baslik, tarih, link, gorsel_url):
    print(f"\n📨 [{site}] Bildirimi Hazırlanıyor... {baslik}")
    
    caption = (
        f"🚀 <b>{site}</b>\n\n"
        f"📌 <b>{baslik}</b>\n"
        f"🗓 {tarih}\n\n"
        f"🔗 <a href='{link}'>BAŞVURU YAP</a>"
    )

    count = 0
    for ham_id in abone_listesi:
        try:
            chat_id = str(ham_id).strip().split(".")[0]
            if not chat_id.isdigit(): continue

            payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            
            if gorsel_url and len(gorsel_url) > 10:
                payload['photo'] = gorsel_url
                method = "sendPhoto"
            else:
                payload['text'] = caption
                method = "sendMessage"

            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}", data=payload, timeout=10)
            count += 1
            time.sleep(0.1) # API flood yapmamak için bekleme
        except: continue
    print(f"   ✅ {count} kişiye gönderildi.")

# ==========================================
# 🕷️ SCRAPING FONKSİYONLARI (GÜNCEL HTML'E GÖRE)
# ==========================================

def scrape_coderspace(driver, client, mevcut, aboneler):
    print("\n🔍 Coderspace Taranıyor...")
    try:
        driver.get("https://coderspace.io/etkinlikler")
        rastgele_bekle(5, 8)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Gönderdiğin HTML'e göre ana kart yapısı "event-card"
        kartlar = soup.find_all("div", class_="event-card")

        for kart in kartlar[:8]: # İlk 8 etkinliği kontrol et
            try:
                # 1. Link ve Başlık Çekme (h5 içindeki a tagi)
                baslik_tag = kart.find("h5").find("a")
                if not baslik_tag: continue
                
                href = baslik_tag.get('href', '')
                link = "https://coderspace.io" + href if not href.startswith("http") else href
                
                baslik = baslik_tag.text.strip()

                # 2. Kayıt Kontrolü (Daha önce gönderildi mi?)
                if link in mevcut: continue

                # 3. Durum Kontrolü (Başvurular kapandı mı?)
                # HTML'de "primary-button--disabled" class'ı varsa etkinlik bitmiştir.
                disabled_btn = kart.find("a", class_="primary-button--disabled")
                if disabled_btn:
                    # Opsiyonel: Eğer sadece aktifleri istiyorsak burada continue diyebiliriz.
                    # Ancak bazen "Tamamlandı" bilgisini de görmek isteyebilirsiniz.
                    # Şimdilik pas geçiyoruz (aktif değilse gönderme)
                    print(f"   ℹ️ Pas geçildi (Başvuru kapalı): {baslik}")
                    continue

                # 4. Görsel Çekme
                img_tag = kart.find("div", class_="event-card-image").find("img")
                gorsel = None
                if img_tag:
                    # srcset varsa en yüksek çözünürlüğü al, yoksa src
                    if img_tag.get('srcset'):
                        gorsel = img_tag.get('srcset').split(" ")[0] 
                    else:
                        gorsel = img_tag.get('src')

                # 5. Tarih ve Detaylar (ul > li yapısı)
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

                # 6. Tür (Bootcamp, Hackathon vs.)
                tur_tag = kart.find("span", class_="event-card-type")
                if tur_tag:
                    tarih_str = f"[{tur_tag.text.strip()}] {tarih_str}"

                herkese_gonder(aboneler, "Coderspace", baslik, tarih_str, link, gorsel)
                link_kaydet(client, link, baslik, "Coderspace")
                mevcut.append(link)

            except Exception as inner_e:
                print(f"   ⚠️ Coderspace kart hatası: {inner_e}")

    except Exception as e: print(f"🔥 Coderspace Genel Hata: {e}")

def scrape_anbean(driver, client, mevcut, aboneler):
    print("\n🔍 Anbean Taranıyor...")
    try:
        driver.get("https://anbeankampus.co/etkinlikler/")
        rastgele_bekle(5, 8)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Yapı: mini-eventCard
        kartlar = soup.find_all("div", class_="mini-eventCard")

        for kart in kartlar[:5]:
            try:
                link_tag = kart.find("a")
                if not link_tag: continue
                
                href = link_tag.get('href', '')
                link = "https://anbeankampus.co" + href if not href.startswith("http") else href
                
                if link in mevcut: continue
                
                baslik_div = kart.find("div", class_="mini-eventCard-titleDescription")
                baslik = baslik_div.find("h6").text.strip() if baslik_div else "Anbean Etkinliği"
                
                img = kart.find("img", class_="mini-eventCard-HeaderImage")
                gorsel = img.get('srcset', '').split(" ")[0] if img and img.get('srcset') else (img.get('src') if img else None)
                
                # Tarihleri topla
                tarihler = []
                date_items = kart.find_all("div", class_="mini-eventCard-dateItem")
                for item in date_items:
                    spans = item.find_all("span")
                    if len(spans) >= 2:
                        tarihler.append(f"{spans[0].text}: {spans[1].text}")
                
                tarih_str = " | ".join(tarihler) if tarihler else "Sitede kontrol ediniz"

                herkese_gonder(aboneler, "Anbean", baslik, tarih_str, link, gorsel)
                link_kaydet(client, link, baslik, "Anbean")
                mevcut.append(link)
            except: pass

    except Exception as e: print(f"🔥 Anbean Genel Hata: {e}")

def scrape_youthall(driver, client, mevcut, aboneler):
    print("\n🔍 Youthall Taranıyor...")
    try:
        # İstenilen Link
        driver.get("https://www.youthall.com/tr/events/")
        rastgele_bekle(5, 9)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Yapı: div.events
        kartlar = soup.find_all("div", class_="events")

        for kart in kartlar[:6]:
            try:
                link_tag = kart.find("a")
                if not link_tag and kart.parent.name == 'a': link_tag = kart.parent
                if not link_tag: continue

                href = link_tag.get('href', '')
                link = "https://www.youthall.com" + href if not href.startswith("http") else href
                
                if link in mevcut: continue
                
                # Başlık
                title_div = kart.find("div", class_="events__content__title")
                baslik = title_div.find("h2").text.strip() if title_div else "Youthall Etkinliği"
                
                # Görsel
                img_div = kart.find("div", class_="events__img")
                img = img_div.find("img") if img_div else None
                gorsel = img.get('src') if img else None
                if gorsel and not gorsel.startswith("http"): gorsel = "https://www.youthall.com" + gorsel

                # Tarih ve Detay
                details_div = kart.find("div", class_="events__content__details")
                tarih_str = "Detaylar Sitede"
                if details_div:
                    bilgiler = [d.text.strip() for d in details_div.find_all("div") if d.text.strip()]
                    tarih_str = " | ".join(bilgiler)

                herkese_gonder(aboneler, "Youthall", baslik, tarih_str, link, gorsel)
                link_kaydet(client, link, baslik, "Youthall")
                mevcut.append(link)
            except: pass

    except Exception as e: print(f"🔥 Youthall Genel Hata: {e}")

def scrape_techcareer(driver, client, mevcut, aboneler):
    print("\n🔍 Techcareer Taranıyor...")
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
            if link in mevcut: continue

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

            herkese_gonder(aboneler, "Techcareer", baslik, "Başvurular Açık", link, None)
            link_kaydet(client, link, baslik, "Techcareer")
            mevcut.append(link)

    except Exception as e: print(f"⚠️ Techcareer Hatası: {e}")

# ==========================================
# 🏁 ANA PROGRAM
# ==========================================
if __name__ == "__main__":
    print("🚀 BOT BAŞLIYOR... (Tüm HTML Yapıları Güncellendi)")
    
    try:
        client = get_google_client()
        aboneler = kullanicilari_guncelle(client)
        if not aboneler: print("⚠️ Abone bulunamadı, sadece tarama yapılacak.")
        
        mevcut_linkler = linkleri_getir(client)
        driver = get_stealth_driver()
        
        # Sırayla tüm siteleri tara
        scrape_anbean(driver, client, mevcut_linkler, aboneler)
        scrape_coderspace(driver, client, mevcut_linkler, aboneler)
        scrape_youthall(driver, client, mevcut_linkler, aboneler)
        scrape_techcareer(driver, client, mevcut_linkler, aboneler)
        
        driver.quit()
        print("\n✅ Tüm işlemler tamamlandı.")
        
    except Exception as e:
        print(f"\n🔥 KRİTİK HATA: {e}")
