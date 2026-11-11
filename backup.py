#!/usr/bin/env python3

"""
"""

from typing import Dict, List

import os
import sys
import argparse
import json
import subprocess
import glob
import uuid
from pathlib import Path
import shutil
import time
import random
from itertools import chain

def prompt_option(question, options: List[str], default = None):
    soptions = map(
        lambda opt: opt.upper() if opt == default else opt,
        options
    )
    question = question + f" [{'/'.join(soptions)}]"

    while True:
        sys.stdout.write(question)
        choice = input().lower()
        if default is not None and choice == "":
            return default
        elif choice in options:
            return choice
        else:
            sys.stdout.write(f"Please respond with one of {','.join(options)}).\n")

class BaseConfig:
    def __init__(self):
        self.raw_json = {}

    @property
    def config_path(self) -> Path:
        raise NotImplementedError

    def load(self):
        if self.config_path.exists():
            with open(self.config_path) as fl:
                self.raw_json.update(json.load(fl))

    def save(self):
        with open(self.config_path, 'w') as fl:
            json.dump(self.raw_json, fl)


class DestinationConfig(BaseConfig):
    def __init__(self, dest) -> None:
        super().__init__()
        self.destination = dest

        self.raw_json = {
            "id": str(uuid.uuid4()),
        }

    @property
    def config_path(self):
        return Path(self.destination, "_backup_dest.json")

    @property
    def index(self):
        return DestinationIndex.ensure(self.id)

    def load(self):
        super().load()

        j = self.raw_json
        self.id = j["id"]
        self.pinned_files = set(j.get("pinned_files", []))

    def save(self):
        j = self.raw_json
        j["id"] = self.id
        j["pinned_files"] = list(self.pinned_files)

        super().save()


class DestinationIndex(BaseConfig):
    def __init__(self, id):
        super().__init__()
        self.id = id
        self.raw_json = {
            "id": id,
            "assigned_files": [],
        }

    @classmethod
    def ensure(cls, id):
        if not id in INDEXES:
            idx = DestinationIndex(id)
            idx.load()
            INDEXES[id] = idx
        return INDEXES[id]

    @property
    def config_path(self) -> Path:
        return self.__class__.index_dir() / (self.id + ".json")

    @classmethod
    def index_dir(cls) -> Path:
        return CONFIG_PATH.parent / (CONFIG_PATH.stem + "_index")

    def load(self):
        super().load()

        j = self.raw_json
        self.last_synced = j.get("last_synced", None)
        self.assigned_files = set(j.get("assigned_files", []))

    def save(self):
        j = self.raw_json
        j["last_synced"] = self.last_synced
        j["assigned_files"] = list(self.assigned_files)

        super().save()


CONFIG = {}
CONFIG_PATH: Path = None
DEST_CONFIG: DestinationConfig = None

INDEXES: Dict[str, DestinationIndex] = {}

def load_all_indexes():
    index_dir = DestinationIndex.index_dir()
    index_dir.mkdir(parents=True, exist_ok=True)
    for idxfp in os.listdir(index_dir):
        idxid = Path(index_dir, idxfp).stem
        INDEXES[idxid] = DestinationIndex(idxid)
        INDEXES[idxid].load()

def file_assigned(path):
    for idx in INDEXES.values():
        if path in idx.assigned_files: return idx
    return None

def sum_size(spath):
    size = 0
    for path, dirs, files in os.walk(spath):
        for f in files:
            fp = os.path.join(path, f)
            size += os.stat(fp).st_size
    return size

def timestamp(path):
    mtime = 0
    for root, dirs, files in os.walk(path):
        rmts = [os.stat(Path(root, x)).st_mtime for x in chain(dirs, files)]
        if rmts: mtime = max(mtime, max(rmts))

    return mtime

def rsync(s: Path, d: Path):
    d.parent.mkdir(parents=True, exist_ok=True)

    cmd = None
    if s.is_dir():
        cmd = [ 'rsync', "-rlptgoD", '--info=progress2', str(s) + "/", str(d) + "/"]
    elif s.is_file():
        cmd = [ 'rsync', "-lptgoD", '--info=progress2', str(s), str(d)]
    else:
        print(f" - {str(s)} is not a file or directory")
        return

    process = subprocess.Popen(cmd)
    process.wait()

