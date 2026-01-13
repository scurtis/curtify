import json
import csv
import os

# Configuration
INPUT_DIR = './data'  # Folder containing your 1,000 JSON slices
PLAYLIST_CSV = 'all_playlists_raw.csv'
LOOKUP_CSV = 'all_track_lookup_all.csv'

def process_all_slices():
    # 1. Prepare to write the CSV files
    with open(PLAYLIST_CSV, 'w', newline='', encoding='utf-8') as f_play, \
         open(LOOKUP_CSV, 'w', newline='', encoding='utf-8') as f_look:
        
        play_writer = csv.writer(f_play)
        look_writer = csv.writer(f_look)
        
        # Write Headers
        play_writer.writerow(['playlist_id', 'track_id'])
        look_writer.writerow(['track_id', 'track_name', 'artist_name'])

        # To avoid duplicate tracks in the lookup table
        seen_track_ids = set()
        file_count = 0

        # 2. Iterate through every file in the directory
        files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
        total_files = len(files)
        
        print(f"Starting processing of {total_files} files...")

        for filename in files:
            file_path = os.path.join(INPUT_DIR, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    
                    for playlist in data.get('playlists', []):
                        p_id = playlist['pid']
                        
                        for track in playlist.get('tracks', []):
                            t_id = track['track_uri']
                            
                            # Write to Playlist CSV (The relationship)
                            play_writer.writerow([p_id, t_id])
                            
                            # Write to Lookup CSV (The metadata) if it's new
                            if t_id not in seen_track_ids:
                                look_writer.writerow([
                                    t_id, 
                                    track['track_name'], 
                                    track['artist_name']
                                ])
                                seen_track_ids.add(t_id)
                
                except Exception as e:
                    print(f"Error processing {filename}: {e}")

            file_count += 1
            if file_count % 50 == 0:
                print(f"Progress: {file_count}/{total_files} files processed...")

    print(f"Done! Created {PLAYLIST_CSV} and {LOOKUP_CSV}")

if __name__ == "__main__":
    process_all_slices()
