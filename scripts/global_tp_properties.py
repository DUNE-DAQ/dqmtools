import hdf5libs
import dqmtools.dataframe_creator as dfc
import os
import plotly.io as pio
import click
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
from multiprocessing import Pool
import time 
import concurrent.futures

properties = ['Trigger', 'Sequence', 'Src ID', 'Time Start', 'Samples to Peak',
              'Samples over Threshold', 'Channels', 'Plane', 'Element', 'ADC Integral', 'ADC Peak', 'Detector ID', 'Flag', 'ID ta']
tp_prop = ['time_start', 'samples_to_peak', 'samples_over_threshold', 'adc_integral', 'adc_peak']

def binning(value, bins):
    bin_min = np.min(value)
    bin_max = np.max(value)
    bin_size = (bin_max - bin_min) / bins
    bin_info = [bin_min, bin_max, bin_size]
    return bin_info

def custom_prop(df_tp, prop):
        match prop:
            case 'time_start':
                value = df_tp['time_start'].values - np.min(df_tp['time_start'].values)
                bin_info = binning(value, bins=32)
            case 'samples_to_peak':
                value = df_tp[df_tp['samples_to_peak'] <= df_tp['samples_to_peak'].quantile(0.99)]['samples_to_peak'].values
                bin_info = binning(value, bins=32)
            case 'samples_over_threshold':
                value = df_tp[df_tp['samples_over_threshold'] <= df_tp['samples_over_threshold'].quantile(0.99)]['samples_over_threshold'].values
                bin_info = binning(value, bins=32)
            case 'adc_integral':
                value = df_tp[df_tp['adc_integral'] <= df_tp['adc_integral'].quantile(0.80)]['adc_integral'].values
                bin_info = binning(value, bins=100)
            case 'adc_peak':
                value = df_tp[df_tp['adc_peak'] <= df_tp['adc_peak'].quantile(0.80)]['adc_peak'].values
                bin_info = binning(value, bins=100)
        return value, bin_info

def save_plot(k_v_tuple, extension, save_dir):
    k, v = k_v_tuple
    filename = os.path.join(save_dir, f"{k}.{extension}")
    print(f"Saving {k} to {filename}")
    pio.write_image(v, filename, format=extension, scale=4)
    return filename

def clear_tmp_files(files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)
        else:
            print(f"{file} does not exist.")
    return

def images_to_pdf(figs, name = "tp_properties.pdf", save_dir=","):
    all_figs = [Image.open(pic) for pic in figs]
    ready_pics = [pic.convert('RGB') for pic in all_figs]
    output_path = os.path.join(save_dir, name)
    ready_pics[0].save(output_path, save_all=True, append_images=ready_pics[1:])
    clear_tmp_files(figs)
    return output_path


@click.command()
@click.argument('filenames', nargs=-1, type=click.Path(exists=True))
@click.option('--nrecords', '-n', default=1, help='How many Trigger Records to process (default: 1)')
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 10)')
@click.option('--save_dir', type=click.Path(exists=True), help='Path of the folder where the plots will be saved')

def main(filenames, nrecords, nworkers, save_dir):

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
    df_tp = df_dict['trgd_kDAQ_kTriggerPrimitive']
    df_tp = df_tp.reset_index()

    print("Structure of df_tp:", df_tp.head())

    #df_dict["trh"]['trigger_time_cern'] = pd.to_datetime(df_dict["trh"]['trigger_time'])
    #df_dict['trh']['trigger_time_cern'] = df_dict['trh']['trigger_time_cern'].dt.tz_convert('Europe/Zurich')
    #trigger_timestamp = df_dict["trh"]["trigger_time"].iloc[0]
    #trigger_timestamp_cern = df_dict["trh"]["trigger_time_cern"].iloc[0]

    figs = {}

    print("Plotting Global TP properties")

    for name, prop in zip(properties, df_tp.columns[1:]):

        if prop in tp_prop:
            value, bin_info = custom_prop(df_tp, prop)
            fig = go.Figure(data=[
                go.Histogram(
                    x=value,
                    xbins=dict(start=bin_info[0], end=bin_info[1], size=bin_info[2])
                )
            ])
        else:
            value = df_tp[prop].values
            fig = go.Figure(data=[
                go.Histogram(
                    x=value,
                    nbinsx=100
                )
            ])
            
        fig.update_layout(
            title=dict(text=f"Run {df_tp['run'].iloc[0]} {name}", font=dict(size=24)),
            xaxis_title=name,
            yaxis_title="Counts"
        )
        fig_name = f"TP_properties_run{df_tp['run'].iloc[0]}_{prop}"
        figs[fig_name] = fig
    
    extension = "png"  

# Save in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        files = list(executor.map(lambda kv: save_plot(kv, extension, save_dir), figs.items()))
    
    final_pdf = images_to_pdf(files, "tp_properties_output.pdf", save_dir)
    print(f"TP histogram PDF saved to {final_pdf}")

if __name__ == '__main__':
    main()