def files_equal(a: Path, b: Path, bufsize=8 * 1024**2):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            ca, cb = fa.read(bufsize), fb.read(bufsize)
            if ca != cb: return False
            if not ca: return True

SPOT_CHUNK = 1024**2
SPOT_RANDOM_CHUNKS = 3

def spot_check_equal(a: Path, b: Path, size: int):
    """Compare ~1MB chunks from the start, end, and random offsets of two same-size files."""
    if size <= SPOT_CHUNK * (SPOT_RANDOM_CHUNKS + 2):
        return files_equal(a, b)

    offsets = [0, size - SPOT_CHUNK]
    offsets += [random.randrange(SPOT_CHUNK, size - 2 * SPOT_CHUNK) for _ in range(SPOT_RANDOM_CHUNKS)]
    with open(a, "rb") as fa, open(b, "rb") as fb:
        for off in offsets:
            fa.seek(off)
            fb.seek(off)
            if fa.read(SPOT_CHUNK) != fb.read(SPOT_CHUNK): return False
    return True

SPOT_MATCH = "spot match"

def check_item_files(s: Path, d: Path) -> Dict[Path, str]:
    """
    Compare each file in s against d. Same-size files with differing mtimes are spot-checked.
    Returns {path relative to s: status}.
    """
    pairs = [(s, d)] if s.is_file() else (
        (Path(root, f), Path(d, Path(root, f).relative_to(s)))
        for root, _, files in os.walk(s) for f in files
    )
    results = {}
    for sf, df in pairs:
        rel = sf.relative_to(s) if s.is_dir() else Path()
        if sf.is_symlink() or df.is_symlink(): continue
        if not df.is_file():
            results[rel] = "new"
            continue
        sst, dst = os.stat(sf), os.stat(df)
        if sst.st_size != dst.st_size:
            results[rel] = "size differs"
        elif sst.st_mtime_ns == dst.st_mtime_ns:
            results[rel] = "same"
        else:
            results[rel] = SPOT_MATCH if spot_check_equal(sf, df, sst.st_size) else "DIFFERS"
    return results

def quick_sync(s: Path, d: Path, checks: Dict[Path, str]):
    """Copy mtimes for spot-matched files (so rsync skips them), then rsync the rest."""
    for rel, status in checks.items():
        if status != SPOT_MATCH: continue
        sf, df = s / rel, d / rel
        dst = os.stat(df)
        os.utime(df, ns=(dst.st_atime_ns, os.stat(sf).st_mtime_ns))
    rsync(s, d)

def validate_sources():
    for dglob in CONFIG["sources"]:
        if dglob.startswith(os.path.pathsep): raise ValueError("sources paths must be relative")
        if ".." in dglob: raise ValueError("sources paths may not include ..")

def expand_globs(root):
    for dglob in CONFIG["sources"]:
        for spath in glob.glob(os.path.join(root, dglob)):
            yield spath

def target_items(root):
    for category in expand_globs(root):
        for item in os.listdir(category):
            item_abs = Path(category, item)
            frel = str(item_abs.relative_to(root))
            yield frel

def unassigned_items(root):
    for frel in target_items(root):
        if file_assigned(frel): continue
        yield frel

