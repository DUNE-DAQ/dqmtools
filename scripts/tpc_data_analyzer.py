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
from PIL import Image


def make_hit_thresholds_table(df_dict,thresholds,det_name,run=None,trigger=None,seq=None,jpeg_base=None):
    fig = go.Figure(data=[go.Table(
        header=dict(values=list(thresholds.columns)),
        cells=dict(values=np.round(thresholds.transpose().values, 2).tolist())
    )])

    _, index = dfc.select_record(df_dict[f"detd_k{det_name}_kWIBEth"],run,trigger,seq)
    trigger_time = get_CERN_timestamp(df_dict,index)

    fig.update_layout(title=dict(text=f"Run {index.run}, Trigger {index.trigger},<br>Time {trigger_time} (CERN)<br><sup> Initial hit thresholds to use </sup>", font=dict(size=20)))
    return fig

def make_bad_channels_table(df_dict, high_channels,threshold,det_name,run=None,trigger=None,seq=None,jpeg_base=None):

    n=10
    list_df = [high_channels[i:i+n] for i in range(0,len(high_channels),n)]

    figs = []
    for df in list_df:
        fig = go.Figure(data=[go.Table(
            header=dict(values=list(df.columns)),
            cells=dict(values=np.round(df.transpose().values, 2).tolist())
        )])

        _, index = dfc.select_record(df_dict[f"detd_k{det_name}_kWIBEth"],run,trigger,seq)
        trigger_time = get_CERN_timestamp(df_dict,index)


        fig.update_layout(title=dict(text=f"Run {index.run}, Trigger {index.trigger},<br>Time {trigger_time} (CERN)<br><sup> channels with rms exceeding {threshold} </sup>", font=dict(size=20)))
        figs.append(fig)
    return figs

def make_evd(df_dict : dict, tpc_det_name : str, trigger : int, nworkers : int = 10, tp_overlay : bool = False):
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

    if tpc_det_key not in df_dict.keys():
        print("No tpc det waveforms in file.")
        return None
    
    def make_adc_map_fig(ele,plane):
        df_dict["trh"]['trigger_time_cern'] = pd.to_datetime(df_dict["trh"]['trigger_time'])
        df_dict['trh']['trigger_time_cern'] = df_dict['trh']['trigger_time_cern'].dt.tz_convert('Europe/Zurich')
        trigger_timestamp = df_dict["trh"]["trigger_time"].iloc[0]
        trigger_timestamp_cern = df_dict["trh"]["trigger_time_cern"].iloc[0]

        trigger_types_str = "("
        for trigtype in df_dict["trh"]["trigger_type_bits"].iloc[0]:
            trigger_types_str = trigger_types_str + trigtype.name[1:] + ","
        trigger_types_str=trigger_types_str[:-1]+")"

        df_tmp, index = dfc.select_record(df_dict[tpc_det_key], trigger = trigger)
        if(len(df_tmp)==0):
            return "NO-DATA-FOUND"
        fig = plot_WIBEth_adc_map(df_dict,tpc_det_key,ele,plane,
                                    offset=True,make_static=True,make_tp_overlay=tp_overlay,
                                    orientation="vertical",colorscale='plasma',color_range=(-256,256), trigger = trigger)
        print(f"Figure for trigger {trigger} element {ele} plane {plane} processed...")
        fig.update_layout(title=dict(text=f"Run {index.run}, Trigger {index.trigger}, Element {ele} Plane {plane}<br><sup>Trigger Type {trigger_types_str}, {trigger_timestamp_cern} (CERN)</sup>", font=dict(size=24) ) )
        fig_name = f"EventDisplay_run{index.run}_trigger{index.trigger}_seq{index.sequence}_Element{ele}_plane{plane}"
        if tp_overlay: fig_name = f"{fig_name}_tp"
        return fig_name, fig

    figs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        future_p = {executor.submit(make_adc_map_fig,
                                    p[0],p[1]): p for p in myplanes }
        for future in concurrent.futures.as_completed(future_p):
            res = future.result()
            figs[res[0]] = res[1]
    return figs

def clear_tmp_files(files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)
        else:
            print(f"{file} does not exist.")

    return

def pdf_to_pdf(figs,  name = "raw_adc_data_analysis.pdf"):
    merger = PdfWriter()
    for fig in figs:
        merger.append(fig)
    merger.write(name)
    merger.close()
    clear_tmp_files(figs)
    return name

def images_to_pdf(figs, name = "raw_adc_data_analysis.pdf"):
    all_figs = [Image.open(pic) for pic in figs]
    ready_pics = [pic.convert('RGB') for pic in all_figs]
    ready_pics[0].save(name, save_all=True, append_images=ready_pics[1:])
    clear_tmp_files(figs)
    return name


