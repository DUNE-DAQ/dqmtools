#!/usr/bin/env python3

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *
from dqmtools.dqmtests import *
from dqmtools.dqmplots import *

import hdf5libs

import concurrent.futures

import click
@click.command()
@click.argument('filename', type=click.Path(exists=True))
@click.argument('output_dir', type=click.Path(exists=True))
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 12)')
@click.option('--nskip', default=0, help='How many trigger records to skip at start of file')
@click.option('--imgtype', default='svg', help='Type of image to write')
#@click.option('--hd/--vd', default=True, help='Whether we are running HD (or VD) (default: "HD")')
#@click.option('--warm/--cold', default=True, help='Whether we are running warm or cold (default: "warm")')
#@click.option('--pds',is_flag=True, help='If PDS was included and should be processed')
#@click.option('--wibpulser', is_flag=True, help='WIBs in pulser mode')
#@click.option('--make-plots',is_flag=True, help='Option to make plots')

def main(filename, output_dir, nworkers, nskip, imgtype):

    df_dict = {}
        
    h5_file = hdf5libs.HDF5RawDataFile(filename)
    records = h5_file.get_all_record_ids()

    if len(records)==0:
        print(f'No records found in file {filename}.')
        return

    if len(records)<nskip:
        print(f'Requested to skip {nskip} records, but there are only {len(records)} in the file.')
        return

    
    rid = records[nskip]

    print(f"Processing record {rid} in file {filename}.")
    
    df_dict = dfc.process_record(h5_file,rid,df_dict,MAX_WORKERS=nworkers,ana_data_prescale=1,wvfm_data_prescale=1)
    df_dict = dfc.concatenate_dataframes(df_dict)


    print(f"Finished creating dataframes.")
    
    tpc_det_key="detd_kHD_TPC_kWIBEth"
    offset=True

    planes = []
    for apa in ["APA1","APA2","APA3","APA4"]:
        for plane in [0,1,2]:
            planes.append((apa,plane))

    def make_adc_map_fig(apa,plane):
        df_tmp, index = dfc.select_record(df_dict[tpc_det_key])
        df_tmp= df_tmp.reset_index()
        fig = plot_WIBEth_adc_map(df_dict,tpc_det_key,apa,plane,
                                  offset=True,make_static=True,make_tp_overlay=False,
                                  orientation="vertical",colorscale='plasma',color_range=(-256,256))
        print(f"Figure for {apa} plane {plane} processed...")
        fig.update_layout(title=dict(text=f"Run {index.run}, Trigger {index.trigger}, {apa} Plane {plane}", font=dict(size=24) ) )
        fig.write_image(f"{output_dir}/EventDisplay_run{index.run}_trigger{index.trigger}_seq{index.sequence}_{apa}_plane{plane}.{imgtype}")
        return f"EventDisplay_run{index.run}_trigger{index.trigger}_seq{index.sequence}_{apa}_plane{plane}.{imgtype}"
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        future_p = {executor.submit(make_adc_map_fig,
                                    p[0],p[1]): p for p in planes }
        for future in concurrent.futures.as_completed(future_p):
            res = future.result()
            print(f"Completed image {res}")

    print("Done.")

if __name__ == '__main__':
    main()
