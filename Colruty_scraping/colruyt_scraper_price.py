import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import time

#pip install webdriver_manager
#pip install selenium-stealth

def create_driver():
    options = Options()
    options.add_argument("--headless")  # headless for speed and no popup
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/113.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )
    return driver


def get_price(driver, url):
    try:
        driver.get(url)

        # Wait until some main product container is visible
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-detail__info"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Try all relevant price classes in order
        for class_name in [
            "product__price__volume-price",
            "product__price__final-price",
            "product__price__kilo-price"
        ]:
            price_span = soup.find("span", class_=class_name)
            if price_span:
                return price_span.get_text(strip=True).replace("€\xa0", "").replace(",", ".")

        return 0
    except Exception as e:
        print(f"Error getting price for {url}: {e}")
        return 0
    # try:
    #     WebDriverWait(driver, 10).until(
    #         EC.presence_of_element_located((By.CLASS_NAME, "product__price__volume-price"))
    #     )
    #     soup = BeautifulSoup(driver.page_source, "html.parser")
    #     price_span = soup.find("span", class_="product__price__volume-price")
    #     if price_span:
    #         return price_span.get_text(strip=True).replace("€\xa0", "")
    #     else:
    #         return 0
    # except Exception as e:
    #     print(f"Error getting price for {url}: {e}")
    #     return 0


def scrape_all_prices(urls, save_path):
    driver = create_driver()
    data = []
    for x in urls:
        key = list(x.keys())[0]
        url = str(list(x.values())[0])
        print(f"Trying URL:{url!r}")
        if url:
            price = get_price(driver, url)
        else:
            price = 0
        data.append({"Ingredient":key,"url": url, "price": price})
        time.sleep(1)  # small delay to be polite
    driver.quit()
    df = pd.DataFrame(data)
    df.to_excel(save_path, index=False)
    return df
