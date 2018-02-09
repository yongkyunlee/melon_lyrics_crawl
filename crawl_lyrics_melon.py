#-*- coding:utf-8 -*-
""" Program to crawl melon lyrics
Selenium is used to get list of songs (song ids) of artist because
the list can be retrieved by javascript call.
Selenium is used to load the song info page as the info is loaded dynamically
by javascript (i.e. cannot be loaded by bs4)
BeautifulSoup and Selenium are used and compared for crawling after page is loaded
"""

import os
import re
import csv
import time
import argparse
import sys
import cProfile
import pstats
from urllib.request import urlopen

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup

import utils
from utils import PROJECT_DIR, LYRIC_DIR

MELON_URL = "http://www.melon.com"
DRIVER_WAIT = 3

class Crawler():
	""" This class is a group of functions used by both Selenium crawler and
		bs4 crawler """
	def __init__(self, driver):
		self.driver = driver
		self.wait = WebDriverWait(self.driver, DRIVER_WAIT)

	def _setup(self, artist_id):
		""" This function opens the initial aritst url """
		artist_url = MELON_URL + "/artist/song.htm?artistId={}".format(artist_id)
		self.driver.get(artist_url)

	@staticmethod
	def save_lyrics(artist, song_lyric_dict):
		""" This function saves lyrics to txt file """
		save_cnt = 0
		artist_lyric_dir = os.path.join(LYRIC_DIR, artist)
		if not os.path.isdir(artist_lyric_dir):
			os.makedirs(artist_lyric_dir)
		for song in song_lyric_dict:
			lyric = song_lyric_dict[song]
			if lyric == "":
				continue
			filename = utils.validate_filename(song)
			with open(os.path.join(artist_lyric_dir, filename), 'wb') as fpout:
				fpout.write(lyric.encode('utf8'))
			save_cnt += 1
		return save_cnt

class CrawlerSelenium(Crawler):
	""" This class groups the functions needed to crawl using selenium only """
	def __init__(self, driver):
		super(CrawlerSelenium, self).__init__(driver)

	def _crawl_songs_lyrics(self, n_song):
		""" This function crawls song name and lyric from all the songs retrived
			by pageObj
		@return - dict {song_name: lyric} """
		song_lyric_dict = dict()
		song_idx =  0
		song_end = False
		while not song_end:
			try:
				div_pagelist = self.driver.find_element_by_id("pageList")
				song_list = div_pagelist.find_element_by_tag_name("tbody")\
							.find_elements_by_tag_name("tr")
				song_cnt = len(song_list)
				btn_song_info = song_list[song_idx].find_element_by_class_name("btn_icon_detail")
				btn_song_info.click()
				self.wait.until(EC.staleness_of(btn_song_info))
				# crawl lyric from song_info page
				song = self.driver.find_element_by_class_name("song_name").text.strip()
				try:
					lyric = self.driver.find_element_by_class_name("lyric").text.strip()
				except NoSuchElementException: # no lyric uploaded
					lyric = ""
				song_lyric_dict[song] = lyric
				# return to previous page and wait until id "btn_icon_detail" and
				# class "page_num" are avaiable
				# Question: there are multiple elements of same class - how can we
				# be sure if all of such elements have been loaded
				# self.driver.execute_script("window.history.go(-1)")
				self.driver.back()
				self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "btn_icon_detail")))
				self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page_num")))
			except:
				print("{} failed".format(song_idx))
			song_idx += 1
			if n_song is not None:
				song_cnt = n_song
			if song_idx >= song_cnt:
				song_end = True
		return song_lyric_dict

	def get_song_lyric_dict(self, artist_id, n_song=None):
		""" This function returns song_lyric_dict of all songs of artist
			with input artist_id using Selenium only
		@param n_song - number of songs to crawl (crawl all if None)
		@return - dict {song_name: lyric}
		"""
		self._setup(artist_id)
		song_lyric_dict = dict()
		page_idx = 0
		page_end = False
		print("Song page progress: ", end='')
		while not page_end:
			song_lyric_dict.update(self._crawl_songs_lyrics(n_song))
			page_list = self.driver.find_element_by_class_name("page_num")\
						.find_elements_by_tag_name("a")
			page_cnt = len(page_list) + 1
			next_page = page_list[page_idx]
			next_page.click()
			self.wait.until(EC.staleness_of(next_page))
			print("{}/{} ".format(page_idx+1, page_cnt), end='')
			page_idx += 1
			if page_idx >= page_cnt - 1:
				page_end = True
		print()

		song_lyric_dict.update(self._crawl_songs_lyrics(n_song))
		return song_lyric_dict

