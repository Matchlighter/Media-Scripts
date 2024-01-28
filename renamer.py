#!/usr/bin/env python3

"""
A simple python script template.
"""

import os
import sys
import argparse
import csv
import subprocess

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def remove_empty_folders(root):
    folders = list(os.walk(root))[1:]

    for folder in folders:
        if not folder[2] and not folder[1]:
            os.rmdir(folder[0])


def generate_csv(tdir, csv_file):
    with open(csv_file, 'w') as f:
        writer = csv.writer(f)
        for root, dirs, files in os.walk(tdir):
            dirs.sort()
            files.sort()
            for f in files:
                p = os.path.join(os.path.relpath(root, tdir), f)
                size = os.stat(os.path.join(root, f)).st_size
                writer.writerow([p, p, sizeof_fmt(size)])

def rename_from_csv(tdir, csv_file):
    with open(csv_file,'r') as csvfile:
        reader = csv.reader(csvfile, delimiter = ',')

        for row in reader:
            if len(row) == 0: continue
            if row[0] == row[1]: continue

            if row[1] == "DEL":
                try:
                    os.remove(os.path.join(tdir, row[0]))
                except Exception as err:
                    print(f'File {row[0]} could not be removed: {err}!')
                continue

            try:
                target = os.path.join(tdir, row[1])
                os.makedirs(os.path.dirname(target), exist_ok=True)
                os.rename(os.path.join(tdir, row[0]), target)
            except Exception as err:
                print(f'File {row[0]} could not be renamed to {row[1]}: {err}!')

def prompt(tdir, csv_file):
    generate_csv(tdir, csv_file)
    process = subprocess.Popen(f"code --wait {csv_file}", shell=True, stdout=subprocess.PIPE)
    process.wait()
    if process.returncode != 0: return
    rename_from_csv(tdir, csv_file)
    os.remove(csv_file)
    remove_empty_folders(tdir)

def main(arguments):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('folder', help="Input Folder", default=".")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--from-file', help="Use the passed --file as input", action="store_true")
    group.add_argument("--code", action="store_true")

    parser.add_argument('--file', help="Output CSV", default="./renamings.csv")

    args = parser.parse_args(arguments)

    if args.code:
        prompt(args.folder, args.file)
    elif args.from_file:
        rename_from_csv(args.folder, args.file)
    else:
        generate_csv(args.folder, args.file)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))