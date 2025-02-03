import selenium
from selenium import webdriver

browser = webdriver.Safari()
browser.get('https://gw.geneanet.org/lipari?lang=fr&n=bessey&p=gabrielle+denise+josephine')
page_source = browser.page_source
browser.quit()

print(page_source)