class CrawlerSeleniumDual(Crawler):
	""" This class groups the functions need to crawl using selenium only 
		by opening dual browsers """
	def __init__(self, driver):
		super(CrawlerSeleniumDual, self).__init__(driver)

	def _get_song_id_list(self, n_song):
		""" This function gets list of song_ids from one page
		@return - list [song_id] """
		song_id_list = list()
		href_pattern = re.compile(r'javascript:melon.link.goSongDetail\(\'(?P<id>\d+)\'\);')
		div_pagelist = self.driver.find_element_by_id("pageList")
		song_list = div_pagelist.find_element_by_tag_name("tbody")\
					.find_elements_by_tag_name("tr")
		if n_song is not None:
			song_list = song_list[:n_song]
		for song in song_list:
			btn_song_info = song.find_element_by_class_name("btn_icon_detail")
			href_str = btn_song_info.get_attribute('href')
			song_id = href_pattern.match(href_str).group("id")
			song_id_list.append(song_id)
		return song_id_list

	def _crawl_song_lyric(self):
		""" This function crawls song name and lyric from the currently open
			song info page
		@return - tuple (song_name, lyric) """
		song = self.driver.find_element_by_class_name("song_name").text.strip()
		div_wrap_lyric = self.driver.find_element_by_class_name("wrap_lyric")
		try:
			div_lyric = div_wrap_lyric.find_element_by_class_name("lyric")
			lyric = div_lyric.text.strip()
		except NoSuchElementException:
			assert div_wrap_lyric.find_element_by_class_name("lyric_none") is not None
			lyric = ""
		return song, lyric

	def get_song_lyric_dict(self, artist_id, n_song=None):
		""" This function crawls and returns song_lyric_dict of all songs of
			artist with input artist_id using two browers of Selenium
		@param n_song - number of songs to crawl (crawl all if None)
		@return - dict {song_name: lyric}
		"""
		self._setup(artist_id)
		song_id_list = list()
		song_lyric_dict = dict()
		page_end = False
		page_idx = 0
		while not page_end:
			page_list = self.driver.find_element_by_class_name("page_num")\
						.find_elements_by_tag_name("a")
			page_cnt = len(page_list) + 1
			song_id_list += self._get_song_id_list(n_song)
			next_page = page_list[page_idx]
			next_page.click()
			self.wait.until(EC.staleness_of(next_page))
			page_idx += 1
			if page_idx >= page_cnt - 1:
				page_end = True
		song_id_list += self._get_song_id_list(n_song)
		# open new window and use the new window to oepn song info page that
		# contains lyrics
		second_browser = self.driver.execute_script("window.open()")
		self.driver.switch_to_window(self.driver.window_handles[1])
		print("Crwaling progress: ", end='')
		for idx, song_id in enumerate(song_id_list):
			url = MELON_URL + "/song/detail.htm?songId={}".format(song_id)
			self.driver.get(url)
			song, lyric = self._crawl_song_lyric()
			song_lyric_dict[song] = lyric
			if idx % 50 == 0 and idx != 0:
				print("{}/{} ".format(idx, len(song_id_list)), end='')
		print()
		return song_lyric_dict

class CrawlerBs4(Crawler):
	""" This function groups the functions needed to crawl using both Selenium
		and bs4 """
	def __init__(self, driver):
		super(CrawlerBs4, self).__init__(driver)

	def _get_song_id_list(self, n_song):
		""" This function gets list of song_ids from one page
		@return - list [song_id] """
		song_id_list = list()
		href_pattern = re.compile(r'javascript:melon.link.goSongDetail\(\'(?P<id>\d+)\'\);')
		div_pagelist = self.driver.find_element_by_id("pageList")
		song_list = div_pagelist.find_element_by_tag_name("tbody")\
					.find_elements_by_tag_name("tr")
		if n_song is not None:
			song_list = song_list[:n_song]
		for song in song_list:
			btn_song_info = song.find_element_by_class_name("btn_icon_detail")
			href_str = btn_song_info.get_attribute('href')
			song_id = href_pattern.match(href_str).group("id")
			song_id_list.append(song_id)
		return song_id_list

	def _crawl_song_lyric(self):
		""" This function crawls song name and lyric from the currently open
			song info page
		@return - tuple (song_name, lyric) """
		page_html = self.driver.page_source
		source = BeautifulSoup(page_html, "html.parser")
		div_conts = source.find("div", id="wrap").find("div", id="cont_wrap")\
					.find("div", id="conts")
		div_entry = div_conts.find("div", class_="section_info")\
					.find("div", class_="wrap_info").find("div", class_="entry")
		div_song_name = div_entry.find("div", class_="song_name")
		assert div_song_name.text.strip().split()[0] == "곡명"
		song = " ".join(div_song_name.text.strip().split()[1:])
		div_wrap_lyric = div_conts.find("div", class_="section_lyric")\
						 .find("div", class_="wrap_lyric")
		div_lyric = div_wrap_lyric.find("div", class_="lyric")
		if div_lyric is None: # when no lyric exists
			assert div_wrap_lyric.find("div", class_="lyric_none") is not None
			lyric = ""
		else:
			lyric = div_lyric.text.strip()
		return song, lyric
		
	def get_song_lyric_dict(self, artist_id, n_song=None):
		""" This function crawls and returns song_lyric_dict of all songs of
			artist with input artist_id using Selenium and BeautifulSoup
		@param n_song - number of songs to crawl (crawl all if None)
		@return - dict {song_name: lyric}
		"""
		self._setup(artist_id)
		song_id_list = list()
		song_lyric_dict = dict()
		page_end = False
		page_idx = 0
		while not page_end:
			page_list = self.driver.find_element_by_class_name("page_num")\
						.find_elements_by_tag_name("a")
			page_cnt = len(page_list) + 1
			song_id_list += self._get_song_id_list(n_song)
			next_page = page_list[page_idx]
			next_page.click()
			self.wait.until(EC.staleness_of(next_page))
			page_idx += 1
			if page_idx >= page_cnt - 1:
				page_end = True
		song_id_list += self._get_song_id_list(n_song)
		# open page for each song in song_id_list and crawl lyrics
		print("Crawling progress: ", end='')
		for idx, song_id in enumerate(song_id_list):
			url = MELON_URL + "/song/detail.htm?songId={}".format(song_id)
			self.driver.get(url)
			song, lyric = self._crawl_song_lyric()
			song_lyric_dict[song] = lyric
			if idx % 50 == 0 and idx != 0:
				print("{}/{} ".format(idx, len(song_id_list)), end='')
		print()
		return song_lyric_dict