def reconcile_directory(src_root, dest_root):
    index = DEST_CONFIG.index

    print("Scanning Destination for deleted/not-assigned items")

    # Delete items no longer present in source (after confirmation)
    # Delete items assigned to another dest
    delete_items = []
    unassigned_but_present_items = []
    for frel in target_items(dest_root):
        assn = file_assigned(frel)
        pinned = frel in DEST_CONFIG.pinned_files
        if (assn and assn != index) or not Path(src_root, frel).exists():
            if not pinned:
                delete_items.append(frel)
        elif not assn:
            unassigned_but_present_items.append(frel)

    if len(delete_items) > 0:
        print(f" - {len(delete_items)} items deleted from source or assigned to another destination. Delete? (Yes/No/Pin)")
        for item in delete_items:
            ans = prompt_option(f"   - " + str(item), ["y", "n", "p"], default="n")
            if ans == "y":
                shutil.rmtree(Path(dest_root, item))
                index.assigned_files.remove(item)
            if ans == "p":
                DEST_CONFIG.pinned_files.add(item)
                index.assigned_files.remove(item)

    index.save()
    DEST_CONFIG.save()

    # Add missing items to the index
    if len(unassigned_but_present_items) > 0:
        print(f" - Found {len(unassigned_but_present_items)} unassigned items present in the destination. Creating missing assignments.")
        for item in unassigned_but_present_items:
            index.assigned_files.add(item)

    # Remove index entries for items not presset in dest
    print("Verify index.")
    for frel in list(index.assigned_files):
        if not Path(dest_root, frel).exists():
            print(f" - Not in dest: {frel}")
            index.assigned_files.remove(frel)

    index.save()

    # Rsync outdated items from source to dest
    print("Scanning for assigned items updated in source.")
    sync_started = time.time()
    last_synced = index.last_synced or 0

    outdated_items = []
    for frel in target_items(dest_root):
        spath = Path(src_root, frel)
        if not spath.exists(): continue
        if timestamp(spath) > last_synced:
            outdated_items.append(frel)

    skipped = 0
    if outdated_items:
        mode = prompt_option(
            f" - {len(outdated_items)} items updated in source. Sync (a)ll, (n)one, or decide (e)ach?",
            ["a", "n", "e"], default="e",
        )

        for frel in outdated_items:
            spath = Path(src_root, frel)
            dpath = Path(dest_root, frel)

            if mode == "n":
                skipped += 1
                continue

            print(f" - {frel}")
            checks = check_item_files(spath, dpath)

            if mode == "e":
                print_changed_files(spath, dpath, last_synced, checks)
                ans = prompt_option("   Full sync (a), Quick sync (q/y), or Skip (n)?", ["a", "q", "y", "n"], default="q")
                if ans == "n":
                    skipped += 1
                    continue
                if ans == "a":
                    rsync(spath, dpath)
                    continue

            quick_sync(spath, dpath, checks)

    if skipped:
        print(f" - {skipped} updated items skipped; last-synced time not advanced so they will be offered again.")
    else:
        index.last_synced = sync_started
    index.save()


def format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}B"
        size /= 1024

def format_stat(path: Path):
    if not path.exists():
        return "missing"
    st = os.stat(path)
    date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
    size = "dir" if path.is_dir() else format_size(st.st_size)
    return f"{date}  {size:>9}"

def changed_paths(spath: Path, since):
    if spath.is_file():
        if os.stat(spath).st_mtime > since:
            yield Path()
        return

    if os.stat(spath).st_mtime > since:
        yield Path()
    for root, dirs, files in os.walk(spath):
        for name in chain(dirs, files):
            p = Path(root, name)
            if os.stat(p).st_mtime > since:
                yield p.relative_to(spath)

def print_changed_files(spath: Path, dpath: Path, since, checks: Dict[Path, str]):
    rows = []
    for rel in sorted(changed_paths(spath, since)):
        s = spath / rel
        d = dpath / rel
        label = str(rel) if str(rel) != "." else "(item root)"
        if s.is_dir(): label += "/"
        rows.append((label, format_stat(s), format_stat(d), checks.get(rel, "")))

    if not rows:
        print("     (no changed files found)")
        return

    width = max(len(r[0]) for r in rows)
    print(f"     {'path':<{width}}  {'src':<30}  {'dest':<30}  check")
    for label, sstat, dstat, check in rows:
        print(f"     {label:<{width}}  {sstat:<30}  {dstat:<30}  {check}")


MIN_FREE_GB = 30
MIN_FREE_SPACE = MIN_FREE_GB * 1024**3

