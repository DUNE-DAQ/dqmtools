#!/usr/bin/env python3

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *
from dqmtools.dqmtests import *
from dqmtools.dqmplots import *

import hdf5libs

import os
import plotly.io as pio
from pypdf import PdfWriter
import pandas as pd
import numpy as np
import concurrent.futures


import click

import plotly.graph_objects as go


def make_hit_thresholds_table(df_dict,thresholds,det_name,run=None,trigger=None,seq=None,jpeg_base=None):
    fig = go.Figure(data=[go.Table(
        header=dict(values=list(thresholds.columns)),
        cells=dict(values=np.round(thresholds.transpose().values, 2).tolist())
    )])

    _, index = dfc.select_record(df_dict[f"detd_k{det_name}_kWIBEth"],run,trigger,seq)
    trigger_time = get_CERN_timestamp(df_dict,index)

    fig.update_layout(title=dict(text=f"Run {index.run}, Trigger {index.trigger}, Time {trigger_time} (CERN)<br><sup> Initial hit thresholds to use </sup>", font=dict(size=20)))
    return fig

def make_bad_channels_table(df_dict, high_channels,threshold,det_name,run=None,trigger=None,seq=None,jpeg_base=None):
    fig = go.Figure(data=[go.Table(
        header=dict(values=list(high_channels.columns)),
        cells=dict(values=np.round(high_channels.transpose().values, 2).tolist())
    )])

    _, index = dfc.select_record(df_dict[f"detd_k{det_name}_kWIBEth"],run,trigger,seq)
    trigger_time = get_CERN_timestamp(df_dict,index)


    fig.update_layout(title=dict(text=f"Run {index.run}, Trigger {index.trigger}, Time {trigger_time} (CERN)<br><sup> channels with rms exceeding {threshold} </sup>", font=dict(size=20)))
    return fig

def make_evd(df_dict : dict, tpc_det_name : str, nworkers : int = 10):
    print(tpc_det_name)
    match tpc_det_name:
        case 'HD_TPC':
            tpc_det_key=f"detd_kHD_TPC_kWIBEth"
            elements = [1,2,3,4]
        case 'VD_BottomTPC':
            tpc_det_key=f"detd_kVD_BottomTPC_kWIBEth"
            elements = [4,5]
        case 'VD_Top_TPC':
            tpc_det_key=f"detd_kVD_Top_TPC_kTDEEth"
            elements = [2,3]
        case _:
            print('ERROR: det_id must be one of [HD_TPC, VD_BottomTPC, VD_Top_TPC].')
            return
    
    planes = [0, 1, 2]    
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
        fig_name = f"EventDisplay_run{index.run}_trigger{index.trigger}_seq{index.sequence}_Element{ele}_plane{plane}"
        return fig_name, fig

    figs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        future_p = {executor.submit(make_adc_map_fig,
                                    p[0],p[1]): p for p in myplanes }
        for future in concurrent.futures.as_completed(future_p):
            res = future.result()
            figs[res[0]] = res[1]
    return figs


