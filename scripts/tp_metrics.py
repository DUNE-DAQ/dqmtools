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

def classify_det_comp(elements):
    """Return detector classification based on element numbers."""
    elements = set(elements)
    hd, vd_top, vd_bottom = {1,2,3,4}, {2,3}, {4,5}

    if elements <= hd and not elements & (vd_top | vd_bottom):
        return "HD_TPC"
    if elements <= vd_top:
        return "VD_TopTPC"
    if elements <= vd_bottom:
        return "VD_BottomTPC"
    if elements <= (vd_top | vd_bottom):
        return "VD_TopTPC + VD_BottomTPC"
    
    return "ERROR: det_id must be one of [HD_TPC, VD_BottomTPC, VD_TopTPC]."


def tp_metrics(df_tp):
    """Compute TP metrics and return fig data."""
    planes = np.unique(df_tp['plane'].to_numpy())
    elements = set(np.unique(df_tp['element'].to_numpy()))
    top_tpc, bottom_tpc = {2,3}, {4,5}

    # Determine detector groups present
    groups = {}
    if elements & top_tpc: groups['Top TPC'] = top_tpc
    if elements & bottom_tpc: groups['Bottom TPC'] = bottom_tpc

    element_to_det = {ele: classify_det_comp([ele]) for ele in elements}
    figs = {}
    triggers = np.unique(df_tp['trigger'].to_numpy())

    # --- TP rate per channel ---
    def tp_rate_channel(df):
        for pl in planes:
            fig = make_subplots(
                rows=len(groups), cols=1,
                subplot_titles=list(groups.keys())
            )
            for row_idx, (name, grp) in enumerate(groups.items()):
                shown_legends = set()
                for ele in grp:
                    df_ele = df[(df['element']==ele) & (df['plane']==pl)]
                    if df_ele.empty:
                        print(f"No TPs for CRP {ele} - Plane {pl}")
                        continue

                    ch = df_ele['channel'].to_numpy() - np.min(df_ele['channel'].to_numpy())
                    ch_id = np.arange(np.min(ch), np.max(ch)+1)
                    counts, _ = np.histogram(ch, bins=ch_id)

                    fig.add_trace(go.Scatter(
                        x=ch_id, y=counts, mode='markers', marker=dict(size=5),
                        name=f"{name} CRP {ele}", legendgroup=f"CRP {ele}",
                        showlegend=ele not in shown_legends
                    ), row=row_idx+1, col=1)
                    shown_legends.add(ele)

            fig.add_annotation(
                text="Channel index", showarrow=False, xref="paper", yref="paper",
                x=0.5, y=-0.15, font=dict(size=16), textangle=0)

            fig.add_annotation(
                text="TP Count", showarrow=False, xref="paper", yref="paper",
                x=-0.1, y=0.5, font=dict(size=16), textangle=-90)

            fig.update_layout(
                width=1500, height=300*len(groups),
                title=dict(text=f"Run {df['run'].iloc[0]}: TP Count per channel (Plane {pl})", font=dict(size=20))
            )
            figs[f"TP_count_channel_plane{pl}"] = fig

    # --- TP count comparison between planes ---
    def tp_count_planes(df):
        valid_groups = [g for g in groups if df['element'].isin(groups[g]).any()]
        subplot_titles = [f"{['U','V'][pl]} plane - {name}" 
                          for pl in [0,1] for name in valid_groups]
        fig = make_subplots(rows=2, cols=len(valid_groups), subplot_titles=subplot_titles)
        has_data = False
        colors, color_map = px.colors.qualitative.Dark24, {}

        for i, pl in enumerate([0,1]):
            for j, group_name in enumerate(valid_groups):
                for ele in groups[group_name]:
                    key = f"{element_to_det.get(ele,'Unknown')}_{ele}"
                    color_map.setdefault(key, colors[len(color_map) % len(colors)])

                    col_num, ind_num = [], []
                    for trg in triggers:
                        df_trg = df[df['trigger']==trg]
                        col_tp = df_trg[(df_trg.plane==2) & (df_trg.element==ele)]
                        ind_tp = df_trg[(df_trg.plane==pl) & (df_trg.element==ele)]
                        col_num.append(len(col_tp)); ind_num.append(len(ind_tp))

                    if sum(col_num)+sum(ind_num)==0:
                        continue
                    
                    fig.add_trace(go.Scatter(
                        x=col_num, y=ind_num, mode='markers', marker=dict(size=10, color=color_map[key]),
                        opacity=0.85, name=f'CRP {ele}', showlegend=i==0
                    ), row=i+1, col=j+1)
                    has_data = True

        if has_data:
            fig.add_annotation(
                text="Collection TP Count", showarrow=False, xref="paper", yref="paper",
                x=0.5, y=-0.15, font=dict(size=16), textangle=0)

            fig.add_annotation(
                text="Induction TP Count", showarrow=False, xref="paper", yref="paper",
                x=-0.095, y=0.5, font=dict(size=16), textangle=-90)
            
            fig.update_layout(width=1800, height=800,
                              title=dict(text=f"Run {df['run'].iloc[0]}: TP Count Comparison by Plane", font=dict(size=20)),
                              showlegend=True)
            figs["TP_counts_comparison_planes"] = fig

    # --- ADC correlation between planes ---
    def adc_correlation(df):
        bins = np.arange(0,15000,150)
        for pl in [0,1]:
            fig = make_subplots(rows=2, cols=2, subplot_titles=[f"CRP {ele}" for ele in elements])
            fig_has_data = False

            for i, ele in enumerate(elements):
                col_adc, ind_adc = [], []
                for trg in triggers:
                    df_trg = df[df['trigger']==trg]
                    col_tp = df_trg[(df_trg.plane==2) & (df_trg.element==ele)]
                    ind_tp = df_trg[(df_trg.plane==pl) & (df_trg.element==ele)]
                    col_adc.extend(col_tp['adc_integral'].to_numpy())
                    ind_adc.extend(ind_tp['adc_integral'].to_numpy())

                if not col_adc or not ind_adc: continue
                min_len = min(len(col_adc), len(ind_adc))
                col_adc, ind_adc = np.array(col_adc[:min_len]), np.array(ind_adc[:min_len])
                H, xedges, yedges = np.histogram2d(col_adc, ind_adc, bins=[bins, bins])
                H_log = np.log10(H, out=np.zeros_like(H), where=H>0)
                z = np.where(H>0, H_log, np.nan)

                fig.add_trace(go.Heatmap(z=z.T, x=xedges, y=yedges, colorscale='Viridis', coloraxis='coloraxis'), 
                              row=i//2+1, col=i%2+1)
                fig_has_data = True

            if fig_has_data:

                fig.add_annotation(
                    text="Collection ADC", showarrow=False, xref="paper", yref="paper",
                    x=0.5, y=-0.15, font=dict(size=16), textangle=0)

                fig.add_annotation(
                    text=f"Induction ADC (Plane {pl})", showarrow=False, xref="paper", yref="paper",
                    x=-0.09, y=0.5, font=dict(size=16), textangle=-90)
                   
                fig.update_layout(
                    coloraxis=dict(colorscale='Viridis', colorbar=dict(title='log₁₀(Density)')),
                    width=900, height=600,
                    title=dict(text=f"Run {df['run'].iloc[0]}: ADC Correlation between planes (Plane {pl})", font=dict(size=20)),
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

    if "trgd_kDAQ_kTriggerPrimitive" in df_dict:
        print("Constructing TP dataframe from TR")
        df_tp = df_dict['trgd_kDAQ_kTriggerPrimitive']
    elif "trgh_kDAQ_kTriggerPrimitive" in df_dict:
        print("Constructing TP dataframe from TPStream")
        df_tp = df_dict['trgh_kDAQ_kTriggerPrimitive']

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