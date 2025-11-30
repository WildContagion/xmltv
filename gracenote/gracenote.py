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
    
    # Read and parse JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Create XML structure
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Gracenote TV Listings')
    tv.set('source-info-url', 'https://tvlistings.gracenote.com')
    tv.set('generator-info-name', 'Gracenote TV Converter')
    
    # Process each channel
    for channel in data:
        xmltv_id = channel.get('xmltv_id')
        device = channel.get('device')
        lineup_id = channel.get('lineup_id')
        headend_id = channel.get('headend_id')
        country = channel.get('country')
        postal = channel.get('postal')
        site_id = channel.get('site_id')
        name = channel.get('name')
        
        # Add channel to XML
        channel_elem = ET.SubElement(tv, 'channel')
        channel_elem.set('id', xmltv_id)
        display_name = ET.SubElement(channel_elem, 'display-name')
        display_name.text = name
        
        # Calculate timestamp for today 04:00:00
        today = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
        timestamp = int(today.timestamp())
        date_str = today.strftime('%Y-%m-%d')
        
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
            # Make API request
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            programs_data = response.json()
            
            # Process programs for 3 days
            for day_offset in range(3):
                current_date = today + timedelta(days=day_offset)
                date_key = current_date.strftime('%Y-%m-%d')
                
                if date_key in programs_data:
                    day_programs = programs_data[date_key]
                    
                    for program in day_programs:
                        # Extract program data
                        start_time = program.get('startTime')
                        end_time = program.get('endTime')
                        rating = program.get('rating')
                        program_info = program.get('program', {})
                        
                        title = program_info.get('title', '')
                        short_desc = program_info.get('shortDesc')
                        season = program_info.get('season')
                        episode = program_info.get('episode')
                        episode_title = program_info.get('episodeTitle')
                        
                        # Convert timestamps
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
                            # XMLTV NS format
                            ep_num_ns = ET.SubElement(programme, 'episode-num')
                            ep_num_ns.set('system', 'xmltv_ns')
                            ep_num_ns.text = f"{season}.{episode}.0"
                            
                            # Onscreen format
                            ep_num_onscreen = ET.SubElement(programme, 'episode-num')
                            ep_num_onscreen.set('system', 'onscreen')
                            ep_num_onscreen.text = f"S{season}E{episode}"
                        
                        # Add rating if available
                        if rating:
                            rating_elem = ET.SubElement(programme, 'rating')
                            value_elem = ET.SubElement(rating_elem, 'value')
                            value_elem.text = rating
            
        except requests.RequestException as e:
            print(f"Error fetching data for channel {xmltv_id}: {e}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response for channel {xmltv_id}: {e}")
    
    # Create pretty XML and save to file
    xml_str = minidom.parseString(ET.tostring(tv, encoding='utf-8')).toprettyxml(indent="  ")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    
    print(f"XMLTV file saved to: {output_file}")

if __name__ == "__main__":
    main()