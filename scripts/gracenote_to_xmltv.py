#!/usr/bin/env python3
"""
Gracenote TV Listings to XMLTV Converter
Usage: python gracenote_to_xmltv.py [input_file] [-o output_file]
       python gracenote_to_xmltv.py --help
"""

import sys
import os
import json
import argparse
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests
from typing import Dict, List, Optional, Any
import re

def parse_args():
    parser = argparse.ArgumentParser(
        description='Convert Gracenote TV listings to XMLTV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gracenote_to_xmltv.py channels.xml
  python gracenote_to_xmltv.py channels.xml -o output.xml
  python gracenote_to_xmltv.py --help
        """
    )
    parser.add_argument('input', nargs='?', help='Input XML file (channels.xml)')
    parser.add_argument('-o', '--output', help='Output XMLTV file')
    
    # If no arguments, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    return parser.parse_args()

def parse_channels_file(xml_file: str) -> List[Dict]:
    """Parse the channels XML file and extract channel information."""
    channels = []
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Assuming structure: <channels><channel>...</channel></channels>
        for channel_elem in root.findall('.//channel'):
            channel = {
                'name': channel_elem.text.strip() if channel_elem.text else '',
                'lang': channel_elem.get('lang'),
                'xmltv_id': channel_elem.get('xmltv_id'),
                'site_id': channel_elem.get('site_id')
            }
            
            if channel['site_id']:
                parts = channel['site_id'].split('/')
                if len(parts) >= 6:
                    channel['device'] = parts[0]
                    channel['lineup_id'] = parts[1]
                    channel['headend_id'] = parts[2]
                    channel['country'] = parts[3]
                    channel['postal'] = parts[4]
                    channel['prgsvcid'] = parts[5]
            
            channels.append(channel)
    
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)
    
    return channels

def fetch_programs(channel: Dict) -> Optional[Dict]:
    """Fetch program listings from Gracenote API for a channel."""
    timestamp = int(datetime.combine(datetime.now().date(), datetime.min.time().replace(hour=4)).timestamp())
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    payload = {
        "lineupId": channel.get('lineup_id', ''),
        "IsSSLinkNavigation": True,
        "timespan": 336,
        "timestamp": timestamp,
        "prgsvcid": channel.get('prgsvcid', ''),
        "headendId": channel.get('headend_id', ''),
        "countryCode": channel.get('country', ''),
        "postalCode": channel.get('postal', ''),
        "device": channel.get('device', ''),
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
    except requests.exceptions.RequestException as e:
        print(f"Error fetching programs for channel {channel.get('name')}: {e}", file=sys.stderr)
        return None

def parse_programs(program_data: Dict, channel: Dict) -> List[Dict]:
    """Parse program data from Gracenote API response."""
    programs = []
    today = datetime.now().date()
    
    # Process 3 days of programs
    for day_offset in range(3):
        date_key = (today + timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        if program_data and date_key in program_data:
            day_programs = program_data[date_key]
            
            for program in day_programs:
                try:
                    # Parse program information
                    start_time = datetime.fromtimestamp(program.get('startTime', 0))
                    end_time = datetime.fromtimestamp(program.get('endTime', 0))
                    
                    program_info = program.get('program', {})
                    
                    prog = {
                        'start': start_time.strftime('%Y%m%d%H%M%S'),
                        'stop': end_time.strftime('%Y%m%d%H%M%S'),
                        'channel_id': channel.get('xmltv_id') or channel.get('site_id'),
                        'title': program_info.get('title', ''),
                        'short_desc': program_info.get('shortDesc'),
                        'rating': program.get('rating'),
                        'season': program_info.get('season'),
                        'episode': program_info.get('episode'),
                        'episode_title': program_info.get('episodeTitle'),
                        'lang': channel.get('lang')
                    }
                    programs.append(prog)
                except (KeyError, TypeError, ValueError) as e:
                    print(f"Error parsing program: {e}", file=sys.stderr)
                    continue
    
    return programs

def create_xmltv(channels: List[Dict], all_programs: List[List[Dict]]) -> str:
    """Create XMLTV document from channels and programs."""
    # Create root element
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Gracenote TV Listings')
    tv.set('source-info-url', 'https://tvlistings.gracenote.com')
    tv.set('generator-info-name', 'Gracenote TV Converter')
    
    # Add channels
    for channel in channels:
        channel_id = channel.get('xmltv_id') or channel.get('site_id')
        if not channel_id:
            continue
            
        channel_elem = ET.SubElement(tv, 'channel')
        channel_elem.set('id', channel_id)
        
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.text = channel.get('name', '')
    
    # Add programs
    for channel_programs in all_programs:
        for program in channel_programs:
            programme = ET.SubElement(tv, 'programme')
            programme.set('start', f"{program['start']} +0000")
            programme.set('stop', f"{program['stop']} +0000")
            programme.set('channel', program['channel_id'])
            
            # Title
            title = ET.SubElement(programme, 'title')
            if program['lang']:
                title.set('lang', program['lang'])
            title.text = program['title']
            
            # Episode title (sub-title)
            if program.get('episode_title'):
                sub_title = ET.SubElement(programme, 'sub-title')
                if program['lang']:
                    sub_title.set('lang', program['lang'])
                sub_title.text = program['episode_title']
            
            # Description
            if program.get('short_desc'):
                desc = ET.SubElement(programme, 'desc')
                if program['lang']:
                    desc.set('lang', program['lang'])
                desc.text = program['short_desc']
            
            # Episode numbers
            if program.get('season') and program.get('episode'):
                # XMLTV NS format (season.episode.part)
                ep_num_ns = ET.SubElement(programme, 'episode-num')
                ep_num_ns.set('system', 'xmltv_ns')
                ep_num_ns.text = f"{program['season']}.{program['episode']}.0"
                
                # On-screen format
                ep_num_onscreen = ET.SubElement(programme, 'episode-num')
                ep_num_onscreen.set('system', 'onscreen')
                ep_num_onscreen.text = f"S{program['season']}E{program['episode']}"
            
            # Rating
            if program.get('rating'):
                rating_elem = ET.SubElement(programme, 'rating')
                value = ET.SubElement(rating_elem, 'value')
                value.text = program['rating']
    
    # Convert to pretty XML
    xml_string = ET.tostring(tv, encoding='utf-8')
    parsed = minidom.parseString(xml_string)
    pretty_xml = parsed.toprettyxml(indent='  ', encoding='utf-8')
    
    # Add XML declaration
    return pretty_xml

def main():
    args = parse_args()
    
    # Determine input file
    if args.input:
        input_file = args.input
    else:
        # Try default file
        default_file = 'channels.xml'
        if os.path.exists(default_file):
            input_file = default_file
        else:
            print(f"Error: No input file specified and '{default_file}' not found.", file=sys.stderr)
            sys.exit(1)
    
    # Determine output file
    if args.output:
        output_file = args.output
    else:
        output_file = 'output.xml'
    
    print(f"Processing channels from: {input_file}")
    print(f"Output will be saved to: {output_file}")
    
    # Parse channels
    channels = parse_channels_file(input_file)
    print(f"Found {len(channels)} channels")
    
    all_programs = []
    
    # Fetch programs for each channel
    for i, channel in enumerate(channels, 1):
        print(f"Fetching programs for channel {i}/{len(channels)}: {channel.get('name')}")
        
        program_data = fetch_programs(channel)
        if program_data:
            programs = parse_programs(program_data, channel)
            all_programs.append(programs)
            print(f"  Found {len(programs)} programs")
        else:
            print(f"  No programs found or error fetching")
            all_programs.append([])
    
    # Create XMLTV
    print("Creating XMLTV document...")
    xmltv_data = create_xmltv(channels, all_programs)
    
    # Save to file
    try:
        with open(output_file, 'wb') as f:
            f.write(xmltv_data)
        print(f"Successfully saved XMLTV to {output_file}")
    except IOError as e:
        print(f"Error saving file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
