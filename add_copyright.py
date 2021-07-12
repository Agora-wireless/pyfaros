#!/usr/bin/env python3
#
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#	INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#	PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
#	FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#	OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
# Copyright (c) 2020, 2021 Skylark Wireless.

import argparse
import sys
import traceback
import os

filepath = os.path.dirname(os.path.abspath(__file__))

disclaimer = """\
#
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#	INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#	PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
#	FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#	OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#\
"""
split_disclaimer = [line+"\n" for line in disclaimer.split("\n")]

def read_file(filename):
    with open(filename, "r") as fptr:
        lines = []
        for line in fptr.readlines():
            lines.append(line)
    return lines

# REVISIT: This needs to detect a list and append the current year if the file was modified.
def modify_copyright(_=None):
    return "# Copyright (c) 2020, 2021 Skylark Wireless.\n"

def update_copyright(lines):
    for idx, line in enumerate(lines):
        if "Copyright (c)" in line:
            lines[idx] = modify_copyright(line)
            return True

    # No copyright found.  Append after comments.
    for idx, line in enumerate(lines):
        if line.startswith("#"):
            continue
        lines.insert(idx, modify_copyright())
        return True

    return False

def write_file(filename, lines):
    with open(filename, "w") as fptr:
        for line in lines:
            fptr.write(line)

def find_disclaimer(lines):
    length = len(split_disclaimer)
    for start_idx in range(3):
        if lines[start_idx:start_idx+length] == split_disclaimer:
            return True
    return False

def add_disclaimer(lines):
    if find_disclaimer(lines):
        return False

    insert_idx = 1 if lines and lines[0].startswith("#!") else 0
    lines[insert_idx:insert_idx] = split_disclaimer

    return True

def replace_copyright_for_python(filename):
    lines = read_file(filename)
    rewrite_file = False

    if add_disclaimer(lines):
        rewrite_file = True

    if update_copyright(lines):
        rewrite_file = True

    if rewrite_file:
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
