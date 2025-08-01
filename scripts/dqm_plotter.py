#!/usr/bin/env python3

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *
from dqmtools.dqmtests import *
from dqmtools.dqmplots import *

import hdf5libs

import concurrent.futures
import os

import click
@click.command()
@click.argument('input_data', type=click.Path(exists=True))
@click.argument('output_dir', type=click.Path(exists=True))
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 12)')
@click.option('--nskip', default=0, help='How many trigger records to skip at start of file')
@click.option('--nrecords', default=1, help='How man trigger records to plot')
@click.option('--imgtype', default='svg', help='Type of image to write')
@click.option('--element',default=None, help='specific element to plot')
@click.option('--plane',default=None, help='specific plane to plot')
@click.option('--det-id', default='VD_Bottom_TPC', help='detector id (HD_TPC, VD_Bottom_TPC, VD_Top_TPC)')

def main(input_data, output_dir, nworkers, nskip, nrecords, imgtype, element, plane, det_id):

    match det_id:
        case 'HD_TPC':
            tpc_det_key=f"detd_kHD_TPC_kWIBEth"
            default_elements = [1,2,3,4]
        case 'VD_Bottom_TPC':
            tpc_det_key=f"detd_kVD_BottomTPC_kWIBEth"
            default_elements = [5,6]
        case 'VD_Top_TPC':
            tpc_det_key=f"detd_kVD_TopTPC_kTDEEth"
            default_elements = [2,3]
        case _:
            print('ERROR: det_id must be one of [HD_TPC, VD_BottomTPC, VD_TopTPC].')
            return

    filename = input_data
    if(os.path.isdir(input_data)):
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
        
        df_dict = dfc.process_record(h5_file,rid,df_dict,MAX_WORKERS=nworkers,ana_data_prescale=1,wvfm_data_prescale=1)
        df_dict = dfc.concatenate_dataframes(df_dict)
        
        print(f"Finished creating dataframes.")

        pd.set_option('display.max_columns', None)
        print(df_dict["trh"])

        offset=True
        
        if plane is not None:
            planes = [ int(plane) ]
        else:
            planes = [0, 1, 2]
            
        if element is not None:
            elements = [ int(element) ]
        else:
            elements = default_elements

        myplanes = []
        for ele in elements:
            for plane in planes:
                myplanes.append((ele,plane))
        
        df_dict["trh"]['trigger_time_cern'] = pd.to_datetime(df_dict["trh"]['trigger_time'])
        df_dict['trh']['trigger_time_cern'] = df_dict['trh']['trigger_time_cern'].dt.tz_convert('Europe/Zurich')
        trigger_timestamp = df_dict["trh"]["trigger_time"].iloc[0]
        trigger_timestamp_cern = df_dict["trh"]["trigger_time_cern"].iloc[0]

        trigger_types_str = "("
        for trigtype in df_dict["trh"]["trigger_type_bits"].iloc[0]:
            trigger_types_str = trigger_types_str + trigtype.name[1:] + ","
        trigger_types_str=trigger_types_str[:-1]+")"
        
        if tpc_det_key not in df_dict.keys():
            print("No tpc det waveforms in file.")
            return None
        
        def make_adc_map_fig(ele,plane):
            df_tmp, index = dfc.select_record(df_dict[tpc_det_key])
            df_tmp= df_tmp.reset_index()
            if(len(df_tmp)==0):
                return "NO-DATA-FOUND"
            fig = plot_WIBEth_adc_map(df_dict,tpc_det_key,ele,plane,
                                      offset=True,make_static=True,make_tp_overlay=False,
                                      orientation="vertical",colorscale='plasma',color_range=(-256,256))
            print(f"Figure for {ele} plane {plane} processed...")
            fig.update_layout(title=dict(text=f"Run {index.run}, Trigger {index.trigger}, Element {ele} Plane {plane}<br><sup>Trigger Type {trigger_types_str}, {trigger_timestamp_cern} (CERN)</sup>", font=dict(size=24) ) )
            fig_name = f"EventDisplay_run{index.run}_trigger{index.trigger}_seq{index.sequence}_Element{ele}_plane{plane}.{imgtype}"
            fig.write_image(f"{output_dir}/{fig_name}", scale=3)
            return fig_name

        with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
            future_p = {executor.submit(make_adc_map_fig,
                                        p[0],p[1]): p for p in myplanes }
            for future in concurrent.futures.as_completed(future_p):
                res = future.result()
                print(f"Completed image {res}")

        record_count = record_count + 1
        print(f"Done with {record_count} records.")

if __name__ == '__main__':
    main()
