from flask import Flask, send_from_directory, render_template_string, render_template, request 
import re
import os
from collections import defaultdict
from cachetools import cached, TTLCache
from enum import IntEnum

app = Flask(__name__)

# Set the directory you want to serve the images from
IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'

# Store the last modification time
last_mod_time = 0

class EventDisplayIndex(IntEnum):
    RUN = 0
    TRIGGER = 1
    ELEMENT = 2
    PLANE = 3

def get_latest_pds_plots(directory):

    max_images = defaultdict(lambda: {'run': -1, 'trigger': -1, 'filename': ''})
    filename_regex = re.compile(r"run(\d+)_(\d+)_([^_]+)\.svg")
    
    for filename in os.listdir(directory):

        match = filename_regex.match(filename)
        if match:
            run = int(match.group(1))
            run_id = int(match.group(2))
            key = str(match.group(3))

            if (run > max_images[key]['run']) or (run == max_images[key]['run'] and run_id > max_images[key]['trigger']):
                max_images[key]['run'] = run
                max_images[key]['trigger'] = run_id
                max_images[key]['filename'] = filename

    
    sorted_keys = list(max_images.keys())
    sorted_keys.sort()
    images = [ max_images[key]['filename'] for key in sorted_keys ]    
    return images


def get_latest_WIBTests_files(directory):
    
    filename_regex = re.compile(r"Tests_WIBS_results_run(\d+)_trigger(\d+)\.[^.]+")    
    max_image = None
    max_run = 0
    max_trigger = 0
    for filename in os.listdir(directory):
        match = filename_regex.match(filename)
        if match:
            run = int(match.group(1))
            trigger = int(match.group(2))
            
            # Check if this run and trigger number is larger than the current stored values
            if (run > max_run) or (run == max_run and trigger > max_trigger):
                max_run = run
                max_trigger = trigger
                max_image = filename
                
    return [ max_image ]


def gather_EventDisplay_files(directory):
        
    # Regex parse ... for now
    filename_regex = re.compile(r"EventDisplay_run(\d+)_trigger(\d+)_seq\d+_APA(\d+)_plane(\d+)\.svg")
    filename_regex = re.compile(
        r"""^EventDisplay_run(?P<run>\d+)
            _trigger(?P<trigger>\d+)
            _seq\d+
            _(?P<element_type>APA|CRP)(?P<element_id>\d+)?     # APA<digits> or CRP[digits optional]
            _plane(?P<plane>\d+)\.svg$""",
        re.X
    )

    return_dict = {}

    for filename in os.listdir(directory):
        match = filename_regex.match(filename)
        if not match:
            continue
        
        # Get the information about the run
        run = int(match['run'])
        trigger = int(match['trigger'])
        element_id = int(match['element_id'])
        plane = int(match['plane'])
        
        return_dict[(run, trigger, element_id, plane)] = filename

    return return_dict


def filter_EventDisplay_files(directory, select_run=None, select_trigger=None, select_element=None, select_plane=None):
    
    event_file_dict = gather_EventDisplay_files(directory)
        
    search_list = [lambda _: True]
    
    if select_run is not None:
        search_list.append(lambda x: x[EventDisplayIndex.RUN.value]==int(select_run))
    if select_trigger is not None:
        search_list.append(lambda x: x[EventDisplayIndex.TRIGGER.value]==int(select_trigger))
    if select_element is not None:
        search_list.append(lambda x: x[EventDisplayIndex.ELEMENT.value]==int(select_element))
    if select_plane is not None:
        search_list.append(lambda x: x[EventDisplayIndex.PLANE.value]==int(select_plane))

    return { k:v for k,v in event_file_dict.items() if all(s(k) for s in search_list) }
        

def get_latest_EventDisplay_files(directory, select_element=None, select_plane=None):
    filtered_files = filter_EventDisplay_files(directory, select_element, select_plane)
    print("filtered_files", filtered_files)
    # Now we get file for the max run/trigger for each element/plane

    # Firstly split filtered files by element/plane
    element_plane_dict = {}
    for key, value in filtered_files.items():
        element_plane_key = (key[EventDisplayIndex.ELEMENT.value], key[EventDisplayIndex.PLANE.value])
        if element_plane_key not in element_plane_dict:
            element_plane_dict[element_plane_key] = {}
        element_plane_dict[element_plane_key][key] = value

    # Now get the max run/trigger for each element/plane
    max_files = {}
    for (element, plane), files in element_plane_dict.items():
        max_run = max(key[EventDisplayIndex.RUN] for key in files.keys())
        max_trigger = max(key[EventDisplayIndex.TRIGGER] for key in files.keys())
        max_files[(element, plane)] = files[(max_run, max_trigger, element, plane)]


    sorted_keys = sorted(max_files.keys(), key=lambda x: (x[0], x[1]))
    sorted_images = [ max_files[key] for key in sorted_keys ]
    print(sorted_images)

    return sorted_images


@app.route('/')
@app.route('/index')
@app.route('/home')
def index():
    return render_template('index.html')

@app.route('/event_display/')
@app.route('/event_display/apa<ele>')
@app.route('/event_display/apa<ele>_plane<plane>')
@app.route('/event_display/crp<ele>')
@app.route('/event_display/crp<ele>_plane<plane>')
def event_display(ele=None, plane=None):
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_element=ele, select_plane=plane)
    return render_template('event_display.html', images=evd_images, ele=ele, plane=plane)

@app.route('/event_display_grid/apa<ele>')
@app.route('/event_display_grid/crp<ele>')
def event_display_grid(ele=None):
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_element=ele)
    return render_template('event_display_grid.html', images=evd_images, ele=ele)

@app.route('/event_display_plane/plane<plane>')
def event_display_plane(plane=None):
    if plane is None: plane = 2
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY+"/EventDisplays", select_plane=plane)
    return render_template('event_display_plane.html', images=evd_images, plane=plane)

@app.route('/tests/wibs')
def tests_wibs():
    test_images = get_latest_WIBTests_files(IMAGE_DIRECTORY+"/WIBTests")
    return render_template('tests_wibs.html', images=test_images)

@app.route('/pds')
def pds():
    images = get_latest_pds_plots(IMAGE_DIRECTORY+"/pds_plots")
    return render_template("pds.html",images=images)

@app.route('/images/<subdir>/<path:filename>')
def serve_image(subdir,filename):
    return send_from_directory(IMAGE_DIRECTORY+"/"+subdir, filename)

import click
@click.command()
@click.argument('image_dir', type=click.Path(exists=True))
@click.option('--port', default=8005, help='Which port to run the image browser on')

def main(image_dir,port):
    global IMAGE_DIRECTORY

    IMAGE_DIRECTORY=image_dir
    
    app.run(debug=True,host='0.0.0.0',port=port)

if __name__ == '__main__':
    main()
