#!/usr/bin/env python3
import argparse
import sys
import traceback
import os

filepath = os.path.dirname(os.path.abspath(__file__))

def read_file(filename):
    with open(filename, "r") as fptr:
        lines = []
        for line in fptr.readlines():
            lines.append(line)
    return lines

def update_copyright(lines):
    for line in lines:
        if "copyright" in line.lower():
            return False

    # No copyright found.  Append after comments.
    for idx, line in enumerate(lines):
        if line.startswith("#"):
            continue
        lines.insert(idx, "# Copyright (c) 2020 Skylark Wireless. All Rights Reserved.\n")
        return True

    return False

def write_file(filename, lines):
    with open(filename, "w") as fptr:
        for line in lines:
            fptr.write(line)

def replace_copyright_for_python(filename):
    lines = read_file(filename)
    if update_copyright(lines):
        write_file(filename, lines)


def run(dirs : list) -> None:
    if dirs == []:
        dirs = [os.path.curdir]
    for dirname in dirs:
        for root, _, files in os.walk(dirname):
            for name in files:
                if name.endswith(".py"):
                    replace_copyright_for_python(os.path.join(root, name))


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdb',    help="Enter debugger on failure", action="store_true")
    parser.add_argument('dirname', help="List of directories", action="store", nargs="*")
    args = parser.parse_args(argv)

    try:
        run(list(iter(args.dirname)))
    except Exception as e:
        if args.pdb:
            traceback.print_exc()
            import pdb
            pdb.post_mortem()
        raise e

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