@click.command()
@click.argument('filenames', nargs=-1, type=click.Path(exists=True))
@click.option('--nrecords', '-n', default=1, help='How many Trigger Records to process (default: 1)')
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 10)')
@click.option('--hd/--vd', default=True, help='Whether we are running HD (or VD) (default: "HD")')
@click.option('--warm/--cold', default=True, help='Whether we are running warm or cold (default: "warm")')
@click.option('--make-plots',is_flag=True, help='Option to make plots')
def main(filenames, nrecords, nworkers, hd, warm, make_plots):

    #setup our tests
    dqm_test_suite_wibs = DQMTestSuite("WIBEth Tests")
    dqm_test_suite_wibs.register_test(CheckAllExpectedFragmentsTest())
    dqm_test_suite_wibs.register_test(CheckNFrames_WIBEth())
    
    if(hd):
        tpc_det_name = "HD_TPC"
        tpc_det_id = 3
        tpc_rms_high_threshold=100
        tpc_rms_low_threshold=[15.]
        if not warm:
            tpc_rms_high_threshold=50
            tpc_rms_low_threshold=[4.,3.]
        pds_det_names = ["HD_PDS"]
        pds_det_ids = [ 2 ]
            
    else:
        tpc_det_name = "VD_BottomTPC"
        tpc_det_id = 10
        tpc_rms_high_threshold=100
        tpc_rms_low_threshold=[12.,20.]        
        if not warm:
            tpc_rms_high_threshold=50
            tpc_rms_low_threshold=[2.,3.]
        pds_det_names = ["VD_MembranePDS","VD_CathodePDS"]
        pds_det_ids = [ 8, 9 ]


    dqm_test_suite_wibs.register_test(CheckRMS_WIBEth(det_name=tpc_det_name,threshold=tpc_rms_high_threshold,verbose=True),
                                        name=f"CheckRMS_{tpc_det_name}_High")
    dqm_test_suite_wibs.register_test(CheckPedestal_WIBEth(det_name=tpc_det_name,verbose=True),
                                         name=f"CheckPedestal_{tpc_det_name}")
    dqm_test_suite_wibs.register_test(InitialHitThreshold_WIBEth(det_name=tpc_det_name,verbose=True),
                                        name=f"InitialHitThreshold_{tpc_det_name}_High")


    dqm_test_suite = DQMTestSuite("Waveform data")
    dqm_test_suite.register_test(dqm_test_suite_wibs)

    df_dict = {}
    n_processed_records = 0
    for filename in filenames:
        print(f'Processing file {filename}.')
        
        h5_file = hdf5libs.HDF5RawDataFile(filename)
        records = h5_file.get_all_record_ids()

        if nrecords==-1 or nrecords > (n_processed_records+len(records)):
            records_to_process = records
        else:
            records_to_process = records[:(nrecords-n_processed_records)]
        print(f'Will process {len(records_to_process)} of {len(records)} records.')

        for rid in records_to_process:
            print(f'Processing record {rid}')
            df_dict = dfc.process_record(h5_file,rid,df_dict,MAX_WORKERS=nworkers, wvfm_data_prescale=1)
            n_processed_records += 1

    df_dict = dfc.concatenate_dataframes(df_dict)

    res = dqm_test_suite.run_test(df_dict)

    outputs = dqm_test_suite_wibs.get_test_outputs()
    high_channels = outputs[f"CheckRMS_{tpc_det_name}_High"]
    initial_hit_thresholds = outputs[f"InitialHitThreshold_{tpc_det_name}_High"]


    print(dqm_test_suite.get_table(show_last_update=False))

    for test in dqm_test_suite.get_all_tests():
        if test.is_test_suite():
            print(f'Results for {test.get_name()}:')
            print(test.get_table(show_last_update=False))

    if(make_plots):
        figs = {}
        print("Plotting RMS")
        figs[f"pdune2_{tpc_det_name}_rms"] = plot_WIBEth_by_channel(df_dict,var="adc_rms",det_name=tpc_det_name)
        figs[f"pdune2_{tpc_det_name}_rms_fixrange"] = plot_WIBEth_by_channel(df_dict,var="adc_rms",det_name=tpc_det_name,yrange=[-1,60])
        print("Plotting ADC mean")
        figs[f"pdune2_{tpc_det_name}_mean"] = plot_WIBEth_by_channel(df_dict,var="adc_mean",det_name=tpc_det_name)
        print("Plotting table of high noise channels")
        figs[f"pdune2_{tpc_det_name}_high_channels"] = make_bad_channels_table(df_dict, high_channels, tpc_rms_high_threshold, tpc_det_name)
        print("Plotting table of Initial hit thresholds to set for the TPG")
        figs[f"pdune2_{tpc_det_name}_hit_thresholds"] = make_hit_thresholds_table(df_dict, initial_hit_thresholds, tpc_det_name)

        print("Plotting event display")
        evd_figs = make_evd(df_dict, tpc_det_name)
        figs = figs | evd_figs

        print("Saving figures")
        for k, v in figs.items():
            pio.write_image(v, k+".pdf", format="pdf")
        
        merger = PdfWriter()

        for pdf in figs:
            merger.append(pdf+".pdf")

        merger.write("raw_adc_analysis.pdf")
        merger.close()

        for pdf in figs:
            name = pdf+".pdf"
            if os.path.exists(name):
                os.remove(name)
            else:
                print(f"{name} does not exist.")

if __name__ == '__main__':
    main()
