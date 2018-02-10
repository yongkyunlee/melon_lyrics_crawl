#-*- coding:utf-8 -*-

import os
import re
import csv

FILE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_DIR = FILE_DIR
LYRIC_DIR = os.path.join(PROJECT_DIR, "lyrics")

def validate_filename(filename):
	""" This function changes the filename so that the filename
		is not illegal and does not mess up with the directory """
	# replace space with _
	filename = filename.replace(' ', '_')
	# \ / : ? * " < > | are not allowed as file/dir name
	special_ch = re.compile(r'[\\\?\/\:\*\"\|<>]')
	# replace special ch with `
	filename = re.sub(special_ch, '`', filename) + ".txt"
	return filename

def print_profile(pr_stats, n_print):
	pr_stats.sort_stats("tottime")
	pr_stats.print_stats(n_print)
	# pr_stats.sort_stats("cumtime")
	# pr_stats.print_stats(n_print)
	# pr_stats.sort_stats("ncalls")
	# pr_stats.print_stats(n_print)

def read_artist_id_csv(csv_file, ignore_y):
	""" This function reads artist_id csv
	@param ignore_y - skip artist with "y" for the "crawled" column in True
					  save every artist ignoring "y" if False
	@return - dict {artist: artist_id} """
	artist_id_dict = dict()
	with open(csv_file, 'r') as fpin:
		reader = csv.reader(fpin, delimiter=',')
		next(reader)
		for row in reader:
			if len(row) > 0:
				if ignore_y or row[2] != "Y":
					artist_id_dict[row[0]] = row[1]
	return artist_id_dict

def read_artist_id_csv_list(file_list, ignore_y):
	""" This function reads the list of artist_id_csv_list """
	artist_id_dict = dict()
	for csv_file in file_list:
		artist_id_dict.update(read_artist_id_csv(file, ignore_y))

def update_artist_id_csv(csv_file, artist):
	""" This function updates artist_id_csv file by appending 'Y' at the
		end of the of the given artist """
	with open(csv_file, 'r') as fpin:
		lines = fpin.read().split("\n")
		lines = list(map(lambda x: x.split(','), lines))
	with open(csv_file, 'w', newline='') as fpout:
		wr = csv.writer(fpout, delimiter=',')
		for line in lines:
			if line[0] == artist:
				line[2] = "Y"
			wr.writerow(line)

def csv_alphabetical_order(csv_file):
	with open(csv_file, 'r') as fpin:
		lines = fpin.read().split("\n")
		lines = list(map(lambda x: x.split(','), lines))
	with open(csv_file, 'w', newline='') as fpout:
		wr = csv.writer(fpout, delimiter=',')
		header = lines.pop(0)
		print(header)
		print(lines)
		wr.writerow(header)
		lines = sorted(lines, key=lambda x: x[0])
		for line in lines:
			wr.writerow(line)

if __name__ == "__main__":
	csv_alphabetical_order(os.path.join(PROJECT_DIR, "artist_id.csv"))