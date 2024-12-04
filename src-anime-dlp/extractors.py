# Import necessary modules for Selenium and ChromeDriver setup
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
import time


# ----------------------------------------------------------
# Filemoon
# ----------------------------------------------------------
def get_donload_url_Filemoon(orginal_url: str, aniworld_redict: str) -> str:
    options = webdriver.FirefoxOptions()
    options.add_argument("-profile")
    options.add_argument('/home/tzwicker/python/anime-dlp-3/firefox-profile')
    driver = webdriver.Firefox(options=options)

    driver.get(orginal_url)

    time.sleep(4)

    # clicking the courses tab in homepage.
    driver.find_element(By.XPATH, f"//a[contains(@href, '{aniworld_redict}')]").click()
    # driver.find_element(By.XPATH, "//a[contains(@class, 'watchEpisode')][.//h4[text()[contains(., 'Filemoon')]]]").click()

    time.sleep(5)

    # Access requests via the `requests` attribute
    for request in driver.requests:
        if request.response:
            link = request.url
            if "master.m3u8" in link:
                if "delivery-node" in link:
                    continue
                driver.quit()
                return link
    exit(1)


# ----------------------------------------------------------
# VOE
# ----------------------------------------------------------
def get_donload_url_VOE(aniworl_url: str) -> str:
    """need the foloing url: https://aniworld.to/redirect/..."""
    driver = webdriver.Firefox()
    driver.get(aniworl_url)
    time.sleep(4)
    # Access requests via the `requests` attribute
    for request in driver.requests:
        if request.response:
            link = request.url
            if "master.m3u8" in link:
                driver.quit()
                return link
    exit(1)


# ----------------------------------------------------------
# Vidoza
# ----------------------------------------------------------
def get_download_url_Vidoza(html_data: str) -> str:
    """finds the stramurl from Vidoza"""
    start: int = (html_data.find("<source src=")) + 13  # to remove class=row
    stop: int = start + html_data[start:].find('"')
    url: str = html_data[start:stop]
    return url


# ----------------------------------------------------------
# testing
# ----------------------------------------------------------
def test():
    url = get_donload_url_Filemoon("https://aniworld.to/anime/stream/birdie-wing-golf-girls-story/staffel-1/episode-5", "redirect/2852314")
    print(url)
