import json
import sys
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom

def main():
    # Get input file from command line argument or use default
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'gracenote/channels.json'
    
    # Get output file from command line argument or use default
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'guide/channels.xml'
    
    # Read JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
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
    
    # Prepare request data
    request_data = {
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
    
    # Make API request
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        "https://tvlistings.gracenote.com/api/sslgrid",
        headers=headers,
        json=request_data
    )
    
    programs = response.json()
    
    # Create XML structure
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Gracenote TV Listings')
    tv.set('source-info-url', 'https://tvlistings.gracenote.com')
    tv.set('generator-info-name', 'Gracenote TV Converter')
    
    # Add channel
    channel = ET.SubElement(tv, 'channel')
    channel.set('id', xmltv_id)
    display_name = ET.SubElement(channel, 'display-name')
    display_name.text = name
    
    # Process programs for 3 days
    for day_offset in range(3):
        current_date = (today + timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        if current_date in programs:
            day_programs = programs[current_date]
            
            for program in day_programs:
                # Convert timestamps
                start_time = datetime.fromtimestamp(program['startTime'])
                end_time = datetime.fromtimestamp(program['endTime'])
                
                start_time_str = start_time.strftime('%Y%m%d%H%M%S +0000')
                end_time_str = end_time.strftime('%Y%m%d%H%M%S +0000')
                
                # Extract program data
                rating = program.get('rating')
                program_data = program.get('program', {})
                title = program_data.get('title', '')
                short_desc = program_data.get('shortDesc')
                season = program_data.get('season')
                episode = program_data.get('episode')
                episode_title = program_data.get('episodeTitle')
                
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
                    episode_num_xmltv = ET.SubElement(programme, 'episode-num')
                    episode_num_xmltv.set('system', 'xmltv_ns')
                    episode_num_xmltv.text = f"{season}.{episode}.0"
                    
                    episode_num_onscreen = ET.SubElement(programme, 'episode-num')
                    episode_num_onscreen.set('system', 'onscreen')
                    episode_num_onscreen.text = f"S{season}E{episode}"
                
                # Add rating if available
                if rating:
                    rating_elem = ET.SubElement(programme, 'rating')
                    value_elem = ET.SubElement(rating_elem, 'value')
                    value_elem.text = str(rating)
    
    # Convert to pretty XML and save
    xml_str = minidom.parseString(ET.tostring(tv)).toprettyxml(indent="  ")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    
    print(f"XML TV guide saved to {output_file}")

if __name__ == "__main__":
    main()