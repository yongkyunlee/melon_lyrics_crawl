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
import math
import random
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
DRIVER_WAIT = 10

class CrawlerBase():
	""" This class is a group of functions used by both Selenium crawler and
		bs4 crawler """
	def __init__(self, driver):
		self.driver = driver
		self.wait = WebDriverWait(self.driver, DRIVER_WAIT)

	def _setup(self, artist_id):
		""" This function opens the initial aritst url """
		artist_url = MELON_URL + "/artist/song.htm?artistId={}".format(artist_id)
		self.artist = artist
		self.driver.get(artist_url)

	def save_lyric(self, artist, song, lyric):
		artist_lyric_dir = os.path.join(LYRIC_DIR, artist)
		if not os.path.isdir(artist_lyric_dir):
			os.makedirs(artist_lyric_dir)
		if lyric != "":
			song = utils.validate_filename(song)
			with open(os.path.join(artist_lyric_dir, song), 'wb') as fpout:
				fpout.write(lyric.encode('utf8'))

	@staticmethod
	def save_lyrics_dict(artist, song_lyric_dict):
		""" This function saves lyrics to txt file after reading input dict
		@param song_lyric_dict - {song: lyric}
		"""
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

class Crawler(CrawlerBase):
	""" This class is the actual crawler used for lyric crawling
	@param option - selenium_raw, selenium, bs4
	"""
	def __init__(self, driver, option):
		super(Crawler, self).__init__(driver)
		if option not in ("selenium_raw", "selenium", "bs4"):
			raise ValueError("Wrong crawler option")
		self.option = option

	def _get_song_id_list(self, n_song):
		""" This function gets list of song_ids from one page
		@return - list [song_id]
		"""
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

	def _crawl_song_lyric_bs4(self):
		""" This function crawls song name and lyric from the currently open
			song info page
		@return - tuple (song_name, lyric)
		"""
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

	def _crawl_song_lyric_selenium(self):
		""" This function crawls song name and lyric from the currently open
			song info page
		@return - tuple (song_name, lyric)
		"""
		self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "song_name")))
		self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "wrap_lyric")))
		song = self.driver.find_element_by_class_name("song_name").text.strip()
		div_wrap_lyric = self.driver.find_element_by_class_name("wrap_lyric")
		try:
			div_lyric = div_wrap_lyric.find_element_by_class_name("lyric")
			lyric = div_lyric.text.strip()
		except NoSuchElementException:
			assert div_wrap_lyric.find_element_by_class_name("lyric_none") is not None
			lyric = ""
		return song, lyric

	def _crawl_songlist_lyrics(self, n_song, save=True):
		""" This function crawls song name and lyric from all the songs retrived
			by pageObj by calling opening each song_info page in the song list
			using Selenium
		@return - dict {song_name: lyric}
		"""
		song_lyric_dict = dict()
		song_idx =  0
		song_end = False
		while not song_end:
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
			if song in song_lyric_dict:
				song += "_dup"
			if save:
				self.save_lyric(self.artist, song, lyric)
			song_lyric_dict[song] = lyric
			# return to previous page and wait until id "btn_icon_detail" and
			# class "page_num" are avaiable
			# Question: there are multiple elements of same class - how can we
			# be sure if all of such elements have been loaded
			self.driver.back()
			self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "btn_icon_detail")))
			self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page_num")))
			song_idx += 1
			if n_song is not None:
				song_cnt = n_song
			if song_idx >= song_cnt:
				song_end = True
		return song_lyric_dict

	def get_song_lyric_dict(self, artist_id, n_song=None, time_sleep=True,
							save=True):
		""" This function crawls and returns song_lyric_dict of all songs of
			artist with input artist_id
		@param n_song - number of songs to crawl (crawl all if None)
		@param time_sleep - boolean for manual time sleep
		@param save - boolean for saving the lyrics
		@return - dict {song_name: lyric}
		"""
		self._setup(artist_id)
		song_id_list = list()
		song_lyric_dict = dict()
		page_end = False
		single_page = False
		page_idx = 0
		while not page_end:
			if self.option == "selenium_raw":
				songlist_lyric_dict = self._crawl_songlist_lyrics(n_song,
										save=save)
				for song in songlist_lyric_dict:
					if song in song_lyric_dict:
						song += "_dup"
					song_lyric_dict[song] = songlist_lyric_dict[song]
			else:
				song_id_list += self._get_song_id_list(n_song)
			page_list = self.driver.find_element_by_class_name("page_num")\
						.find_elements_by_tag_name("a")
			if len(page_list) == 0:
				single_page = True
				break
			next_page = page_list[page_idx]
			next_page.click()
			self.wait.until(EC.staleness_of(next_page))
			page_idx += 1
			if page_idx >= len(page_list) - 1:
				page_end = True
			if time_sleep:
				time.sleep(random.uniform(0., 1.))
		if self.option == "selenium_raw":
			if not single_page:
				song_lyric_dict.update(self._crawl_songlist_lyrics(n_song))
		else:
			if not single_page:
				song_id_list += self._get_song_id_list(n_song)
		# open and use a new window for retrieving song info page
		if self.option == "bs4" or self.option == "selenium":
			print("Crawling progress: ", end='')
			for idx, song_id in enumerate(song_id_list):
				url = MELON_URL + "/song/detail.htm?songId={}".format(song_id)
				self.driver.get(url)
				# choose what tool to use for crawling
				if self.option == "bs4":
					song, lyric = self._crawl_song_lyric_bs4()
				elif self.option == "selenium":
					song, lyric = self._crawl_song_lyric_selenium()
				# if the song name is the same
				if song in song_lyric_dict:
					song += "_dup"
				if save:
					self.save_lyric(self.artist, song, lyric)
				song_lyric_dict[song] = lyric
				# TODO: do not know why print below does not work
				if idx % 50 == 0 and idx != 0:
					print("{}/{} ".format(idx, len(song_id_list)), end='')
				if time_sleep:
					time.sleep(random.uniform(0.5, 3.5))
		print()
		return song_lyric_dict

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Crawl lyrics of songs\
				uploaded on Melon")
	parser.add_argument("--bs4", action="store_true",
						help="use crawler that utilizes BeautifulSoup with\
							  Selenium")
	parser.add_argument("--selenium_raw", action="store_true",
						help="use crawler that utilizes Selenium in a raw way\
							  i.e. simple but inefficient way")
	parser.add_argument("--selenium", action="store_true",
						help="use crawler that utilizes Selenium")
	parser.add_argument("--profile", action="store_true")
	parser.add_argument("--test", action="store_true")
	args = parser.parse_args()
	pr = cProfile.Profile()

	start_time = time.time()
	driver = webdriver.Chrome(os.path.join(PROJECT_DIR, "chromedriver.exe"))

	if not args.bs4 and not args.selenium and not args.selenium_raw:
		raise Exception("Crawling tool must be selected (bs4, selenium_raw, selenium)")
	if args.bs4:
		crawler = Crawler(driver, "bs4")
	elif args.selenium:
		crawler = Crawler(driver, "selenium")
	elif args.selenium_raw:
		crawler = Crawler(driver, "selenium_raw")

	artist_id_csv = os.path.join(PROJECT_DIR, "artist_id.csv")
	
	if args.profile:
		artist_id_dict = utils.read_artist_id_csv(artist_id_csv, ignore_y=True)
		artist = input("Artist to crawl: ")
		n_print = int(input("Number of stats to print: "))
		artist_id = artist_id_dict[artist]
		pr.enable()
		song_lyric_dict = crawler.get_song_lyric_dict(artist_id, n_song=None,
							time_sleep=True, save=False)
		pr.disable()
		print("{} lyrics crawled".format(len(song_lyric_dict)))
		#save_cnt = crawler.save_lyrics_dict(artist, song_lyric_dict)
		#print("{} lyrics saved".format(save_cnt))
		pr_stats = pstats.Stats(pr)
		utils.print_profile(pr_stats, n_print)
	elif args.test:
		artist_id_dict = utils.read_artist_id_csv(artist_id_csv, ignore_y=True)
		artist = input("Artist to crawl: ")
		artist_id = artist_id_dict[artist]
		n_song = int(input("Number of songs to be crawled from each page: "))
		aritst_id = artist_id_dict[artist]
		song_lyric_dict = crawler.get_song_lyric_dict(artist_id, n_song=n_song,
							save=True)
		print(song_lyric_dict.keys())
		print("Number of lyrics crawled: ", len(song_lyric_dict))
	else:
		artist_id_dict = utils.read_artist_id_csv(artist_id_csv, ignore_y=False)
		for artist in artist_id_dict:
			print("Crawling {}".format(artist))
			artist_id = artist_id_dict[artist]
			song_lyric_dict = crawler.get_song_lyric_dict(artist_id, n_song=None,
								time_sleep=True, save=True)
			print(artist, "{} lyrics crawled".format(len(song_lyric_dict)))
			#save_cnt = crawler.save_lyrics(artist, song_lyric_dict)
			#print(artist, "{} lyrics saved".format(save_cnt))
			utils.update_artist_id_csv(artist_id_csv, artist)

	driver.quit()
	end_time = time.time()
	elapsed_time = end_time - start_time
	elapsed_min = math.floor(elapsed_time / 60)
	elapsed_sec = 60 * (elapsed_time / 60 - elapsed_min)

	print("Elapsed time: {}min {:.2f}sec".format(elapsed_min, elapsed_sec))
