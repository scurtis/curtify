import json
import csv
import os
import glob

def clean_text(text):
    """
    Standardizes text by removing newlines, carriage returns, 
    and collapsing multiple spaces into one.
    """
    if not text:
        return ""
    # Replace newlines/tabs with spaces, then strip and shrink internal whitespace
    return " ".join(text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').split()).strip()

def parse_spotify_json_to_csv(input_directory, output_filename):
    # These are the columns for our 'Long Format' table
    fieldnames = ['pid', 'track_uri', 'track_name', 'artist_name']
    
    # Initialize the CSV file
    with open(output_filename, mode='w', encoding='utf-8', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        # Find all .json files in the specified folder (e.g., mpd.slice.0-999.json)
        json_files = glob.glob(os.path.join(input_directory, "*.json"))
        print(f"Found {len(json_files)} JSON files to process.")
        
        total_playlists = 0
        total_tracks = 0

        for file_path in json_files:
            print(f"Processing: {os.path.basename(file_path)}...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                for playlist in data.get('playlists', []):
                    pid = playlist['pid']
                    total_playlists += 1
                    
                    for track in playlist.get('tracks', []):
                        # Clean the data immediately to avoid SQL errors later
                        writer.writerow({
                            'pid': pid,
                            'track_uri': track['track_uri'],
                            'track_name': clean_text(track['track_name']),
                            'artist_name': clean_text(track['artist_name'])
                        })
                        total_tracks += 1
                        
    print(f"\nSuccess! Processed {total_playlists} playlists and {total_tracks} track interactions.")
    print(f"Output saved to: {output_filename}")

if __name__ == "__main__":
    # Update these paths to match your local setup
    INPUT_DIR = "./data"  # Folder where your .json slices are kept
    OUTPUT_FILE = "spotify_interactions_long.csv"
    
    parse_spotify_json_to_csv(INPUT_DIR, OUTPUT_FILE)
