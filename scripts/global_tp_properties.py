import hdf5libs
import dqmtools.dataframe_creator as dfc
import os
import plotly.io as pio
import click
#import pandas as pd
import numpy as np
import plotly.graph_objects as go
from PIL import Image
from plotly.subplots import make_subplots
import concurrent.futures

properties = ['Trigger', 'Sequence', 'Src ID', 'Time Start', 'Samples to Peak',
              'Samples over Threshold', 'Channels', 'Plane', 'Element', 'ADC Integral', 'ADC Peak', 'Detector ID', 'Flag', 'ID ta']
tp_prop = {'time_start':'Time Start',
        'samples_to_peak': 'Samples to Peak',
        'samples_over_threshold': 'Samples over Threshold',
        'adc_integral': 'ADC Integral',
        'adc_peak': 'ADC Peak'}

def classify_det_comp(elements):
    """Return detector classification based on element numbers."""
    elements = set(elements)

    hd = {1, 2, 3, 4}
    vd_top = {2, 3}
    vd_bottom = {4, 5}

    if elements.issubset(hd) and not (elements & vd_top or elements & vd_bottom):
        return "HD_TPC"
    elif elements.issubset(vd_top):
        return "VD_TopTPC"
    elif elements.issubset(vd_bottom):
        return "VD_BottomTPC"
    elif elements.issubset(vd_top | vd_bottom):
        return "VD_TopTPC + VD_BottomTPC"
    else:
        return "ERROR: det_id must be one of [HD_TPC, VD_BottomTPC, VD_TopTPC]."

def param_compare(df_tp, figs):

    tde = [2, 3]
    bde = [4, 5]
    planes = np.unique(df_tp['plane'].to_numpy())

    color_crp = {2: 'red', 3: 'blue', 4: 'green', 5: 'orange'}

    elements = df_tp['element'].unique()
    detector_str = classify_det_comp(elements)
    
    groups = []
    if df_tp['element'].isin(tde).any():
        groups.append(('TDE', tde))
    if df_tp['element'].isin(bde).any():
        groups.append(('BDE', bde))

    if not groups:
        print("No CRP data found in dataframe.")
        return {}

    for prop in tp_prop.items():
        # One figure per property
        fig = make_subplots(
            rows=len(groups), cols=len(planes),
            subplot_titles=[f"Plane {pl}" for _ in groups for pl in planes]
        )

        for j, (crp_name, crp) in enumerate(groups):   # rows
            shown_legends = set()
            for i, pl in enumerate(planes):            # cols
                for ele in crp:
                    df = df_tp[(df_tp['element'] == ele) & (df_tp['plane'] == pl)]
                    if len(df) < 5:
                        print(f"Less than 5 entries for {prop[1]} for Plane {pl} of CRP {ele}")
                        continue

                    value, bin_info = custom_prop(df, prop[0])
                    start, stop, step = bin_info
                    if step <= 0 or start >= stop:
                        bins = np.linspace(value.min(), value.max(), 100)
                    else:
                        bins = np.arange(start, stop + step, step)
                    counts, bins = np.histogram(value, bins=bins)

                    fig.add_trace(
                        go.Scatter(
                            x=np.repeat(bins, 2)[1:-1],
                            y=np.repeat(counts, 2),
                            mode='lines',
                            line=dict(width=1, color=color_crp.get(ele, 'black')),
                            name=f"CRP {ele}",
                            legendgroup=f"CRP{ele}",
                            showlegend=(ele not in shown_legends)
                        ),
                        row=j+1, col=i+1
                    )
                    shown_legends.add(ele)

        # Annotations
        fig.add_annotation(
            text=prop[1], showarrow=False,
            xref="paper", yref="paper",
            x=0.5, y=-0.15, font=dict(size=16)
        )
        fig.add_annotation(
            text="TP Count", showarrow=False,
            xref="paper", yref="paper",
            x=-0.10, y=0.5, font=dict(size=16),
            textangle=-90
        )

        fig.update_layout(
            width=1500,
            height=450*len(groups),
            title=dict(
                text=f"Run {df_tp['run'].iloc[0]}: {prop[1]} ({detector_str})",
                font=dict(size=20)
            ),
            template="plotly_white"
        )

        figs[f'Comparison of CRP elements for {prop[1]}'] = fig

    return figs

def binning(value, bins):
    bin_min = np.min(value)
    bin_max = np.max(value)
    bin_size = (bin_max - bin_min) / bins
    bin_info = [bin_min, bin_max, bin_size]
    return bin_info

