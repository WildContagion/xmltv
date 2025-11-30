#!/usr/bin/env python3
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Convert Gracenote TV listings to XMLTV format')
    parser.add_argument('input_file', help='Input channels.json file')
    parser.add_argument('-o', '--output', help='Output XML file (default: channels.xml)', default='./guide/channels.xml')
    args = parser.parse_args()

    # Read and parse JSON data
    try:
        with open(args.input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in '{args.input_file}'")
        sys.exit(1)

    # Extract data from JSON
    xmltv_id = data.get('xmltv_id')
    device = data.get('device')
    lineup_id = data.get('lineup_id')
    headend_id = data.get('headend_id')
    country = data.get('country')
    postal = data.get('postal')
    site_id = data.get('site_id')
    name = data.get('name')

    # Calculate timestamp for today at 04:00:00
    today = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
    timestamp = int(today.timestamp())
    date = today.strftime('%Y-%m-%d')

    # Prepare API request
    url = "https://tvlistings.gracenote.com/api/sslgrid"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    payload = {
        "lineupId": lineup_id,
        "IsSSLinkNavigation": True,
        "timespan": 336,
        "timestamp": timestamp,
        "prgsvcid": site_id,
        "headendId": headend_id,
        "countryCode": country,
        "postalCode": postal,
        "device": device,
        "userId": "-",
        "aid": "orbebb",
        "DSTUTCOffset": -240,
        "STDUTCOffset": -300,
        "DSTStart": "2026-03-08T02:00Z",
        "DSTEnd": "2026-11-01T02:00Z",
        "languagecode": "en-us"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        programs_data = response.json()
    except requests.RequestException as e:
        print(f"Error fetching data from API: {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON response from API")
        sys.exit(1)

    # Create XML structure
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Gracenote TV Listings')
    tv.set('source-info-url', 'https://tvlistings.gracenote.com')
    tv.set('generator-info-name', 'Gracenote TV Converter')

    # Add channel information
    channel = ET.SubElement(tv, 'channel')
    channel.set('id', xmltv_id)
    display_name = ET.SubElement(channel, 'display-name')
    display_name.text = name

    # Process programs for 2 days
    for day_offset in range(2):
        current_date = (today + timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        # Check if the date exists in the response
        if current_date not in programs_data:
            continue
            
        date_programs = programs_data[current_date]
        
        for program in date_programs:
            # Convert timestamps
            start_time = datetime.fromtimestamp(program['startTime'])
            end_time = datetime.fromtimestamp(program['endTime'])
            
            start_time_str = start_time.strftime('%Y%m%d%H%M%S +0000')
            end_time_str = end_time.strftime('%Y%m%d%H%M%S +0000')
            
            # Extract program data with fallbacks
            rating = program.get('rating')
            program_info = program.get('program', {})
            title = program_info.get('title', '')
            short_desc = program_info.get('shortDesc')
            season = program_info.get('season')
            episode = program_info.get('episode')
            episode_title = program_info.get('episodeTitle')
            
            # Create programme element
            programme = ET.SubElement(tv, 'programme')
            programme.set('start', start_time_str)
            programme.set('stop', end_time_str)
            programme.set('channel', xmltv_id)
            
            # Add title
            title_elem = ET.SubElement(programme, 'title')
            title_elem.set('lang', 'en')
            title_elem.text = title
            
            # Add sub-title if available
            if episode_title:
                sub_title = ET.SubElement(programme, 'sub-title')
                sub_title.set('lang', 'en')
                sub_title.text = episode_title
            
            # Add description if available
            if short_desc:
                desc = ET.SubElement(programme, 'desc')
                desc.set('lang', 'en')
                desc.text = short_desc
            
            # Add episode numbers if available
            if season is not None and episode is not None:
                # XMLTV NS format (season.episode.part)
                episode_ns = ET.SubElement(programme, 'episode-num')
                episode_ns.set('system', 'xmltv_ns')
                episode_ns.text = f"{season}.{episode}.0"
                
                # On-screen format
                episode_onscreen = ET.SubElement(programme, 'episode-num')
                episode_onscreen.set('system', 'onscreen')
                episode_onscreen.text = f"S{season}E{episode}"
            
            # Add rating if available
            if rating:
                rating_elem = ET.SubElement(programme, 'rating')
                value_elem = ET.SubElement(rating_elem, 'value')
                value_elem.text = rating

    # Create XML tree and write to file
    tree = ET.ElementTree(tv)
    
    # Add XML declaration and DOCTYPE
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
        f.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">\n')
        tree.write(f, encoding='unicode')

    print(f"XMLTV data saved to {args.output}")

if __name__ == "__main__":
    main()
