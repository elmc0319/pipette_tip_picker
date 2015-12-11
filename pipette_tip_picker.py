#!/usr/bin/env python2.6

from __future__ import division
import sys
import csv
import operator
import re
import os
import math
from numpy import array
from numpy import array, mean, std
import argparse
import logging
from ConfigParser import SafeConfigParser
from PIL import Image, ImageDraw, ImageFont
from pyPdf import PdfFileWriter, PdfFileReader

def usage():
	print "usage:"
	print ""
	print "  pipette_tip_picker.py <inputfile.txt> <filterfile.txt> <-o [output folder]> <-c [config]> <-d [debug]>"
	print ""
	print "where:"
	print "  [inputfile]      IDT probelist file that has plate and well locations (required)"
	print "  [filterfile]     file with a list of all the loci to be removed from blend (required)"
	print "  [output folder]         folder location to generate the image files"
	print "  [config]         is the configuration file (default pipette_tip_picker.cfg)"
	print "  [debug]          flag to emit debug trace information (default pipette_tip_picker.log)."
	print ""
	exit(1);  


# Creating a routine that appends files to the output file
def append_pdf(input,output):
	    [output.addPage(input.getPage(page_num)) for page_num in range(input.numPages)]


def run(args):
	logger = logging.getLogger("pipette_tip_picker")
	logger.setLevel(logging.DEBUG)

	if args.debug:
		fileLog = logging.FileHandler(args.debug, mode="w")
		logger.addHandler(fileLog)

	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	logger.addHandler(console)

	logger.info("reading configuration file: " + args.config)
	config = SafeConfigParser()
	config.read(args.config)

	num_rows = int(config.get('plate','plate_rows'))
	num_cols = int(config.get('plate','plate_columns'))
	plate_dimensions = [num_rows, num_cols] 

	group = int(config.get('input_file', 'locus_unit'))
	wellcol = int(config.get('input_file', 'well_col_no'))
	probecol = int(config.get('input_file', 'probe_col_no'))
	platecol = int(config.get('input_file', 'plate_col_no'))

	inputfile = args.probefile
	removefile = args.filterfile

	if args.keep:
		keep_color = (255,255,255)
		rem_color = (0,0,0)
	else:
		keep_color = (0,0,0)
		rem_color = (255,255,255)

	dest = inputfile[:-4]+'/'
	if args.output != '':
		dest = args.output+'/'
	if not os.path.isdir(dest):
		os.makedirs(dest)

	pat = '(\w)(\d*)'
	pat2 = '(.*)(LHS|RHS).*'
	pattern = re.compile(pat)
	pattern2 = re.compile(pat2)

	plate_well_name_cord = {}
	with open(inputfile) as inp:
		logger.info("reading input file: "+ inputfile)
		data = csv.reader(inp, delimiter="\t")
		header = next(data, None)
		for line in data:
			if line[platecol] not in plate_well_name_cord:
				plate_well_name_cord[line[platecol]] = {}

			match = pattern.search(line[wellcol])
			row = ord(match.group(1))-ord('A')
			col = int(match.group(2))-1
			plate_well_name_cord[line[platecol]][(row, col)] = line[probecol]

	remove_name = []
	with open(removefile) as inp:
		logger.info("reading filter file: "+ removefile)
		data = csv.reader(inp, delimiter="\t")
		header = next(data, None)
		for line in data:
			remove_name += [line[0]]
	
	plate_res_row = int(config.get('plate_resolution', 'row_pixels'))
	plate_res_col = int(config.get('plate_resolution', 'column_pixels'))
	row_pix = int(plate_res_row*(num_cols+1)/num_cols)
	col_pix = int(plate_res_col*(num_rows+2)/num_rows)

	for plate in plate_well_name_cord:
		rem_loci = 0
		logger.info("creating images for plate "+ plate)
		image = Image.new("RGB", [row_pix, col_pix], "white")
		draw = ImageDraw.Draw(image)

		rbucket = plate_res_row/(num_cols)
		cbucket = plate_res_col/(num_rows)
		
		font = ImageFont.truetype("/usr/share/fonts/liberation/LiberationMono-BoldItalic.ttf", 100)

		#write headers on image
		draw.text((0.25*plate_res_row,cbucket/6), plate, (0,0,0), font=font)

		font = ImageFont.truetype("/usr/share/fonts/liberation/LiberationMono-BoldItalic.ttf", 60)

		for i in range(2,plate_dimensions[0]+2):
			i_ = i-2
			ord_A = ord('A')
			draw.text((1/3*rbucket, cbucket*(i+1/3)), chr(ord_A+i_), (0,0,0), font=font)

		for i in range(1,plate_dimensions[1]+1):
			draw.text((rbucket*(i+1/3), 4/3*cbucket), str(i), (0,0,0), font=font)

		for i in range(0,plate_dimensions[0]):
			for j in range(0,plate_dimensions[1]):
				color = keep_color

				i_ = i+2
				j_ = j+1	

				if (i,j) not in plate_well_name_cord[plate]:
					color = (127,127,127)
				else:
					name = plate_well_name_cord[plate][(i,j)]
					probe = pattern2.search(name).group(1)
					if probe in remove_name:
						color = rem_color
						rem_loci += 1

				draw.ellipse((rbucket*(j_+1/8), cbucket*(i_+1/8), rbucket*(j_+7/8), \
							  cbucket*(i_+7/8)), outline = (0,0,0), fill=color)

		rem_loci = int(rem_loci/group)
		draw.text((0.60*plate_res_row, cbucket/3), "Count of Loci Removed = "+ \
				  str(rem_loci), (0,0,0), font=font)

		image.save(dest+plate+".pdf", "PDF", quality = 100, resolution=500)

	# Writing all the collected pages to a file
	logger.info("creating final pdf")
	output_pdf = PdfFileWriter()
	for plate in sorted(plate_well_name_cord):
		pdf_file = PdfFileReader(file(dest+plate+".pdf","rb"))

		append_pdf(pdf_file,output_pdf)
		os.remove(dest+plate+".pdf")

	output_pdf.write(file(dest+inputfile[:-4]+".pdf","wb"))


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("probefile", nargs='?', type=str, help="add IDT probe order file")
	parser.add_argument("filterfile", nargs='?', type=str, help="add file with names of loci to remove")
	parser.add_argument("-o", "--output", default="", help="output directory(default=<filename>/)")
	parser.add_argument("-c", "--config", dest="config", default="pipette_tip_picker.cfg", \
	nargs="?", help="configuration file for pipette tip picking (default pipette_tip_picker.cfg)")
	parser.add_argument("-k", "--keep", dest="keep", action='store_true', default=False, help="keep the selected loci")
	parser.add_argument("-d", "--debug", dest="debug", const="pipette_tip_picker.log", \
	nargs="?", help="debug to file (default pipette_tip_picker.log)")
	parser.add_argument("-v", "--version", action="version", version="0.1")

	args = parser.parse_args()

	if not args.probefile or not args.filterfile:
		usage()

	run(args)
	
if __name__ == "__main__":
  main()
