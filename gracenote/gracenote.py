import json
import sys
import time
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom

def main():
    # Get input file from command line argument or use default
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'channels.json'
    
    # Read and parse JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Extract channel data
    xmltv_id = data['xmltv_id']
    device = data['device']
    lineup_id = data['lineup_id']
    headend_id = data['headend_id']
    country = data['country']
    postal = data['postal']
    site_id = data['site_id']
    name = data['name']
    
    # Calculate timestamp for today 04:00:00
    today = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
    timestamp = int(today.timestamp())
    date = today.strftime('%Y-%m-%d')
    
    # Prepare request payload
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
    
    # Make API request
    response = requests.post(
        "https://tvlistings.gracenote.com/api/sslgrid",
        json=payload,
        headers=headers
    )
    
    programs_data = response.json()
    
    # Create XML structure
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Gracenote TV Listings')
    tv.set('source-info-url', 'https://tvlistings.gracenote.com')
    tv.set('generator-info-name', 'Gracenote TV Converter')
    
    # Add channel element
    channel = ET.SubElement(tv, 'channel')
    channel.set('id', xmltv_id)
    
    display_name = ET.SubElement(channel, 'display-name')
    display_name.text = name
    
    # Process programs
    if date in programs_data:
        for program in programs_data[date]:
            # Extract program data
            start_time = program['startTime']
            end_time = program['endTime']
            rating = program.get('rating')
            program_info = program['program']
            title = program_info['title']
            short_desc = program_info.get('shortDesc')
            season = program_info.get('season')
            episode = program_info.get('episode')
            episode_title = program_info.get('episodeTitle')
            
            # Convert timestamps to XMLTV format
            start_dt = datetime.fromtimestamp(start_time)
            end_dt = datetime.fromtimestamp(end_time)
            start_str = start_dt.strftime('%Y%m%d%H%M%S +0000')
            end_str = end_dt.strftime('%Y%m%d%H%M%S +0000')
            
            # Create programme element
            programme = ET.SubElement(tv, 'programme')
            programme.set('start', start_str)
            programme.set('stop', end_str)
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
                episode_ns = ET.SubElement(programme, 'episode-num')
                episode_ns.set('system', 'xmltv_ns')
                episode_ns.text = f"{season}.{episode}.0"
                
                episode_onscreen = ET.SubElement(programme, 'episode-num')
                episode_onscreen.set('system', 'onscreen')
                episode_onscreen.text = f"S{season}E{episode}"
            
            # Add rating if available
            if rating:
                rating_elem = ET.SubElement(programme, 'rating')
                value_elem = ET.SubElement(rating_elem, 'value')
                value_elem.text = rating
    
    # Convert to pretty XML string
    xml_str = ET.tostring(tv, encoding='utf-8')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")
    
    # Save to output file
    output_file = f"{xmltv_id}_programs.xml"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(pretty_xml)
    
    print(f"XMLTV file saved as: {output_file}")

if __name__ == "__main__":
    main()
