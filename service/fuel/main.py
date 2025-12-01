import json
import sys
import xml.etree.ElementTree as ET
import argparse
import requests
from typing import Optional, Dict, List
import urllib3
from xml.dom import minidom

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_epg_data(channel_id: str, max_items: int = 50) -> Optional[ET.Element]:
    """Fetch EPG data from Fuelmedia API"""
    url = f"https://fueltools-prod01-v1-fast.fuelmedia.io/mrss?ChId={channel_id}&maxItems={max_items}&ContentType=epg"
    
    try:
        response = requests.get(url, verify=False, timeout=30)
        response.raise_for_status()
        
        # Check if response contains valid XML
        if not response.content.strip():
            print(f"Warning: Empty response for channel {channel_id}")
            return None
            
        # Try to parse XML
        xml_root = ET.fromstring(response.content)
        return xml_root
        
    except ET.ParseError as e:
        print(f"Error parsing XML for channel {channel_id}: {e}")
        print(f"Response content (first 500 chars): {response.content[:500]}")
        return None
    except Exception as e:
        print(f"Error fetching data for channel {channel_id}: {e}")
        return None

def parse_channel_data(xml_root: ET.Element) -> Dict:
    """Extract channel information from XML"""
    channel_data = {'display_name': ''}
    
    try:
        # Try different possible locations for channel info
        # Method 1: Direct channel element
        channel_elem = xml_root.find('channel')
        if channel_elem is None:
            # Method 2: Try RSS format
            channel_elem = xml_root.find('.//channel')
        
        if channel_elem is not None:
            # Try different display-name locations
            display_name_elem = channel_elem.find('display-name')
            if display_name_elem is None:
                display_name_elem = channel_elem.find('title')  # RSS format
            
            if display_name_elem is not None and display_name_elem.text:
                channel_data['display_name'] = display_name_elem.text.strip()
    except Exception as e:
        print(f"Error parsing channel data: {e}")
    
    return channel_data

def parse_programs(xml_root: ET.Element, language: str) -> List[Dict]:
    """Extract program information from XML"""
    programs = []
    
    try:
        # Try different XML structures
        
        # Method 1: TV XML format (programme elements)
        programme_elements = xml_root.findall('.//programme')
        if programme_elements:
            for prog in programme_elements:
                try:
                    program_data = {
                        'start': prog.get('start', ''),
                        'stop': prog.get('stop', ''),
                        'title': '',
                        'desc': ''
                    }
                    
                    # Extract title
                    title_elem = prog.find('title')
                    if title_elem is not None and title_elem.text:
                        program_data['title'] = title_elem.text.strip()
                    
                    # Extract description
                    desc_elem = prog.find('desc')
                    if desc_elem is None:
                        desc_elem = prog.find('description')
                    
                    if desc_elem is not None and desc_elem.text:
                        program_data['desc'] = desc_elem.text.strip()
                    
                    programs.append(program_data)
                except Exception as e:
                    print(f"Error parsing programme element: {e}")
                    continue
        
        # Method 2: RSS format (item elements)
        if not programs:
            item_elements = xml_root.findall('.//item')
            for item in item_elements:
                try:
                    program_data = {
                        'start': '',
                        'stop': '',
                        'title': '',
                        'desc': ''
                    }
                    
                    # Extract title
                    title_elem = item.find('title')
                    if title_elem is not None and title_elem.text:
                        program_data['title'] = title_elem.text.strip()
                    
                    # Extract description
                    desc_elem = item.find('description')
                    if desc_elem is not None and desc_elem.text:
                        program_data['desc'] = desc_elem.text.strip()
                    
                    # Try to get start/stop from pubDate or other elements
                    pubdate_elem = item.find('pubDate')
                    if pubdate_elem is not None and pubdate_elem.text:
                        # Convert pubDate to start time (simplified)
                        program_data['start'] = pubdate_elem.text.strip()
                    
                    programs.append(program_data)
                except Exception as e:
                    print(f"Error parsing item element: {e}")
                    continue
        
        # Method 3: Look for any program-like structures
        if not programs:
            # Try to find any elements that might contain program data
            for elem in xml_root.iter():
                if elem.tag.endswith('program') or elem.tag.endswith('show'):
                    try:
                        program_data = {
                            'start': elem.get('start', elem.get('begin', '')),
                            'stop': elem.get('stop', elem.get('end', '')),
                            'title': '',
                            'desc': ''
                        }
                        
                        # Look for title and description in child elements
                        for child in elem:
                            if child.tag.endswith('title') or child.tag.endswith('name'):
                                if child.text:
                                    program_data['title'] = child.text.strip()
                            elif child.tag.endswith('desc') or child.tag.endswith('description'):
                                if child.text:
                                    program_data['desc'] = child.text.strip()
                        
                        if program_data['title']:  # Only add if we have a title
                            programs.append(program_data)
                    except:
                        continue
    
    except Exception as e:
        print(f"Error parsing programs: {e}")
    
    # Limit to 2 days worth of programs if needed
    # (You might want to add date filtering logic here)
    
    return programs