def custom_prop(df_tp, prop):
    def roundup(value):
        return round(value/50) * 50
    match prop:
        case 'time_start':
            value = df_tp['time_start'].values - np.min(df_tp['time_start'].values)
            bin_info = binning(value, bins=16)
        case 'samples_to_peak':
            value = df_tp[df_tp['samples_to_peak'] <= df_tp['samples_to_peak'].quantile(0.995)]['samples_to_peak'].values
            bin_info = binning(value, bins=16)
        case 'samples_over_threshold':
            value = df_tp[df_tp['samples_over_threshold'] <= df_tp['samples_over_threshold'].quantile(0.995)]['samples_over_threshold'].values
            bin_info = binning(value, bins=16)
        case 'adc_integral':
            value = df_tp[df_tp['adc_integral'] <= roundup(df_tp['adc_integral'].quantile(0.995))]['adc_integral'].values
            bin_info = binning(value, bins=100)
        case 'adc_peak':
            value = df_tp[df_tp['adc_peak'] <= roundup(df_tp['adc_peak'].quantile(0.995))]['adc_peak'].values
            bin_info = binning(value, bins=50)
    return value, bin_info

def save_plot(k_v_tuple, extension, save_dir):
    k, v = k_v_tuple
    filename = os.path.join(save_dir, f"{k}.{extension}")
    print(f"Saving {k} to {filename}")
    pio.write_image(v, filename, format=extension, scale=4)
    return filename

def images_to_pdf(files, pdf_name, save_dir):
    ready_pics = [Image.open(f).convert("RGB") for f in files]
    if not pdf_name.lower().endswith(".pdf"):
        pdf_name = f"{pdf_name}.pdf"

    output_path = os.path.join(save_dir, pdf_name)

    ready_pics[0].save(output_path, save_all=True, append_images=ready_pics[1:])

    for f in files:
        if os.path.exists(f):
            os.remove(f)
        else:
            print(f"{f} does not exist.")

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

    if "trgd_kDAQ_kTriggerPrimitive" in df_dict:
        print("Constructing TP dataframe from TR")
        df_tp = df_dict['trgd_kDAQ_kTriggerPrimitive']
    elif "trgh_kDAQ_kTriggerPrimitive" in df_dict:
        print("Constructing TP dataframe from TPStream")
        df_tp = df_dict['trgh_kDAQ_kTriggerPrimitive']

    df_tp = df_tp.reset_index()

    print("Structure of df_tp:", df_tp.head())

    detectors = df_tp['element'].unique()
    detector_names = [classify_det_comp(detectors)]
    detector_str = ", ".join(sorted(set(detector_names)))

    figs = {}

    run = df_tp['run'].iloc[0]

    print("Plotting Global TP properties")

    for name, prop in zip(properties, df_tp.columns[1:]):

        if prop in tp_prop:
            value, bin_info = custom_prop(df_tp, prop)
            bins = np.arange(bin_info[0], bin_info[1] + bin_info[2], bin_info[2])
            counts, bins = np.histogram(value, bins=bins)

            hist = go.Scatter(
                x=np.repeat(bins, 2)[1:-1],   # repeat edges to form steps
                y=np.repeat(counts, 2),
                mode='lines',
                line=dict(color='red', width=1),
                name='Linear',
                yaxis='y1'
            )
            hist_log = go.Scatter(
                x=np.repeat(bins, 2)[1:-1],   # repeat edges to form steps
                y=np.repeat(counts, 2),
                mode='lines',
                line=dict(color='blue', width=1),
                name='Log',
                yaxis='y2'
            )

            fig = go.Figure(data=[hist, hist_log])

            fig.update_layout(
                title=dict(text=f"Run {df_tp['run'].iloc[0]} {name} ({detector_str})", font=dict(size=20)),
                xaxis_title=name,
                yaxis=dict(
                    title='Counts (Linear)',
                    side='left',
                    type='linear'
                ),
                yaxis2=dict(
                    title='Counts (Log)',
                    side='right',
                    overlaying='y',
                    type='log'
                ),
                barmode='overlay',
                template='plotly_white',
                legend=dict(x=0.7, y=0.95)
            )

        else:
            value = df_tp[prop].values
            counts, bins = np.histogram(value, bins=100)

            hist = go.Scatter(
                x = np.repeat(bins, 2)[1:-1],
                y = np.repeat(counts, 2),
                mode='lines',
                line=dict(color='red', width=1),
                name='Linear',
                yaxis='y1'
            )
            fig = go.Figure(data=[hist])

            fig.update_layout(
                title=dict(text=f"Run {df_tp['run'].iloc[0]} {name} ({detector_str})", font=dict(size=20)),
                xaxis_title=name,
                yaxis=dict(
                    title='Counts (Linear)',
                    side='left',
                    type='linear'
                ),
                yaxis2=dict(
                    title='Counts (Log)',
                    side='right',
                    overlaying='y',
                    type='log'
                ),
                barmode='overlay',
                template= 'plotly_white',
                legend=dict(x=0.7, y=0.95)
            )
            
        fig_name = f"TP_properties_run{df_tp['run'].iloc[0]}_{prop}"
        figs[fig_name] = fig

    extension = "png" 
    pdf_name = f'tp_properties_run_{run}'

    figs = param_compare(df_tp, figs) 

    # Save in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        files = list(executor.map(lambda kv: save_plot(kv, extension, save_dir), figs.items()))
    
    final_pdf = images_to_pdf(files, pdf_name, save_dir)
    print(f"TP histogram PDF saved to {final_pdf}")

if __name__ == '__main__':
    main()