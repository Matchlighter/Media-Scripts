
# Media Scripts

This is a collection of scripts that I use to help me manage my media collection.


## `renamer.py`

Walks a directory tree and produces a CSV of all files. The CSV can be saved or automatically opened in VS Code (VS Code supports column and multi-cursor editing). The second column of the CSV can be used to bulk-rename files.
If using VS Code, this script will apply all of the modified file names when the file is closed.

Second column can instead be set to `DEL` to delete the file instead of renaming it.

### Examples

#### Open in VS Code and rename upon closing
```sh
./renamer.py /some/base/path --code
```

#### Save to CSV file
```sh
./renamer.py /some/base/path --file=./renamings.csv
```

#### Read and Rename from previously saved file
```sh
./renamer.py /some/base/path --from-file --file=./renamings.csv
```


## `backup.py`

I keep all my media on a (presently) 24TB-usable Unraid NAS. I backup my important/irreplaceable stuff to Backblaze B2. But that would get very expensive if I were to use that to backup all of my (replaceable) media as well. I didn't want to purchase and maintain a second, off-site NAS either. But, I _do_ have a quantity of used hard drives that I've decommissioned. They have high hours so I wouldn't trust them as primary storage, or even in a backup NAS. But they'd be great for periodic, cold backups of replaceable data.

However, they are relatively small and wouldn't fit my whole collection on a single drive, and I don't want to attach and mount all of them at once.

This script allows me to backup to those drives while only attaching one at a time and keeping the others cold. When I want to backup my media, I attach a drive and run the script. The script gives the drive a unique identifier and then begins backing up my media. When the drive reaches a high water mark, the script ends and indicates to replace the drive. I swap the drive for an empty one, rerun the script, and it picks up where it left off. Repeat until all media is backed-up.

The script keeps a local index of which items it has backed up to which drives. This both allows it to know what's already been backed up w/o keeping all backup drives online, and also allows the script to know which files have been modified since the last run. Running the script with the `--outdated` flag will list the files changed since the last backup, and indicate which backup drive each file resides on.

The script assigns _items_ to each drive, not individual files. An "item" is intended to be a movie (with all versions and extras) or a whole TV series. The script assumes a standard Plex layout - `movies/single_movie_folder/movie_file.mkv` for movies or `tv/series_name/season_x/episode_y.mkv` for TV.

The script is configured with a `backup_config.json` file that looks like such:
```json
{
    "sources": [
        "./movies/",
        "./tv/",
        "./additional_libraries/*/*/"
    ]
}
```
In this case, "items" will be each folder in `./movies/`, each folder in `./tv/`, and each folder in (eg) `./additional_libraries/dvd/movies/`.

You could change the `./tv/` entry to `./tv/*/`, in which case each season becomes an item instead of each series.

Note that `sources` must:
- Be paths relative to the source passed to the script - absolute paths may not be used
- Be paths within the source - paths with `../` may not be used

File structure is maintained relative to the passed source root - ie `<source_root>/movies/some_movie/movie.mkv` is backed-up to `<dest>/movies/some_movie/movie.mkv` - regardless of `sources` conguration in the config.

### Command Parameters
```
./backup.py <source_root> [--dest <dest>] [--config <config_file>] [--outdated]
```

### Example Usage

#### Start backing up to the given destination
NB: The `--config` parameter is optional. It's default value (relative to the given source root) is shown.
```sh
./backup.py /your_root_media_folder --dest /mnt/backup_drive --config ./backup_config.json
# OR
./backup.py /your_root_media_folder --dest /mnt/backup_drive
```

#### List outdated files
```sh
./backup.py /your_root_media_folder --outdated
```


## `transcode.py` (deprecated)

I used this to bulk transcode a whole folder (and sub-folders) of files. It is somewhat specific to how I used to process things and was intended to run in WSL. I don't use this anymore, but have included it for reference and/or future use.