def create_xmltv_output(all_channels_data: List[Dict]) -> ET.Element:
    """Create XMLTV formatted XML from all channel data"""
    # Create root element
    tv = ET.Element('tv')
    tv.set('source-info-name', 'Bitcentral, Inc.')
    tv.set('source-info-url', 'https://bitcentral.com')
    tv.set('generator-info-name', 'FUEL EPG Generator')
    
    # Add all channels and programs
    for channel_info in all_channels_data:
        channel_id = channel_info['channel_id']
        display_name = channel_info['display_name']
        language = channel_info['language']
        programs = channel_info['programs']
        
        # Add channel element
        channel = ET.SubElement(tv, 'channel')
        channel.set('id', channel_id)
        
        display_name_elem = ET.SubElement(channel, 'display-name')
        display_name_elem.text = display_name
        
        # Add programs for this channel
        for program in programs:
            if program['title']:  # Only add if we have a title
                programme = ET.SubElement(tv, 'programme')
                
                # Add start time (required)
                start_time = program['start'] if program['start'] else '20000101000000'
                programme.set('start', start_time)
                
                # Add stop time (required)
                stop_time = program['stop'] if program['stop'] else '20000101010000'
                programme.set('stop', stop_time)
                
                programme.set('channel', channel_id)
                
                # Add title
                title = ET.SubElement(programme, 'title')
                title.set('lang', language)
                title.text = program['title']
                
                # Add description if available
                if program['desc']:
                    desc = ET.SubElement(programme, 'desc')
                    desc.set('lang', language)
                    desc.text = program['desc']
    
    return tv

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate XMLTV EPG from Fuelmedia API')
    parser.add_argument('input_file', nargs='?', default='service/fuel/channels.json',
                       help='JSON file containing channel information (default: service/fuel/channels.json)')
    parser.add_argument('-o', '--output', default='guide/fuel.xml',
                       help='Output XML file (default: guide/fuel.xml)')
    
    args = parser.parse_args()
    
    # Load channel data
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        
        if not isinstance(channels_data, list):
            print(f"Error: Input file must contain a JSON array. Found {type(channels_data)}")
            sys.exit(1)
            
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{args.input_file}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading input file: {e}")
        sys.exit(1)
    
    all_channels_data = []
    processed_count = 0
    
    print(f"Processing {len(channels_data)} channel(s)...")
    
    # Process each channel
    for idx, channel_info in enumerate(channels_data, 1):
        channel_id = channel_info.get('channel_id')
        language = channel_info.get('language', 'en')
        
        if not channel_id:
            print(f"Warning [{idx}/{len(channels_data)}]: Skipping entry without channel_id")
            continue
        
        print(f"[{idx}/{len(channels_data)}] Processing channel: {channel_id} ({language})")
        
        # Fetch EPG data
        xml_root = fetch_epg_data(channel_id)
        if xml_root is None:
            print(f"  Failed to fetch data for channel {channel_id}")
            # Still create an entry with basic info
            all_channels_data.append({
                'channel_id': channel_id,
                'display_name': f"Channel {channel_id}",
                'language': language,
                'programs': []
            })
            continue
        
        # Parse channel and program data
        channel_data = parse_channel_data(xml_root)
        programs = parse_programs(xml_root, language)
        
        # Use channel ID as display name if not found
        display_name = channel_data.get('display_name', '')
        if not display_name:
            display_name = f"Channel {channel_id}"
        
        # Store data for XML generation
        all_channels_data.append({
            'channel_id': channel_id,
            'display_name': display_name,
            'language': language,
            'programs': programs
        })
        
        print(f"  Found {len(programs)} program(s)")
        processed_count += 1
    
    # Create combined XMLTV output
    if all_channels_data:
        print(f"\nCreating XMLTV file with data from {processed_count} channel(s)...")
        
        tv = create_xmltv_output(all_channels_data)
        
        # Add XML declaration and DOCTYPE
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
        
        # Convert to string and pretty print
        xml_str = ET.tostring(tv, encoding='utf-8').decode('utf-8')
        
        # Use minidom for pretty printing
        try:
            parsed_xml = minidom.parseString(xml_str)
            pretty_xml = parsed_xml.toprettyxml(indent="  ")
            
            # Remove the default XML declaration from minidom
            lines = pretty_xml.split('\n')
            if lines and lines[0].startswith('<?xml'):
                lines = lines[1:]
            pretty_xml = xml_declaration + '\n'.join(lines)
        except:
            # Fallback if minidom fails
            print("Warning: Could not pretty print XML, using basic formatting")
            pretty_xml = xml_declaration + xml_str
        
        # Write to file
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            print(f"Success! EPG data saved to {args.output}")
            print(f"Total channels: {len(all_channels_data)}")
            
            # Count total programs
            total_programs = sum(len(ch['programs']) for ch in all_channels_data)
            print(f"Total programs: {total_programs}")
            
        except Exception as e:
            print(f"Error writing to output file {args.output}: {e}")
            sys.exit(1)
    else:
        print("No EPG data was fetched. Output file not created.")

if __name__ == "__main__":
    main()
