#!/usr/bin/env python3
import json
import sys
import os
import argparse
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, List, Optional, Any

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Convert Gracenote TV listings to XMLTV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s channels.json
  %(prog)s channels.json -o output.xml
  %(prog)s --help
        """
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        default='channels.json',
        help='Input JSON file with channel data (default: channels.json)'
    )
    parser.add_argument(
        '-o', '--output',
        default='gracenote.xml',
        help='Output XML file (default: gracenote.xml)'
    )
    return parser.parse_args()

def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def fetch_program_data(channel_data: Dict, date_str: str) -> Optional[Dict]:
    """Fetch program data from Gracenote API for a specific date."""
    timestamp = int(datetime.strptime(f'{date_str} 04:00:00', '%Y-%m-%d %H:%M:%S').timestamp())
    
    payload = {
        "lineupId": channel_data.get("lineup_id"),
        "IsSSLinkNavigation": True,
        "timespan": 336,
        "timestamp": timestamp,
        "prgsvcid": channel_data.get("site_id"),
        "headendId": channel_data.get("headend_id"),
        "countryCode": channel_data.get("country"),
        "postalCode": channel_data.get("postal"),
        "device": channel_data.get("device"),
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
        print(f"Error fetching data for channel {channel_data.get('name')}: {e}")
        return None

def process_channel(channel_data: Dict, dates: List[str]) -> List[Dict]:
    """Process a single channel and return list of programs."""
    all_programs = []
    
    for date_str in dates:
        print(f"Fetching data for {channel_data.get('name')} on {date_str}...")
        
        program_data = fetch_program_data(channel_data, date_str)
        if not program_data:
            continue
            
        # Extract programs for the specific date
        date_programs = program_data.get(date_str, [])
        
        for program in date_programs:
            try:
                # Convert Unix timestamps to XMLTV format
                start_time = datetime.fromtimestamp(program.get("startTime"))
                end_time = datetime.fromtimestamp(program.get("endTime"))
                
                start_str = start_time.strftime("%Y%m%d%H%M%S")
                end_str = end_time.strftime("%Y%m%d%H%M%S")
                
                prog_info = program.get("program", {})
                
                # Extract season/episode information
                season = prog_info.get("season")
                episode = prog_info.get("episode")
                
                program_entry = {
                    "start": start_str,
                    "end": end_str,
                    "channel_id": channel_data.get("xmltv_id") or channel_data.get("site_id"),
                    "title": prog_info.get("title", "Unknown"),
                    "episode_title": prog_info.get("episodeTitle"),
                    "description": prog_info.get("shortDesc"),
                    "season": season if season is not None else None,
                    "episode": episode if episode is not None else None,
                    "rating": program.get("rating"),
                    "language": channel_data.get("language")
                }
                
                all_programs.append(program_entry)
            except Exception as e:
                print(f"Error processing program: {e}")
                continue
    
    return all_programs

def create_xmltv(channels: List[Dict], programs: List[Dict]) -> str:
    """Create XMLTV document from channels and programs."""
    # Create root element
    tv = ET.Element("tv")
    tv.set("source-info-name", "Gracenote TV Listings")
    tv.set("source-info-url", "https://tvlistings.gracenote.com")
    tv.set("generator-info-name", "Gracenote TV Converter")
    
    # Add channel definitions
    for channel in channels:
        channel_id = channel.get("xmltv_id") or channel.get("site_id")
        channel_elem = ET.SubElement(tv, "channel")
        channel_elem.set("id", str(channel_id))
        
        display_name = ET.SubElement(channel_elem, "display-name")
        display_name.text = channel.get("name", "Unknown")
    
    # Add programs
    for program in programs:
        programme = ET.SubElement(tv, "programme")
        programme.set("start", f"{program['start']} +0000")
        programme.set("stop", f"{program['end']} +0000")
        programme.set("channel", str(program['channel_id']))
        
        # Add title
        title = ET.SubElement(programme, "title")
        if program['language']:
            title.set("lang", program['language'])
        title.text = program['title']
        
        # Add sub-title (episode title) if exists
        if program['episode_title']:
            subtitle = ET.SubElement(programme, "sub-title")
            if program['language']:
                subtitle.set("lang", program['language'])
            subtitle.text = program['episode_title']
        
        # Add description if exists
        if program['description']:
            desc = ET.SubElement(programme, "desc")
            if program['language']:
                desc.set("lang", program['language'])
            desc.text = program['description']
        
        # Add episode numbers if available
        if program['season'] is not None and program['episode'] is not None:
            # xmltv_ns format
            ep_ns = ET.SubElement(programme, "episode-num")
            ep_ns.set("system", "xmltv_ns")
            ep_ns.text = f"{program['season']}.{program['episode']}.0"
            
            # onscreen format
            ep_onscreen = ET.SubElement(programme, "episode-num")
            ep_onscreen.set("system", "onscreen")
            ep_onscreen.text = f"S{program['season']}E{program['episode']}"
        
        # Add rating if available
        if program['rating']:
            rating_elem = ET.SubElement(programme, "rating")
            value_elem = ET.SubElement(rating_elem, "value")
            value_elem.text = program['rating']
    
    return prettify_xml(tv)

def main():
    args = parse_arguments()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)
    
    try:
        # Load channel data
        with open(args.input_file, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        
        print(f"Loaded {len(channels_data)} channels from {args.input_file}")
        
        # Generate dates for next 3 days
        today = datetime.now().date()
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
        
        all_programs = []
        
        # Process each channel
        for i, channel in enumerate(channels_data):
            print(f"Processing channel {i+1}/{len(channels_data)}: {channel.get('name', 'Unknown')}")
            channel_programs = process_channel(channel, dates)
            all_programs.extend(channel_programs)
        
        print(f"Total programs fetched: {len(all_programs)}")
        
        # Create XMLTV output
        xml_content = create_xmltv(channels_data, all_programs)
        
        # Write to output file
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        print(f"XMLTV file saved to: {args.output}")
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
