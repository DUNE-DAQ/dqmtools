from flask import Flask, send_from_directory, render_template_string, render_template, request 
import re
import os
from collections import defaultdict
from cachetools import cached, TTLCache
import pandas as pd

app = Flask(__name__)

# Set the directory you want to serve the images from
IMAGE_DIRECTORY = '/nfs/rscratch/np04daq'

# Store the last modification time
last_mod_time = 0


def gather_EventDisplay_files(directory, filename_regex, to_find=['run', 'trigger', 'element_id', 'plane']):
    file_dict = {k : [] for k in to_find}
    file_dict['filename'] = []
    
    for filename in os.listdir(directory):
        match = filename_regex.match(filename)
        if not match:
            continue

        for name in to_find:
            file_dict[name].append(int(match[name]))
        file_dict['filename'].append(filename)  # Fixed: was missing .append()

    return_df = pd.DataFrame.from_dict(file_dict)
    return return_df

def filter_EventDisplay_files(directory, filename_regex, to_find=['run', 'trigger', 'element_id', 'plane'], filters: dict={}):
    '''
    Filter out unwanted entries
    '''
    
    event_file_df = gather_EventDisplay_files(directory, filename_regex, to_find)
    
    for filter, val in filters.items():
        if val is None:
            continue
        event_file_df = event_file_df[event_file_df[filter]==int(val)]
    return event_file_df


def get_latest_pds_plots(directory):
    filename_regex = re.compile(r"run(?P<run>\d+)_(?P<trigger>\d+)_([^_]+)\.svg")
    print(gather_EventDisplay_files(directory, filename_regex), ['run', 'trigger'])
    return gather_EventDisplay_files(directory, filename_regex, ['run', 'trigger'])

def get_latest_WIBTests_files(directory):
    filename_regex = re.compile(r"Tests_WIBS_results_run(?P<run>\d+)_trigger(?P<trigger>\d+)\.[^.]+")    
    filename_df = gather_EventDisplay_files(directory, filename_regex, ['run', 'trigger'])
    
    # Get max run and then max trigger for that run
    max_image = filename_df.sort_values(['run','trigger']).iloc[0]['filename']
    return [max_image]


def get_latest_EventDisplay_files(directory, select_element=None, select_plane=None):
    filename_regex = re.compile(
        r"""^EventDisplay_run(?P<run>\d+)
            _trigger(?P<trigger>\d+)
            _seq\d+
            _(?P<element_type>APA|CRP)(?P<element_id>\d+)?     # APA<digits> or CRP[digits optional]
            _plane(?P<plane>\d+)\.png$""",
        re.X
    )
    
    filtered_df = filter_EventDisplay_files(directory, filename_regex, filters={'element_id': select_element, 'plane_id': select_plane})
    # Now we get file for the max run/trigger for each element/plane
    
    max_for_el_plane = (filtered_df.sort_values(['run', 'trigger'], ascending=[False, False])
          .drop_duplicates(['element_id', 'plane'], keep='first')).sort_values(['element_id','plane'])

    return max_for_el_plane['filename'].to_list()


@app.route('/')
@app.route('/index')
@app.route('/home')
def index():
    return render_template('index.html')

@app.route('/event_display/')
@app.route('/event_display/run<run>/trigger<trigger>')
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
    print(IMAGE_DIRECTORY+subdir, filename)
    return send_from_directory(IMAGE_DIRECTORY+subdir, filename)

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
