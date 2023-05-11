# Copyright (c) 2023 Faraday
# SPDX-License-Identifier: MIT
# Adapted from: https://github.com/infobyte/CVE-2023-21036

import zlib
import sys

if len(sys.argv) != 2:
  print(f"USAGE: {sys.argv[0]} cropped.png/jpg")
  exit()

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

def parse_png_chunk(stream):
  data = stream.read(4)
  size = int.from_bytes(data, "big")
  ctype = stream.read(4)
  data += ctype
  body = stream.read(size)
  data += body
  csum = stream.read(4)
  data += csum
  csum = int.from_bytes(csum, "big")
  assert (zlib.crc32(ctype + body) == csum)
  return ctype, data


def valid_iend(trailer):
  iend_pos = len(trailer) - 8
  iend_size = int.from_bytes(trailer[iend_pos-4:iend_pos], "big")
  iend_csum = int.from_bytes(trailer[iend_pos+4:iend_pos+8], "big")
  return iend_size == 0 and iend_csum == 0xAE426082


def parse_png(f_in):
  magic = f_in.read(len(PNG_MAGIC))
  assert (magic == PNG_MAGIC)

  sanitized = magic

  # find end of cropped PNG
  while True:
    ctype, data = parse_png_chunk(f_in)
    sanitized += data
    if ctype == b"IEND":
      break

  # grab the trailing data
  trailer = f_in.read()

  if trailer and valid_iend(trailer):
    # just overwrite
    fname = sys.argv[1]
    print("Saving sanitized file as {}".format(fname))
    with open(fname, "wb") as f:
      f.write(sanitized)
  else:
    print("{} has no trailing bytes or original IEND chunk!".format(
        sys.argv[1]))
    print("{} is not affected by acropalypse.".format(
      sys.argv[1]
    ))


def parse_jpeg(f_in):
  SOI_marker = f_in.read(2)
  has_SOI_marker = SOI_marker == b"\xFF\xD8"

  if not has_SOI_marker:
    print("Could not process {}. Has no SOI marker!".format(
      sys.argv[1]))
    return
  
  APP0_marker = f_in.read(2)
  has_APP0_marker = APP0_marker == b"\xFF\xE0"

  if not has_APP0_marker:
    print("Could not process {}. Has no APP0 marker!".format(
      sys.argv[1]))
    return

  APP0_size = int.from_bytes(f_in.read(2), "big")
  APP0_body = f_in.read(APP0_size - 2)

  has_APP0_JFIF_body = APP0_body[:4] == b"JFIF"
  if not has_APP0_JFIF_body:
    print("Could not process {}. Has invalid APP0 body".format(
      sys.argv[1]))
    return

  f_in.seek(0, 0)
  file = f_in.read()
  EOI_marker_pos = file.index(b"\xFF\xD9")

  if not EOI_marker_pos:
    print("Could not process {}. Has no EOI marker".format(
      sys.argv[1]))
    return

  sanitized = file[:EOI_marker_pos + 2]
  trailer = file[EOI_marker_pos + 2:]

  if trailer and trailer[-2:] == b"\xFF\xD9":
    # just overwrite
    fname = sys.argv[1]
    print("Saving sanitized file as {}".format(fname))
    with open(fname, "wb") as f:
      f.write(sanitized)
  else:
    print("{} has no trailing bytes or original EOI marker!".format(
      sys.argv[1]))
    print("{} is not affected by acropalypse.".format(
      sys.argv[1]))


f_in = open(sys.argv[1], "rb")
start = f_in.read(2)
f_in.seek(0, 0)

if start == b"\x89P":
  parse_png(f_in)
elif start == b"\xFF\xD8":
  parse_jpeg(f_in)
else:
  print("File doesn't appear to be jpeg or png.")