@click.command()
@click.argument('filenames', nargs=-1, type=click.Path(exists=True))
@click.option('--nrecords', '-n', default=1, help='How many Trigger Records to process (default: 1)')
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 10)')
@click.option('--hd/--vd', default=True, help='Whether we are running HD (or VD) (default: "HD")')
@click.option('--vector',is_flag=True, help='Images in a pdf vector graphics rather than raster')
@click.option('--rms-threshold', default=100, help = "Minimum rms value for a channel to be considered noisy (default:100)")
@click.option('--mean-rms-factor', default=5, help = "factor to multiply the mean rms by when determining the hit threshold (default:5)")
def main(filenames, nrecords, nworkers, hd, vector, rms_threshold, mean_rms_factor):

    if vector:
        extension = "pdf"
    else:
        extension = "png"

    #setup our tests
    dqm_test_suite_wibs = DQMTestSuite("WIBEth Tests")
    dqm_test_suite_wibs.register_test(CheckAllExpectedFragmentsTest())
    dqm_test_suite_wibs.register_test(CheckNFrames_WIBEth())
    
    if hd:
        tpc_det_name = "HD_TPC"            
    else:
        tpc_det_name = "VD_BottomTPC"


    dqm_test_suite_wibs.register_test(CheckRMS_WIBEth(det_name=tpc_det_name,threshold=rms_threshold,verbose=True),
                                        name=f"CheckRMS_{tpc_det_name}_High")
    dqm_test_suite_wibs.register_test(CheckPedestal_WIBEth(det_name=tpc_det_name,verbose=True),
                                         name=f"CheckPedestal_{tpc_det_name}")
    dqm_test_suite_wibs.register_test(InitialHitThreshold_WIBEth(det_name=tpc_det_name, multiplier=mean_rms_factor,verbose=True),
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
    time_meta = df_dict["trh"].iloc[0]["trigger_time"].strftime('%Y%m%d_%X').replace(":", "")

    dqm_test_suite.run_test(df_dict)

    outputs = dqm_test_suite_wibs.get_test_outputs()
    high_channels = outputs[f"CheckRMS_{tpc_det_name}_High"]
    initial_hit_thresholds = outputs[f"InitialHitThreshold_{tpc_det_name}_High"]


    print(dqm_test_suite.get_table(show_last_update=False))

    for test in dqm_test_suite.get_all_tests():
        if test.is_test_suite():
            print(f'Results for {test.get_name()}:')
            print(test.get_table(show_last_update=False))

    triggers = list(range(1, nrecords + 1, 1))

    figs = {}
    print("Plotting RMS")
    figs[f"pdune2_{tpc_det_name}_rms"] = plot_TPCData_by_channel(df_dict,var="adc_rms",det_keys=[f'detd_k{tpc_det_name}_kWIBEth'], trigger = triggers)
    figs[f"pdune2_{tpc_det_name}_rms_fixrange"] = plot_TPCData_by_channel(df_dict,var="adc_rms",det_keys=[f'detd_k{tpc_det_name}_kWIBEth'],yrange=[-1,60], trigger = triggers)
    print("Plotting ADC mean")
    figs[f"pdune2_{tpc_det_name}_mean"] = plot_TPCData_by_channel(df_dict,var="adc_mean",det_keys=[f'detd_k{tpc_det_name}_kWIBEth'], trigger = triggers)

    for t in triggers:
        print(f"Plotting event display for trigger: {t}")
        figs = figs | make_evd(df_dict, tpc_det_name, t, tp_overlay = False)
        if "trgd_kDAQ_kTriggerPrimitive" in df_dict:
            print(f"Plotting TP event display for trigger {t}")
            figs = figs | make_evd(df_dict, tpc_det_name, t, tp_overlay = True)

    print("Plotting table of Initial hit thresholds to set for the TPG")
    figs[f"pdune2_{tpc_det_name}_hit_thresholds"] = make_hit_thresholds_table(df_dict, initial_hit_thresholds, tpc_det_name, trigger = triggers)

    print("Plotting table of high noise channels")
    for i, f in enumerate(make_bad_channels_table(df_dict, high_channels, rms_threshold, tpc_det_name, trigger = triggers)):
        figs[f"pdune2_{tpc_det_name}_high_channels_{i}"] = f

    print("Saving figures")
    def save(num, name, fig):
        print(f"Saving {name}")
        filename = f"{name}.{extension}"
        pio.write_image(fig, filename, format=extension, scale=4)
        return num, filename

    files = [None] * len(figs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        future_p = {executor.submit(save, i, k, v) for i, (k, v) in enumerate(figs.items())}
        for future in concurrent.futures.as_completed(future_p):
            res = future.result()
            files[res[0]] = res[1]
            print(f"Completed image {res}")

    pdf_name = f'run{df_dict["trh"].index[0][0]}_raw_adc_data_analysis_{time_meta}.pdf'
    if vector:
        name = pdf_to_pdf(files, pdf_name)
    else:
        name = images_to_pdf(files, pdf_name)
    print(f"Report saved to {name}")

if __name__ == '__main__':
    main()