def backup_new_items(src_root, dest_root):
    print("Backing-up unassigned files")

    usage = shutil.disk_usage(dest_root)
    free_space = usage.free
    if free_space < MIN_FREE_SPACE:
        print(f" - Destination is considered full - less than {MIN_FREE_GB}GB available")
        return

    index = DEST_CONFIG.index

    for frel in unassigned_items(src_root):
        print(f" - Assigning and copying {frel}")

        dpath = Path(dest_root, frel)
        spath = Path(src_root, frel)

        item_size = sum_size(spath)
        free_space = free_space - item_size
        if free_space < MIN_FREE_SPACE:
            print(f"   - Not enough space to assign this item")
            return

        rsync(spath, dpath)
        index.assigned_files.add(frel)
        index.save()


def search_outdated_destinations(src_root):
    unsynced_indices = set()
    index_changes = {}

    unsynced_additions = []
    unsynced_modifications = []
    unsynced_deletions = []

    def changes_for(idx):
        if idx not in index_changes:
            index_changes[idx] = {
                "modifications": [],
                "deletions": [],
            }
        return index_changes[idx]

    for frel in target_items(src_root):
        index = file_assigned(frel)
        if not index:
            unsynced_additions.append(frel)
        elif index.last_synced < timestamp(frel):
            unsynced_modifications.append(frel)
            unsynced_indices.add(index)
            changes_for(index)["modifications"].append(frel)

    for idx in INDEXES.values():
        for ifrel in idx.assigned_files:
            spath = Path(src_root, ifrel)
            if not spath.exists():
                unsynced_deletions.append(ifrel)
                unsynced_indices.add(idx)
                changes_for(idx)["deletions"].append(ifrel)

    if not (unsynced_indices or unsynced_additions or unsynced_modifications or unsynced_deletions):
        print("All items backed up!")
    else:
        if unsynced_additions:
            print(f"{len(unsynced_additions)} items unassigned")
        if unsynced_modifications:
            print(f"{len(unsynced_modifications)} items updated since last backup")
        if unsynced_deletions:
            print(f"{len(unsynced_deletions)} items deleted locally but still present on backup")

        print("Outdated destinations:")
        for idx in unsynced_indices:
            print(f" - {idx.id}")

        print(f"")

        ans = prompt_option("Print verbose information?", ["y", "n", "w"], default="n")
        if ans == "n": return

        print(f"")

        def output(ln):
            print(ln)
            pass

        output(f"{len(unsynced_additions)} items unassigned:")
        for itm in unsynced_additions: output(f" - {itm}")
        output(f"")

        output(f"{len(unsynced_modifications)} items modified:")
        for idx, data in index_changes.items():
            items = data["modifications"]
            if not items: continue
            output(f" - {idx.id}")
            for itm in items: output(f"   - {itm}")
        output(f"")

        output(f"{len(unsynced_deletions)} items deleted:")
        for idx, data in index_changes.items():
            items = data["deletions"]
            if not items: continue
            output(f" - {idx.id}")
            for itm in items: output(f"   - {itm}")
        output(f"")


def main(arguments):
    global CONFIG, CONFIG_PATH, DEST_CONFIG

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    main_group = parser.add_mutually_exclusive_group()
    main_group.add_argument('--outdated', help="List Outdated Destinations", action="store_true")
    main_group.add_argument('--print-roots', help="Print root directories", action="store_true")
    main_group.add_argument('--dest', help="Destination")

    parser.add_argument('src', help="Source", default=".")
    parser.add_argument('--config', help="Config File")

    args = parser.parse_args(arguments)

    if not args.config:
        args.config = os.path.join(args.src, "backup_config.json")

    CONFIG_PATH = Path(args.config)
    CONFIG = json.load(open(CONFIG_PATH))

    validate_sources()

    load_all_indexes()

    if args.outdated:
        search_outdated_destinations(args.src)
    elif args.dest:
        DEST_CONFIG = DestinationConfig(args.dest)
        DEST_CONFIG.load()

        reconcile_directory(args.src, args.dest)
        backup_new_items(args.src, args.dest)

        DEST_CONFIG.save()
        DEST_CONFIG.index.save()
    elif args.print_roots:
        for category in expand_globs(args.src):
            print(category)
    else:
        parser.print_help()

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