def read_artist_id_csv(csv_file):
	""" This function reads artist_id csv
	@return - dict {artist: artist_id} """
	artist_id_dict = dict()
	with open(csv_file, 'r') as fpin:
		reader = csv.reader(fpin, delimiter=',')
		next(reader)
		for row in reader:
			if len(row) == 2:
				artist_id_dict[row[0]] = row[1]
	return artist_id_dict

def print_profile(pr_stats, n_print):
	pr_stats.sort_stats("tottime")
	pr_stats.print_stats(n_print)
	pr_stats.sort_stats("cumtime")
	pr_stats.print_stats(n_print)
	pr_stats.sort_stats("ncalls")
	pr_stats.print_stats(n_print)

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Crawl lyrics of songs\
				uploaded on Melon (default crawler: Selenium only)")
	parser.add_argument("--bs4", action="store_true",
						help="use crawler that utilizes BeautifulSoup with\
							  Selenium")
	parser.add_argument("--selenium", action="store_true",
						help="use crawler that utilizes Selenium only")
	parser.add_argument("--selenium_dual", action="store_true",
						help="use crawler that utilizes two Selenium windows")
	parser.add_argument("--profile", action="store_true")
	parser.add_argument("--overwrite", action="store_true")
	parser.add_argument("--test", action="store_true")
	args = parser.parse_args()
	pr = cProfile.Profile()

	start_time = time.time()
	driver = webdriver.Chrome(os.path.join(PROJECT_DIR, "chromedriver.exe"))

	if args.bs4:
		crawler = CrawlerBs4(driver)
	elif args.selenium_dual:
		crawler = CrawlerSeleniumDual(driver)
	else: # default is Selenium crawler
		crawler = CrawlerSelenium(driver)

	artist_id_dict = read_artist_id_csv(os.path.join(PROJECT_DIR, "artist_id.csv"))

	if args.profile:
		artist = input("Artist to crawl: ")
		n_print = int(input("Number of stats to print: "))
		artist_id = artist_id_dict[artist]
		pr.enable()
		song_lyric_dict = crawler.get_song_lyric_dict(artist_id, n_song=None)
		pr.disable()
		print("{} lyrics crawled".format(len(song_lyric_dict)))
		#save_cnt = crawler.save_lyrics(artist, song_lyric_dict)
		#print("{} lyrics saved".format(save_cnt))
		pr_stats = pstats.Stats(pr)
		print_profile(pr_stats, n_print)
	elif args.test:
		artist = input("Artist to crawl: ")
		artist_id = artist_id_dict[artist]
		n_song = int(input("Number of songs to be crawled from each page: "))
		aritst_id = artist_id_dict[artist]
		song_lyric_dict = crawler.get_song_lyric_dict(artist_id, n_song=n_song)
		print(song_lyric_dict.keys())
		print("Number of lyrics crawled: ", len(song_lyric_dict))
	else:
		for artist in artist_id_dict:
			print("Crawling {}".format(artist))
			try:
				artist_id = artist_id_dict[artist]
				if not args.overwrite:
					if os.path.isdir(os.path.join(LYRIC_DIR, "artist")):
						continue
				song_lyric_dict = crawler.get_song_lyric_dict(artist_id, n_song=None)
				print(artist, "{} lyrics crawled".format(len(song_lyric_dict)))
				save_cnt = crawler.save_lyrics(artist, song_lyric_dict)
				print(artist, "{} lyrics saved".format(save_cnt))
			except Error as e:
				print(artist, e)


	end_time = time.time()
	elapsed_sec = end_time - start_time
	elapsed_min = (end_time - start_time) / 60
	print("Elapsed time: {:.2f}min ({:.2f}sec)".format(elapsed_min, elapsed_sec))

"""
Easier using selenium because with bs4 i need to explicitly dig into 
parent-child relation

Selenium staleness - wait until loaded
which worder dont know - especially when there are multiple elements of the same class
need to wait until everything is loaded
not simply from top to bottom (waiting until the bottom-most element
did not work)
staleness seems to work (does not work for backspace so needs to find a clever way for that)
cProfile not useful because {method 'recv_into' of '_socket.socket' objects}
second is "time.sleep"
from third meaningless
"""