#-*- coding:utf-8 -*-

import os
import re

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

if __name__ == "__main__":
	print(validate_filename('이유 / 너 하<나>야\?'))