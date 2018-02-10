# Descrption
Crawl lyrics uploaded at Melon, a Korean music streaming website

# Usage
--bs4 : use BeautifulSoup with Selenium to crawl
--selenium : use Selenium to crawl (shows best performance)
--selenium_raw : use Selenium in a simple but raw way to crawl
--profile : crawls one artist given by stdin and prints profile of the progrma
			does not save the lyrics
--test: crawls one artist given by stdin and saves the lyrics
--rm_time_sleep: remove the manual time sleep
				 when crawling too many songs, this option may result the IP to be banned