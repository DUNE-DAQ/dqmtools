from flask import Flask, send_from_directory, render_template_string
import re
import os
from collections import defaultdict

app = Flask(__name__)

# Set the directory you want to serve the images from
IMAGE_DIRECTORY = '/nfs/rscratch/pds/plot/'

# Store the last modification time and images list
last_mod_time = 0
images = []

# Regular expression to parse the filenames
filename_regex = [
    re.compile(r"run(\d+)_(\d+)_Baseline.svg"),
    re.compile(r"run(\d+)_(\d+)_RMS.svg"),
    re.compile(r"run(\d+)_(\d+)_Waveform.svg"),
    re.compile(r"run(\d+)_(\d+)_Heat.svg")
]

def get_latest_files(directory):
    max_images = defaultdict(lambda: {'run': -1, 'trigger': -1, 'filename': ''})

    for filename in os.listdir(directory):
        file_to_add = []
        for file_regex in filename_regex:
                print(file_regex)
                match = file_regex.match(filename)
                if match:
                    run = int(match.group(1))
                    run_id = int(match.group(2))
                    key = (run, run_id, file_regex.pattern)
                    
                    if (run > max_images[key]['run']) or (run == max_images[key]['run'] and run_id > max_images[key]['run_id']):
                        max_images[key]['run'] = run
                        max_images[key]['run_id'] = run_id
                        max_images[key]['filename'] = filename
        sorted_keys = sorted(max_images.keys(), key=lambda x: (x[0], x[1]))
        sorted_images = [ max_images[key]['filename'] for key in sorted_keys ]
        print(sorted_images)
        #output.append[sorted_images]

    return sorted_images
# Template for displaying images
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>NP04 EVENT DISPLAYS</title>
    <script>
        // Refresh the page every 30 seconds
        setInterval(function() {
            window.location.reload();
        }, 30000);
    </script>
    <style>
        body {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .image-container {
            text-align: center;
            margin: 20px;
        }
        img {
            width: 80%;
            height: auto;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }
    </style>
</head>
<body>
    <h1>NP04 EVENT DISPLAYS</h1>
    {% for image in images %}
        <div class="image-container">
            <img src="{{ url_for('serve_image', filename=image) }}" alt="{{ image }}"/>
        </div>
    {% endfor %}
</body>
</html>
'''

@app.before_request
def check_for_new_images():
    global last_mod_time, images
    current_mod_time = os.path.getmtime(IMAGE_DIRECTORY)
    if current_mod_time != last_mod_time:
        last_mod_time = current_mod_time
        images = get_latest_files(IMAGE_DIRECTORY)

@app.route('/')
def index():
    global images
    images = get_latest_files(IMAGE_DIRECTORY)
    print(images)
    return render_template_string(HTML_TEMPLATE, images=images)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_DIRECTORY, filename)

import click

@click.command()
@click.argument('image_dir', type=click.Path(exists=True))
@click.option('--port', default=8005, help='Which port to run the image browser on')
def main(image_dir, port):
    global IMAGE_DIRECTORY
    IMAGE_DIRECTORY = image_dir
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
