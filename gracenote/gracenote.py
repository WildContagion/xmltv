#!/usr/bin/env python3
"""
Gracenote TV Listings to XMLTV Converter
Fetches data from Gracenote API and converts to XMLTV format
"""

import json
import requests
import time
import datetime
from datetime import timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sys

def get_timestamp_for_hour(hours_ahead=0):
    """Get Unix timestamp for the start of current hour + specified hours"""
    now = datetime.datetime.now()
    target_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=hours_ahead)
    return int(target_time.timestamp())

def unix_to_datetime(unix_timestamp):
    """Convert Unix timestamp to XMLTV datetime format"""
    return datetime.datetime.fromtimestamp(unix_timestamp).strftime('%Y%m%d%H%M%S')

def fetch_gracenote_data(channel_data, days=3):
    """Fetch program data from Gracenote API for multiple days"""
    all_programs = []
    
    for day_offset in range(days):
        # Calculate timestamp for each day at 00:00
        timestamp = get_timestamp_for_hour(day_offset * 24)
        
        payload = {
            "lineupId": channel_data['lineup_id'],
            "IsSSLinkNavigation": True,
            "timespan": 336,  # 14 days in hours
            "timestamp": timestamp,
            "prgsvcid": channel_data['site_id'],
            "headendId": channel_data['headend_id'],
            "countryCode": channel_data['country'],
            "postalCode": channel_data['postal'],
            "device": channel_data['device'],
            "userId": "-",
            "aid": "orbebb",
            "DSTUTCOffset": -240,
            "STDUTCOffset": -300,
            "DSTStart": "2025-03-09T02:00Z",
            "DSTEnd": "2025-11-02T02:00Z",
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
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract programs for this date
            date_key = (datetime.datetime.now() + timedelta(days=day_offset)).strftime('%Y-%m-%d')
            if date_key in data:
                for program in data[date_key]:
                    program['date_key'] = date_key
                    all_programs.append(program)
                    
            print(f"Fetched data for {date_key}: {len(data.get(date_key, []))} programs")
            time.sleep(1)  # Be nice to the API
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for day {day_offset}: {e}")
            continue
    
    return all_programs

def create_xmltv_output(channel_data, programs):
    """Create XMLTV format from channel data and programs"""
    
    # Create root element
    tv = ET.Element("tv")
    tv.set("source-info-name", "Gracenote TV Listings")
    tv.set("source-info-url", "https://tvlistings.gracenote.com")
    tv.set("generator-info-name", "Gracenote TV Converter")
    
    # Create channel element
    channel = ET.SubElement(tv, "channel")
    channel.set("id", channel_data['xmltv_id'])
    
    display_name = ET.SubElement(channel, "display-name")
    display_name.text = channel_data['name']
    
    url = ET.SubElement(channel, "url")
    url.text = "https://tvlistings.gracenote.com"
    
    # Create programme elements
    for program in programs:
        try:
            programme = ET.SubElement(tv, "programme")
            
            # Start and end times
            start_time = unix_to_datetime(program['startTime'])
            end_time = unix_to_datetime(program['endTime'])
            programme.set("start", f"{start_time} +0000")
            programme.set("stop", f"{end_time} +0000")
            programme.set("channel", channel_data['xmltv_id'])
            
            # Title
            title = ET.SubElement(programme, "title")
            title.set("lang", "en")
            title.text = program.get('program', {}).get('title', 'Unknown Title')
            
            # Episode title (sub-title)
            episode_title = program.get('program', {}).get('episodeTitle')
            if episode_title:
                sub_title = ET.SubElement(programme, "sub-title")
                sub_title.set("lang", "en")
                sub_title.text = episode_title
            
            # Description
            short_desc = program.get('program', {}).get('shortDesc')
            if short_desc:
                desc = ET.SubElement(programme, "desc")
                desc.set("lang", "en")
                desc.text = short_desc
            
            # Season and episode information
            season = program.get('program', {}).get('season')
            episode = program.get('program', {}).get('episode')
            
            if season is not None and episode is not None:
                # XMLTV NS format (season.episode.part)
                episode_num_ns = ET.SubElement(programme, "episode-num")
                episode_num_ns.set("system", "xmltv_ns")
                episode_num_ns.text = f"{season}.{episode}.0"
                
                # On-screen format
                episode_num_onscreen = ET.SubElement(programme, "episode-num")
                episode_num_onscreen.set("system", "onscreen")
                episode_num_onscreen.text = f"S{season}E{episode}"
            
            # Rating
            rating_value = program.get('rating')
            if rating_value:
                rating = ET.SubElement(programme, "rating")
                value = ET.SubElement(rating, "value")
                value.text = rating_value
                
        except Exception as e:
            print(f"Error processing program: {e}")
            continue
    
    return tv

def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element"""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def main():
    # Default file paths
    channels_file = './gracenote/channels.json'
    output_filename = './guide/gracenote.xml'

    # Handle command-line arguments
    if len(sys.argv) > 1:
        channels_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_filename = sys.argv[2]

    # Load channels from JSON file
    try:
        with open(channels_file, 'r') as f:
            channels = json.load(f)
    except FileNotFoundError:
        print(f"Error: channels file not found at {channels_file}")
        return
    except json.JSONDecodeError as e:
        print(f"Error parsing channels file: {e}")
        return

    print(f"Loaded {len(channels)} channels")

    all_xmltv_data = []

    for channel in channels:
        print(f"\nProcessing channel: {channel.get('name', 'Unknown')}")

        # Fetch program data for 3 days
        programs = fetch_gracenote_data(channel, days=3)
        print(f"Retrieved {len(programs)} programs for {channel['name']}")

        # Create XMLTV structure
        xmltv_root = create_xmltv_output(channel, programs)
        all_xmltv_data.append(xmltv_root)

    # Combine all channel data into one XMLTV file
    if all_xmltv_data:
        combined_tv = all_xmltv_data[0]
        for tv_element in all_xmltv_data[1:]:
            for child in tv_element:
                combined_tv.append(child)
        xml_output = prettify_xml(combined_tv)
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(xml_output)
        print(f"\nXMLTV file generated: {output_filename}")
        print(f"Total channels: {len(channels)}")
        total_programs = sum(1 for elem in combined_tv.iter() if elem.tag == 'programme')
        print(f"Total programs: {total_programs}")
    else:
        print("No data to export")

if __name__ == "__main__":
    main()