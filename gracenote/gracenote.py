#!/usr/bin/env python3
"""
XMLTV Converter - Converts Gracenote TV listings to XMLTV format
"""

import json
import sys
import argparse
from datetime import datetime, timedelta
import requests
from time import time
import xml.etree.ElementTree as ET
from xml.dom import minidom

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Convert Gracenote TV listings to XMLTV format')
    parser.add_argument('-i', '--input', required=True, help='Input JSON channels file')
    parser.add_argument('-o', '--output', required=True, help='Output XMLTV file')
    parser.add_argument('-d', '--days', type=int, default=3, help='Number of days to fetch (default: 3)')
    return parser.parse_args()

def load_channels(input_file):
    """Load channels from JSON file"""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading channels file: {e}")
        sys.exit(1)

def unix_to_datetime(unix_timestamp):
    """Convert Unix timestamp to XMLTV datetime format"""
    return datetime.utcfromtimestamp(unix_timestamp).strftime('%Y%m%d%H%M%S')

def get_current_timestamp():
    """Get current hour timestamp in Unix format"""
    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    return int(hour_start.timestamp())

def fetch_program_data(channel, timestamp, days=3):
    """Fetch program data from Gracenote API"""
    url = "https://tvlistings.gracenote.com/api/sslgrid"
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    # Calculate DST dates for 2025 (you might want to make this dynamic)
    dst_start = "2025-03-09T02:00Z"
    dst_end = "2025-11-02T02:00Z"
    
    payload = {
        "lineupId": channel["lineup_id"],
        "IsSSLinkNavigation": True,
        "timespan": days * 24,  # Convert days to hours
        "timestamp": timestamp,
        "prgsvcid": channel["site_id"],
        "headendId": channel["headend_id"],
        "countryCode": channel["country"],
        "postalCode": channel["postal"],
        "device": channel["device"],
        "userId": "-",
        "aid": "orbebb",
        "DSTUTCOffset": -240,
        "STDUTCOffset": -300,
        "DSTStart": dst_start,
        "DSTEnd": dst_end,
        "languagecode": "en-us"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data for channel {channel['name']}: {e}")
        return None

def create_xmltv_root():
    """Create XMLTV root element"""
    tv = ET.Element("tv")
    tv.set("source-info-name", "Gracenote TV Listings")
    tv.set("source-info-url", "https://tvlistings.gracenote.com")
    tv.set("generator-info-name", "Gracenote TV Converter")
    return tv

def add_channel_element(tv_root, channel):
    """Add channel element to XMLTV"""
    channel_elem = ET.SubElement(tv_root, "channel")
    channel_elem.set("id", channel["xmltv_id"])
    
    display_name = ET.SubElement(channel_elem, "display-name")
    display_name.text = channel["name"]
    
    url = ET.SubElement(channel_elem, "url")
    url.text = "https://tvlistings.gracenote.com"
    
    return channel_elem

def add_programme_element(tv_root, channel_id, program_data, date_key, program_index):
    """Add programme element to XMLTV"""
    try:
        # Extract program data
        start_time = program_data.get("startTime", 0)
        end_time = program_data.get("endTime", 0)
        
        # Skip if missing essential data
        if not start_time or not end_time:
            return
        
        programme = ET.SubElement(tv_root, "programme")
        programme.set("start", f"{unix_to_datetime(start_time)} +0000")
        programme.set("stop", f"{unix_to_datetime(end_time)} +0000")
        programme.set("channel", channel_id)
        
        # Title
        program_info = program_data.get("program", {})
        title = program_info.get("title", "Unknown")
        title_elem = ET.SubElement(programme, "title")
        title_elem.set("lang", "en")
        title_elem.text = title
        
        # Episode title (sub-title)
        episode_title = program_info.get("episodeTitle")
        if episode_title:
            sub_title = ET.SubElement(programme, "sub-title")
            sub_title.set("lang", "en")
            sub_title.text = episode_title
        
        # Description
        short_desc = program_info.get("shortDesc")
        if short_desc:
            desc = ET.SubElement(programme, "desc")
            desc.set("lang", "en")
            desc.text = short_desc
        
        # Season and episode numbers
        season = program_info.get("season")
        episode = program_info.get("episode")
        
        if season is not None and episode is not None:
            # XMLTV NS format (season.episode.part)
            episode_ns = ET.SubElement(programme, "episode-num")
            episode_ns.set("system", "xmltv_ns")
            episode_ns.text = f"{season}.{episode}.0"
            
            # On-screen format
            episode_onscreen = ET.SubElement(programme, "episode-num")
            episode_onscreen.set("system", "onscreen")
            episode_onscreen.text = f"S{season}E{episode}"
        
        # Rating
        rating = program_data.get("rating")
        if rating:
            rating_elem = ET.SubElement(programme, "rating")
            value_elem = ET.SubElement(rating_elem, "value")
            value_elem.text = str(rating)
            
    except Exception as e:
        print(f"Error processing programme data: {e}")

def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element"""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def main():
    """Main function"""
    args = parse_arguments()
    
    print(f"Loading channels from: {args.input}")
    channels = load_channels(args.input)
    
    print(f"Creating XMLTV file for {len(channels)} channels...")
    
    # Create XMLTV root
    tv_root = create_xmltv_root()
    
    # Get current timestamp
    current_timestamp = get_current_timestamp()
    
    # Process each channel
    for channel in channels:
        print(f"Processing channel: {channel['name']}")
        
        # Add channel to XML
        add_channel_element(tv_root, channel)
        
        # Fetch program data
        program_data = fetch_program_data(channel, current_timestamp, args.days)
        
        if program_data and "dates" in program_data:
            # Process program data for each date
            for date_key, programs in program_data["dates"].items():
                if isinstance(programs, list):
                    for i, program in enumerate(programs):
                        add_programme_element(tv_root, channel["xmltv_id"], program, date_key, i)
    
    # Write XML to file
    print(f"Writing XMLTV data to: {args.output}")
    try:
        pretty_xml = prettify_xml(tv_root)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)
        print("XMLTV file created successfully!")
    except Exception as e:
        print(f"Error writing XMLTV file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()