#!/usr/bin/env python3

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *
from dqmtools.dqmtests import *
from dqmtools.dqmplots import *

import hdf5libs

import concurrent.futures
import multiprocessing as mp

import os

import pytz
import timeit


from rich import print


import click
@click.command()
@click.argument('input_data', type=click.Path(exists=True))
@click.argument('output_dir', type=click.Path(exists=True))
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 12)')
@click.option('--nskip', default=0, help='How many trigger records to skip at start of file')
@click.option('--nrecords', default=1, help='How man trigger records to plot')
@click.option('--imgtype', default='svg', help='Type of image to write')
@click.option('--component',default=None, help='specific component to plot')
@click.option('--plane',default=None, help='specific plane to plot')
#@click.option('--hd/--vd', default=True, help='Whether we are running HD (or VD) (default: "HD")')

def main(input_data, output_dir, nworkers, nskip, nrecords, imgtype, component, plane):

    filename = input_data
    if(os.path.isdir(input_data)):
        print(f"Scanning directory {input_data}")
        files = os.listdir(input_data)
        paths = [os.path.join(input_data, basename) for basename in files if not basename.endswith(".writing")]
        filename = max(paths, key=os.path.getctime)

    print(f'Opening file {filename}')
    
    h5_file = hdf5libs.HDF5RawDataFile(filename)
    records = h5_file.get_all_record_ids()

    if len(records)==0:
        print(f'No records found in file {filename}.')
        return

    if len(records)<nskip:
        print(f'Requested to skip {nskip} records, but there are only {len(records)} in the file.')
        return

    record_count = 0
    
    if nrecords==-1:
        nrecords = len(records)
    
    while record_count < nrecords and (record_count+nskip)<len(records):
        
        rid = records[nskip+record_count]
        df_dict = {}

        print(f"Processing record {rid} in file {filename}.")
        df_load_start_time = timeit.default_timer()

        ws = dfc.Workspace(h5_file, rid)
        ws.load_record(MAX_WORKERS=nworkers,ana_data_prescale=1,wvfm_data_prescale=1)
        df_dict = ws
        
        # df_dict = dfc.process_record(h5_file, rid, df_dict, MAX_WORKERS=nworkers,ana_data_prescale=1,wvfm_data_prescale=1)
        df_dict = dfc.concatenate_dataframes(df_dict)
        
        print(f"Finished creating dataframes.")
        df_load_elapsed_time = timeit.default_timer()-df_load_start_time
        print(f"Elapsed time {df_load_elapsed_time}")

        pd.set_option('display.max_columns', None)
        print(df_dict["trh"])
        
        index = df_dict["trh"].index[0]

        det_keys = [ key for key in df_dict if key.startswith('detw') and 'TPC' in key ]

        # FIXME : use op_env instead?
        hd = any("kHD" in k for k in det_keys) #else, vd
        
        offset=True
        
        if plane is not None:
            planes = [ int(plane) ]
        else:
            planes = [0, 1, 2]

        element_ids = []
        if component is not None:
            element_ids = [ int(component) ]
        else:
            if(hd):
                element_ids = [1,2,3,4]
            else:
                element_ids = [2,3,4,5]

        element_type="APA" if hd else "CRP"

        elements = [ f'{element_type}{i}' for i in element_ids ]
                
        myplanes = []
        for el in elements:
            for plane in planes:
                myplanes.append((el,plane))


        df_dict["trh"]['trigger_time_cern'] = pd.to_datetime(df_dict["trh"]['trigger_time'])
        df_dict['trh']['trigger_time_cern'] = df_dict['trh']['trigger_time_cern'].dt.tz_convert('Europe/Zurich')
        trigger_timestamp = df_dict["trh"]["trigger_time"].iloc[0]
        trigger_timestamp_cern = df_dict["trh"]["trigger_time_cern"].iloc[0]

        trigger_types_str = "("
        for trigtype in df_dict["trh"]["trigger_type_bits"].iloc[0]:
            trigger_types_str = trigger_types_str + trigtype.name[1:] + ","
        trigger_types_str=trigger_types_str[:-1]+")"

        df_prep_elapsed_time = timeit.default_timer()-df_load_start_time
        print(f"Elapsed time {df_prep_elapsed_time}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
            # myplanes = myplanes[2:3]
            future_p = {
                executor.submit(make_adc_map_fig, p[0],p[1], df_dict, det_keys, offset, index, imgtype, trigger_types_str, trigger_timestamp_cern, output_dir): p for p in myplanes
            }

            for future in concurrent.futures.as_completed(future_p):
                res = future.result()
                image_elapsed_time = timeit.default_timer()-df_load_start_time
                print(f"Completed image {res}")
                print(f"Elapsed time {image_elapsed_time}")

        record_count += 1
        print(f"Done with {record_count} records.")

def make_adc_map_fig(element, plane, df_dict, det_keys, offset, index, imgtype, trigger_types_str, trigger_timestamp_cern, output_dir):
    print(f"Image {element} plane {plane} processing started...")

    fig = plot_TPC_adc_map_mpl(df_dict=df_dict, det_keys=det_keys,
                        plane=plane, ele=element,
                        make_static=True,
                        offset=offset,
                        make_tp_overlay=False,
                        orientation='vertical',
                        colorscale='plasma',
                        color_range=(-256,256),
                        run=index[0],
                        trigger=index[1],
                        seq=index[2],
                        figsize=(12,8),
                        )
    print(f"Figure for Element {element} plane {plane} processed...")
    fig.suptitle(f"Run {int(index[0])}, Trigger {int(index[1])}, {element} Plane {plane}"+"\n"+f"Trigger Type {trigger_types_str}, {trigger_timestamp_cern} (CERN)", ha='left', x=0.1, size=20) 
    img_file_name = f"EventDisplay_run{int(index[0])}_trigger{int(index[1])}_seq{int(index[2])}_{element}_plane{plane}.{imgtype}"
    fig.tight_layout()
    fig.savefig(output_dir+'/'+img_file_name)
    print(f"Image {img_file_name} saved")

    return img_file_name

if __name__ == '__main__':
    main()
