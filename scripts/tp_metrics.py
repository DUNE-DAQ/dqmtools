import hdf5libs
import dqmtools.dataframe_creator as dfc
import os
import plotly.io as pio
import numpy.ma as ma
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import concurrent.futures
import click

def tp_metrics(df_tp):
    
    tde = [2, 3]
    bde = [4, 5]
    planes = np.unique(df_tp['plane'].to_numpy())
    ind_plane = [0, 1]
    elements = np.unique(df_tp['element'].to_numpy())

    figs = {}

    def tp_rate_channel(df_tp):
        for pl in planes:

            fig = make_subplots(rows=2, cols=1, subplot_titles=["TDE", "BDE"])

            for i, (name, crp) in enumerate([('TDE', tde), ('BDE', bde)]):

                for ele in crp:
                    df = df_tp[(df_tp['element'] == ele) & (df_tp['plane'] == pl)]

                    if df.empty:
                        print(f"No entries for Plane {pl} of CRP {ele}")
                        continue

                    ch = df['channel'].to_numpy()
                    ch = ch - np.min(ch)

                    if len(ch) < 1:
                        continue

                    ch_id = np.arange(np.min(ch), np.max(ch) + 1)
                    counts, _ = np.histogram(ch, bins=ch_id)

                    fig.add_trace(go.Scatter(
                        x=ch_id,
                        y=counts,
                        mode='markers',
                        marker=dict(size=5),
                        name=f'CRP {ele}'
                    ), row=i+1, col=1)

            fig.add_annotation(
                text="Channel index",
                showarrow=False,
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.15,
                font=dict(size=16),
                textangle=0
            )

            fig.add_annotation(
                text="TP Count",
                showarrow=False,
                xref="paper",
                yref="paper",
                x=-0.09,
                y=0.5,
                font=dict(size=16),
                textangle=-90
            )

            fig.update_layout(
                width=1500,
                height=600,
                title=dict(
                    text=f"Run {df_tp['run'].iloc[0]}: TP Count per channel (Plane {pl})",
                    font=dict(size=20)
                ))

            figs[f"TP_count_channel_{pl}"] = fig

    def tp_count_planes(df_tp):
        fig = make_subplots(rows=2, cols=2, 
            subplot_titles=["U plane - TDE", "V plane - TDE", "U plane - BDE", "V plane - BDE"],
            horizontal_spacing=0.1
        )

        # Get a large color palette
        colors = px.colors.qualitative.Dark24
        color_map = {}

        for i, pl in enumerate(ind_plane):
            for k, (name, crp) in enumerate([('TDE', tde), ('BDE', bde)]):
                
                for j, ele in enumerate(crp):

                    key = f"{name}_{ele}"   #Unique id for crp and if it is in tde or bde

                    if key not in color_map:
                        color_map[key] = colors[len(color_map) % len(colors)]

                    col_num = []
                    ind_num = []
                    trigger = np.unique(df_tp['trigger'].to_numpy())

                    for trg in trigger:
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
                            marker=dict(size=7, color=color_map[key]),
                            opacity=0.85,
                            name=f'CRP {ele}',  # make legend clear
                            showlegend=i==0
                        ),
                        row=k+1,
                        col=i+1
                    )

        fig.add_annotation(
            text="Collection TP Count",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.5,
            y=-0.15,
            font=dict(size=16),
            textangle=0
        )

        fig.add_annotation(
            text="Induction TP Count",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=-0.09,
            y=0.5,
            font=dict(size=16),
            textangle=-90
        )

        fig.update_layout(
            width=1800,
            height=800,
            title=dict(text=f"Run {df_tp['run'].iloc[0]}: TP Count Comparison between planes", font=dict(size=20)),
            showlegend=True
        )

        figs[f"TP_counts_comparison_planes"] = fig

    def adc_correlation(df_tp):
        
        bin_x = np.arange(0, 15000, 150)
        bin_y = np.arange(0, 15000, 150)
       
        for pl in ind_plane:

            fig = make_subplots(rows=2, cols=2, 
                                subplot_titles=[f"CRP {ele}" for ele in elements])
            for i, ele in enumerate(elements):

                all_valid_data = []
                col_adc = []
                ind_adc = []
                trigger = np.unique(df_tp['trigger'].to_numpy())

                # Accumulate data across all triggers
                for trg in trigger:
                    df = df_tp[df_tp['trigger'] == trg]
                    if df.empty:
                        print(f"No entries for Plane {pl} of CRP {ele}")
                        continue


                    col_tp = df[(df.plane == 2) & (df.element == ele)]
                    ind_tp = df[(df.plane == pl) & (df.element == ele)]

                    col_adc.extend(col_tp['adc_integral'].to_numpy())
                    ind_adc.extend(ind_tp['adc_integral'].to_numpy())

                # Convert to numpy arrays and ensure same length
                col_adc = np.array(col_adc)
                ind_adc = np.array(ind_adc)
                min_len = min(len(col_adc), len(ind_adc))
                col_adc = col_adc[:min_len]
                ind_adc = ind_adc[:min_len]

                if min_len == 0:
                    continue

                # 2D histogram and log transform
                H, xedges, yedges = np.histogram2d(col_adc, ind_adc, bins=[bin_x, bin_y])
                with np.errstate(divide='ignore'):
                    H_log = np.log10(H)
                H_masked = ma.masked_where(H == 0, H_log)
                z = H_masked.filled(np.nan)

                if H_masked.count() > 0:
                    all_valid_data.append(H_masked.compressed())

                    row = i // 2 + 1
                    col = i % 2 + 1

                    fig.add_trace(go.Heatmap(
                        z=z.T,
                        x=xedges,
                        y=yedges,
                        colorscale='Viridis',
                        coloraxis='coloraxis',
                        hoverongaps=False
                    ),
                    row=row,
                    col=col
                    )

                if all_valid_data:
                    all_valid_data = np.concatenate(all_valid_data)
                    global_zmin = all_valid_data.min()
                    global_zmax = all_valid_data.max()
                else:
                    global_zmin = 0
                    global_zmax = 1


            fig.add_annotation(
                text="Collection ADC",
                showarrow=False,
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.15,
                font=dict(size=16),
                textangle=0
            )

            fig.add_annotation(
                text=f"Induction ADC (Plane {pl})",
                showarrow=False,
                xref="paper",
                yref="paper",
                x=-0.09,
                y=0.5,
                font=dict(size=16),
                textangle=-90
            )   

            fig.update_layout(
                coloraxis=dict(
                    colorscale='Viridis',
                    colorbar=dict(title='log₁₀(Density)'),
                    cmin=global_zmin,
                    cmax=global_zmax,
                ),
                width=900,
                height=600,
                title=dict(text=f"Run {df_tp['run'].iloc[0]}: ADC Correlation between planes", font=dict(size=20)),
                showlegend=False
            )

            figs[f"ADC_correlation_ind_planes_{pl}"] = fig


    tp_rate_channel(df_tp)
    tp_count_planes(df_tp)
    adc_correlation(df_tp)

    return figs

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
    df_tp = df_dict['trgd_kDAQ_kTriggerPrimitive']
    df_tp = df_tp.reset_index()

    print("Structure of df_tp:", df_tp.head())

    extension = "png"
    run = df_tp['run'].iloc[0]
    pdf_name = f'tp_metrics_run_{run}'
    figs = tp_metrics(df_tp)

    with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
        files = list(executor.map(lambda kv: save_plot(kv, extension, save_dir), figs.items()))
        
        final_pdf = images_to_pdf(files, pdf_name, save_dir)
        print(f"TP histogram PDF saved to {final_pdf}")

if __name__ == '__main__':
    main()