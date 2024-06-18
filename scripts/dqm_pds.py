from hdf5libs import HDF5RawDataFile

import os
import detdataformats
import click

from daqdataformats import FragmentType
from rawdatautils.unpack.daphne import *
from tqdm import tqdm

import os
from os.path import join, getmtime

import numpy as np
import pandas as pd
import time

from dqmtools.dqmpds import *

def extract_fragment_info(frag):
    frh = frag.get_header()
    scr_id = frh.element_id.id
    fragType = frh.fragment_type

    if fragType == FragmentType.kDAPHNE.value:  # For self trigger
        trigger = 'self_trigger'
        adcs = np_array_adc(frag)
        channels = np_array_channels(frag)
    elif fragType == 13:  # For full_stream
        trigger = 'full_stream'
        adcs = np_array_adc_stream(frag).transpose()
        channels = np_array_channels_stream(frag)[0]

    return scr_id, trigger, channels, adcs

def dhf5_reader(path, file_list):
    det = 'HD_PDS'
    output_list = []

    for file in file_list:
        filename = f'{path}/{file}'
        h5_file = HDF5RawDataFile(filename)
        records = h5_file.get_all_record_ids()
        
        for r in tqdm(records, desc='Reading data records'):
            pds_geo_ids = list(h5_file.get_geo_ids_for_subdetector(r, detdataformats.DetID.string_to_subdetector(det)))
            
            for gid in pds_geo_ids:
                frag = h5_file.get_frag(r, gid)
                scr_id, trigger, channels, adcs = extract_fragment_info(frag)
                
                for index, ch in enumerate(channels):
                    selected_adcs = np.array(adcs[index])[:262000] if trigger == 'full_stream' else np.array(adcs[index])
    
                    endpoint = find_endpoint(scr_id)
                    output_list.append([trigger, endpoint, channels[index], selected_adcs])

    return output_list

def fig_creator(path):   
    files_list= os.listdir(path)
    files_with_times = [(file, getmtime(join(path, file))) for file in files_list]
    sorted_files = sorted(files_with_times, key=lambda x: x[1], reverse=True)
    sorted_filenames = [file[0] for file in sorted_files]

    last_4_files = sorted_filenames[:4]
    data_list = dhf5_reader(path, last_4_files)
    df        = df_data(data_list)
    map_df    = df_channel_map(df)
    fig_baseline, fig_rms = baseline_rms_plot(map_df)
    fig_waveform = waveforms_plot(map_df)
    heat_map  = heat_map_plot(map_df)

    file  =files_list[0]
    run   =file.split('_')[2]
    run_id=file.split('_')[3]
    
    output_path = f'/nfs/rscratch/pds/plot/'

    #fig_baseline.write_image(f"{output_path}/{run}_{run_id}_Baseline.svg")
    #fig_rms.write_image(f"{output_path}/{run}_{run_id}_RMS.svg")
    #fig_waveform.write_image(f"{output_path}/{run}_{run_id}_Waveform.svg")
    #heat_map.write_image(f"{output_path}/{run}_{run_id}_Heat.svg")

    fig_baseline.write_image(f"Baseline.svg")
    fig_rms.write_image(f"RMS.svg")
    fig_waveform.write_image(f"Waveform.svg")
    heat_map.write_image(f"Heat.svg")

@click.command()
@click.option("--path", '-p', default = '/nfs/rscratch/np04daq/DQM_DATA/NP04/', help="Insert the desired file.")
def main(path):
    while True:
        fig_creator(path)
        print("Waiting for 5 minutes before the next update...")
        time.sleep(5 * 60)  # Sleep for 10 minutes

if __name__ == "__main__":
    main()
