from flask import Flask, send_from_directory, render_template_string, render_template, request 
import re
import os
from collections import defaultdict

app = Flask(__name__)

# Set the directory you want to serve the images from
IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'

# Store the last modification time
last_mod_time = 0

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


def get_latest_EventDisplay_files(directory,select_element=None,select_plane=None):
    
    # Regular expression to parse the filenames
    filename_regex = re.compile(r"EventDisplay_run(\d+)_trigger(\d+)_seq\d+_Element(\d+)_plane(\d+)\.svg")

    #print(directory)
    
    max_images = defaultdict(lambda: {'run': -1, 'trigger': -1, 'filename': ''})
        
    for filename in os.listdir(directory):
        match = filename_regex.match(filename)
        if match:
            run = int(match.group(1))
            trigger = int(match.group(2))
            element = int(match.group(3))
            plane = int(match.group(4))

            if select_element is not None:
                select_element = int(select_element)
                if element!=select_element:
                    continue

            if select_plane is not None:
                select_plane = int(select_plane)
                if plane!=select_plane:
                    continue
            
            # Check if this run and trigger number is larger than the current stored values
            key = (element, plane)
            if (run > max_images[key]['run']) or (run == max_images[key]['run'] and trigger > max_images[key]['trigger']):
                max_images[key]['run'] = run
                max_images[key]['trigger'] = trigger
                max_images[key]['filename'] = filename

    sorted_keys = sorted(max_images.keys(), key=lambda x: (x[0], x[1]))
    sorted_images = [ max_images[key]['filename'] for key in sorted_keys ]
    return sorted_images
        
@app.route('/')
@app.route('/index')
@app.route('/home')
def index():
    return render_template('index.html')

@app.route('/event_display/')
@app.route('/event_display/element<element>')
@app.route('/event_display/element<element>_plane<plane>')
def event_display(element=None, plane=None):
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_element=element, select_plane=plane)
    return render_template('event_display.html', images=evd_images, element=element, plane=plane)

@app.route('/event_display_grid/element<element>')
def event_display_grid(element=None):
    evd_images = get_latest_EventDisplay_files(IMAGE_DIRECTORY + "/EventDisplays", select_element=element)
    return render_template('event_display_grid.html', images=evd_images, element=element)

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
