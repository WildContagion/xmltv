#!/usr/bin/env python3
import json
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import requests
import argparse

def main():
    parser = argparse.ArgumentParser(description='Convert Gracenote TV listings to XMLTV format')
    parser.add_argument('input_file', nargs='?', default='./gracenote/channels.json', help='Input JSON channels file (default: ./gracenote/channels.json)')
    parser.add_argument('-o', '--output', default='./gracenote/channels.xml', help='Output XML file (default: ./gracenote/channels.xml)')
    
    args = parser.parse_args()
    
    # Read channels data
    try:
        with open(args.input_file, 'r') as f:
            channels_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in '{args.input_file}'")
        sys.exit(1)
    
    # Create XML structure
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Gracenote TV Listings')
    tv.set('source-info-url', 'https://tvlistings.gracenote.com')
    tv.set('generator-info-name', 'Gracenote TV Converter')
    
    # Process each channel
    for channel_data in channels_data:
        # Extract channel info
        xmltv_id = channel_data.get('xmltv_id')
        device = channel_data.get('device')
        lineup_id = channel_data.get('lineup_id')
        headend_id = channel_data.get('headend_id')
        country = channel_data.get('country')
        postal = channel_data.get('postal')
        site_id = channel_data.get('site_id')
        name = channel_data.get('name')
        
        # Add channel to XML
        channel_elem = ET.SubElement(tv, 'channel')
        channel_elem.set('id', xmltv_id)
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.text = name
        
        # Get program data from Gracenote API
        programs = get_gracenote_programs(
            lineup_id=lineup_id,
            site_id=site_id,
            headend_id=headend_id,
            country=country,
            postal=postal,
            device=device,
            timestamp=channel_data.get('timestamp')
        )
        
        if programs:
            # Process programs for 3 days
            for date_key in list(programs.keys())[:3]:  # Only first 3 days
                date_programs = programs.get(date_key, [])
                for program in date_programs:
                    add_program_to_xml(tv, xmltv_id, program)
    
    # Write XML to file
    write_xml(tv, args.output)
    print(f"XMLTV file saved to: {args.output}")

def get_gracenote_programs(lineup_id, site_id, headend_id, country, postal, device, custom_timestamp=None):
    """Fetch program data from Gracenote API"""
    
    # Calculate timestamp for today at 04:00:00
    if custom_timestamp:
        timestamp = custom_timestamp
    else:
        today_4am = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
        timestamp = int(today_4am.timestamp())
    
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
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            "https://tvlistings.gracenote.com/api/sslgrid",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data from Gracenote API: {e}")
        return None

def add_program_to_xml(tv_element, xmltv_id, program):
    """Add a program to the XML structure"""
    
    # Convert timestamps
    start_time = datetime.fromtimestamp(program.get('startTime', 0))
    end_time = datetime.fromtimestamp(program.get('endTime', 0))
    
    start_time_str = start_time.strftime("%Y%m%d%H%M%S")
    end_time_str = end_time.strftime("%Y%m%d%H%M%S")
    
    # Get program details
    program_data = program.get('program', {})
    rating = program.get('rating')
    title = program_data.get('title', 'Unknown Title')
    short_desc = program_data.get('shortDesc')
    season = program_data.get('season')
    episode = program_data.get('episode')
    episode_title = program_data.get('episodeTitle')
    
    # Create programme element
    programme = ET.SubElement(tv_element, 'programme')
    programme.set('start', f"{start_time_str} +0000")
    programme.set('stop', f"{end_time_str} +0000")
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
        ep_num_ns = ET.SubElement(programme, 'episode-num')
        ep_num_ns.set('system', 'xmltv_ns')
        ep_num_ns.text = f"{season}.{episode}.0"
        
        # On-screen format
        ep_num_onscreen = ET.SubElement(programme, 'episode-num')
        ep_num_onscreen.set('system', 'onscreen')
        ep_num_onscreen.text = f"S{season}E{episode}"
    
    # Add rating if available
    if rating:
        rating_elem = ET.SubElement(programme, 'rating')
        value_elem = ET.SubElement(rating_elem, 'value')
        value_elem.text = str(rating)

def write_xml(element, output_file):
    """Write XML element to file with proper formatting"""
    rough_string = ET.tostring(element, 'utf-8')
    parsed = minidom.parseString(rough_string)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
        f.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">\n')
        f.write(parsed.toprettyxml(indent="  "))

if __name__ == "__main__":
    main()