import json
import sys
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom

def main():
    # Get input file from command line or use default
    input_file = 'gracenote/channels.json'
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    # Get output file from command line or use default
    output_file = 'guide/channels.xml'
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    # Read and parse JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Create XML structure
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Gracenote TV Listings')
    tv.set('source-info-url', 'https://tvlistings.gracenote.com')
    tv.set('generator-info-name', 'Gracenote TV Converter')
    
    # Process each channel
    for channel_data in data:
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
        
        # Get today's date at 04:00:00
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
                        # Convert timestamps
                        start_time = datetime.fromtimestamp(program['startTime'])
                        end_time = datetime.fromtimestamp(program['endTime'])
                        
                        start_time_str = start_time.strftime('%Y%m%d%H%M%S +0000')
                        end_time_str = end_time.strftime('%Y%m%d%H%M%S +0000')
                        
                        # Get program details
                        rating = program.get('rating')
                        program_info = program.get('program', {})
                        title = program_info.get('title', '')
                        short_desc = program_info.get('shortDesc')
                        season = program_info.get('season')
                        episode = program_info.get('episode')
                        episode_title = program_info.get('episodeTitle')
                        
                        # Create programme element
                        programme_elem = ET.SubElement(tv, 'programme')
                        programme_elem.set('start', start_time_str)
                        programme_elem.set('stop', end_time_str)
                        programme_elem.set('channel', xmltv_id)
                        
                        # Add title
                        title_elem = ET.SubElement(programme_elem, 'title')
                        title_elem.set('lang', 'en')
                        title_elem.text = title
                        
                        # Add sub-title if available
                        if episode_title:
                            sub_title_elem = ET.SubElement(programme_elem, 'sub-title')
                            sub_title_elem.set('lang', 'en')
                            sub_title_elem.text = episode_title
                        
                        # Add description if available
                        if short_desc:
                            desc_elem = ET.SubElement(programme_elem, 'desc')
                            desc_elem.set('lang', 'en')
                            desc_elem.text = short_desc
                        
                        # Add episode numbers if available
                        if season is not None and episode is not None:
                            episode_ns = ET.SubElement(programme_elem, 'episode-num')
                            episode_ns.set('system', 'xmltv_ns')
                            episode_ns.text = f"{season}.{episode}.0"
                            
                            episode_onscreen = ET.SubElement(programme_elem, 'episode-num')
                            episode_onscreen.set('system', 'onscreen')
                            episode_onscreen.text = f"S{season}E{episode}"
                        
                        # Add rating if available
                        if rating:
                            rating_elem = ET.SubElement(programme_elem, 'rating')
                            value_elem = ET.SubElement(rating_elem, 'value')
                            value_elem.text = rating
                            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for channel {name}: {e}")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response for channel {name}: {e}")
        except Exception as e:
            print(f"Unexpected error processing channel {name}: {e}")
    
    # Create pretty XML and save to file
    xml_str = minidom.parseString(ET.tostring(tv)).toprettyxml(indent="  ")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    
    print(f"TV guide saved to {output_file}")

if __name__ == "__main__":
    main()