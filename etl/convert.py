import json, random, glob, os
from tqdm import tqdm

# Find every slice file (recursively)
slice_files = sorted(glob.glob("**/*.json", recursive=True))

if not slice_files:
    print("No JSON files found!")
    exit()

print(f"Found {len(slice_files)} slice files")

# We'll write examples directly to the output file as we go → almost zero RAM
output_file = "spotify_training.jsonl"
examples_count = 0

with open(output_file, "w") as out_f:
    for file_path in slice_files:
        if "mpd.slice" not in file_path.lower():
            continue
        print(f"Processing {file_path} ...")
        try:
            with open(file_path) as f:
                data = json.load(f)
        except Exception as e:
            print(f"  → Could not load {file_path}: {e}")
            continue

        for playlist in tqdm(data["playlists"], desc=os.path.basename(file_path), leave=False):
            tracks = playlist["tracks"]
            if len(tracks) < 8:
                continue

            random.shuffle(tracks)
            split = random.randint(5, min(15, len(tracks)-3))
            seed_tracks  = tracks[:split]
            rec_tracks   = tracks[split:split+random.randint(4, 10)]

            user_msg = "Recommend songs similar to these:\n" + "\n".join(
                f"• {t['artist_name']} – {t['track_name']}" for t in seed_tracks
            )

            assistant_msg = "Here are some great recommendations:\n" + "\n".join(
                f"• {t['artist_name']} – {t['track_name']}" for t in rec_tracks
            )

            example = {
                "messages": [
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_msg}
                ]
            }
            out_f.write(json.dumps(example) + "\n")
            examples_count += 1

print(f"\nAll done! Created {examples_count} training examples → {output_file}")
print("You can now safely fine-tune with this file (it will work even on 8 GB Macs)")
