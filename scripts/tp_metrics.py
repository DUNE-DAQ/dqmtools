import hdf5libs
import dqmtools.dataframe_creator as dfc
import os
import plotly.io as pio
import matplotlib.pyplot as plt
import matplotlib.colors as mcol
from pypdf import PdfWriter
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import concurrent.futures
from plotly.subplots import make_subplots
import click

properties = ['Trigger', 'Sequence', 'Src ID', 'Time Start', 'Samples to Peak',
              'Samples over Threshold', 'Channels', 'Plane', 'Element', 'ADC Integral', 'ADC Peak', 'Detector ID', 'Flag', 'ID ta']
tp_prop = ['time_start', 'samples_to_peak', 'samples_over_threshold', 'adc_integral', 'adc_peak']

def tp_metrics(df_tp):
    elements = np.unique(df_tp['element'].to_numpy())
    planes = np.unique(df_tp['plane'].to_numpy())
    figs = {}

    def tp_rate_channel(df_tp):
        for pl in planes:
            fig = go.Figure()

            for ele in elements:
                df = df_tp[(df_tp['element'] == ele) & (df_tp['plane'] == pl)]

                if df.empty:
                    continue

                ch = df['channel'].to_numpy()
                ch = ch - np.min(ch)
                if len(ch) < 2:
                    continue

                ch_id = np.arange(np.min(ch), np.max(ch) + 1)
                counts, _ = np.histogram(ch, bins=ch_id)

                fig.add_trace(go.Scatter(
                    x=ch_id[:-1],
                    y=counts,
                    mode='markers',
                    marker=dict(size=5),
                    name=f'CRP {ele}'
                ))

            fig.update_layout(
                width=1500,
                height=600,
                title=f'TP Count per channel: Plane {pl}',
                xaxis_title='Channel index',
                yaxis_title='TP counts',
                template='plotly_white',
            )

            figs[f"TP_channel_plane_{pl}"] = fig

    def tp_count_planes(df_tp):
        fig = make_subplots(rows=1, cols=2, subplot_titles=["U plane", "V plane"], horizontal_spacing=0.1)
        ind_plane = [0, 1]
        colors = ['green', 'blue']

        for i, pl in enumerate(ind_plane):
            for j, ele in enumerate(elements):
                col_num = []
                ind_num = []

                for trg in range(1, 40):
                    df = df_tp[df_tp['trigger'] == trg]

                    col_tp = df[(df.plane == 2) & (df.element == ele)]
                    ind_tp = df[(df.plane == pl) & (df.element == ele)]

                    col_num.append(len(col_tp))
                    ind_num.append(len(ind_tp))

                fig.add_trace(
                    go.Scatter(
                        x=col_num,
                        y=ind_num,
                        mode='markers',
                        marker=dict(size=10, color=colors[j]),
                        opacity=0.8,
                        name=f'CRP {ele}',
                        showlegend=(i == 0)  # Show legend only once per element
                    ),
                    row=1,
                    col=i+1
                )

        # Add manual x-axis title centered under both subplots
        fig.add_annotation(
            text="Collection TP Count",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.5,
            y=-0.12,
            font=dict(size=16),
        )

        fig.update_layout(
            width=1800,
            height=800,
            title='Comparison of TP Counts between planes',
            yaxis_title='Induction TP Count',
            template='plotly_white',
            showlegend=True
        )

        figs[f"TP_counts_comparison_planes"] = fig

    tp_rate_channel(df_tp)
    tp_count_planes(df_tp)

    return figs

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

    extension = "png"
    figs = tp_metrics(df_tp)

    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        files = list(executor.map(lambda kv: save_plot(kv, extension, save_dir), figs.items()))
        
        final_pdf = images_to_pdf(files, "tp_metrics.pdf", save_dir)
        print(f"TP histogram PDF saved to {final_pdf}")

if __name__ == '__main__':
    main()