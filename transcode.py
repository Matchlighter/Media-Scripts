#!/usr/bin/env python3

"""
A simple python script template.
"""

import os
import glob
import re
import sys
import argparse
import csv
import subprocess
from termcolor import colored, cprint

GB = 1_000_000_000

def determine_profile(vid):
    if "4K" in vid: return "Custom 4K"
    if "BluRay" in vid: return "Custom BluRay"
    if "DVD" in vid: return "Custom DVD"

    size = os.stat(vid).st_size
    if size > 40*GB: return "Custom 4K"
    if size > 10*GB: return "Custom BluRay"

    return "Custom DVD"

def translate_path(path):
    return f'$(./wsl_to_win.sh "{path}")'

def remove_empty_folders(root):
    folders = list(os.walk(root))[1:]

    for folder in folders:
        # folder example: ('FOLDER/3', [], ['file'])
        if not folder[2] and not folder[1]:
            os.rmdir(folder[0])

dest_base_path = None

def transcode_folder(path, orig_dest="2-Completed Originals", dest=".", quality=None):
    for fldr in glob.glob(path):
        for root, dirs, files in sorted(list(os.walk(fldr))):
            for file in files:
                if not re.match(r".*\.(mkv)$", file): continue

                fquality = quality or determine_profile(os.path.join(root, file))

                transcoded_dest = os.path.join(dest_base_path, dest, os.path.relpath(root, fldr), file)
                os.makedirs(os.path.dirname(transcoded_dest), exist_ok=True)

                print(f"==== Transcoding {colored(os.path.basename(file), 'cyan')} as {colored(fquality, 'cyan')} ====")
                print(f"Source: {colored(os.path.join(root, file), 'cyan')}")
                print(f"Destination: {colored(transcoded_dest, 'cyan')}")

                src_path = os.path.abspath(os.path.join(root, file))
                log_path = f"./transcode_logs/{os.path.basename(src_path)}.log"
                original_dest_dir = orig_dest

                hbcmd = f'./HandBrakeCLI.exe --preset-import-file "./hbpresets.json" -i "{translate_path(src_path)}" -o "{translate_path(transcoded_dest)}" -Z "{fquality}" 2> "{log_path}"' #  > {translate_path(log_path)}
                print(f"Invoking Handbrake: {colored(hbcmd, 'cyan')}")

                process = subprocess.Popen(hbcmd, shell=True)
                process.wait()
                if process.returncode != 0:
                    original_dest_dir = "/mnt/i/1-Failed Transcodes"

                orig_path = os.path.join(original_dest_dir, dest, os.path.relpath(root, fldr), file)
                print(f"Moving original to {colored(orig_path, 'cyan')}")
                os.makedirs(os.path.dirname(orig_path), exist_ok=True)
                os.rename(src_path, orig_path)

                if original_dest_dir == orig_dest:
                    cprint("Complete!", "green")
                else:
                    cprint("Failed!", "red")

                print("")

        remove_empty_folders(fldr)

def main(arguments):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-s", "--source", dest="source", default="./")
    parser.add_argument("-d", "--dest", dest="target", default="./2-Transcoded")

    args = parser.parse_args(arguments)

    global dest_base_path
    dest_base_path = args.target

    odest = os.path.join(args.source, "2-Completed Originals")

    # transcode_folder(os.path.join(args.source, "./arm/completed/movies/0 - *"), orig_dest=odest)
    # transcode_folder(os.path.join(args.source, "./arm/completed/movies/"), orig_dest=odest)
    # transcode_folder(os.path.join(args.source, "./1-Pending Transcode"), orig_dest=odest)
    # transcode_folder(os.path.join(args.source, "./arm/completed/tv/"), dest="tv", orig_dest=odest)

    # transcode_folder(os.path.join(args.source, "./ToTranscode/Pending Movies*"), orig_dest=odest)
    # transcode_folder(os.path.join(args.source, "./ToTranscode/Pending TV/"), dest="tv", orig_dest=odest)

    transcode_folder(os.path.join(args.source, "./Recode - */"), orig_dest=odest)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))