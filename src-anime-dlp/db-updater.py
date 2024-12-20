import os


li = []

for dirpath, dirnames, filenames in os.walk("/mnt/anime-nas/jellyfin"):
    if filenames == []:
        continue
    for i in filenames:
        li.append(i)


with open(os.path.expanduser("~/python/anime-dlp-4/src-anime-dlp/database.txt"), "w") as database:
    for i in li:
        database.write(f"{i}\n")
