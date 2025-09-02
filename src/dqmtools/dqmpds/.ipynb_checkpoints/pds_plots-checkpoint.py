import os
import numpy as np
import pandas as pd

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .pds_utils import *
from tqdm import tqdm

def baseline_rms_plot(df):
 
    if 'baseline' not in df.columns:
        df = df.filter(items=['endpoint', 'channel', 'waveforms']).reset_index()
        df = df.groupby(['endpoint', 'channel'])['waveforms'].mean().reset_index()
        df['baseline'] = df.apply(lambda x: calculate_baseline_rms('baseline', x['waveforms'], 50), axis=1)
        df['rms'] = df.apply(lambda x: calculate_baseline_rms('rms', x['waveforms'], 50), axis=1)
   
    fig_baseline = make_subplots()
    fig_rms      = make_subplots()

    endpoint_list = df['endpoint'].unique()    
    for edp in tqdm(endpoint_list, desc = 'Creating baseline and rms fig.'):
        selected_rows = df[(df['endpoint'] == edp)]
        trace_baseline = go.Scatter(mode='lines+markers',
                        x=selected_rows["channel"],
                        y=selected_rows["baseline"],
                        name=str(edp))

        trace_rms = go.Scatter(mode='lines+markers',
                        x=selected_rows["channel"],
                        y=selected_rows["rms"],
                        name=str(edp))

        fig_baseline.add_trace(trace_baseline)
        fig_rms.add_trace(trace_rms)

    fig_baseline.update_layout(xaxis_title='Channel',
                  yaxis_title="ADC counts",
                  legend_title="ID",
                  title=f'Baseline',
                  xaxis_title_font=dict(size=22), yaxis_title_font=dict(size=22), width=1000, height=600)

    fig_rms.update_layout(xaxis_title='Channel',
                  yaxis_title="ADC counts",
                  legend_title="ID",
                  title=f'RMS',
                  xaxis_title_font=dict(size=22), yaxis_title_font=dict(size=22), width=1000, height=600)

    return fig_baseline, fig_rms
    
def waveforms_plot(df):
    fig = make_subplots(rows=10, cols=16, shared_xaxes=True, shared_yaxes=False, 
                            subplot_titles=["APA 1", "", "", "", "APA 2", "", "", "", "APA 3", "", "", "", "APA 4"] + [""] * (10 * 16 - 4),
                            horizontal_spacing=0.012, vertical_spacing=0.03)
    fig.update_xaxes(title_text='Ticks', row=10, col=8)
    fig.update_yaxes(title_text='ADCs', col=1, row=5)
    
    for i in tqdm(range(len(df)), desc='Creating Waveform fig'):        
        waveform = df.loc[i, 'waveforms']
        col_pos  = df.loc[i, 'real_col_position'] + 1  
        row_pos  = df.loc[i, 'row_position'] + 1
        
        if col_pos <= 4:
            bg_color = 'green'
        elif col_pos <= 8:
            bg_color = 'red'
        elif col_pos <= 12:
            bg_color = 'blue'
        else:
            bg_color = 'black'

        trace = go.Scatter(y=waveform, mode='lines', line=dict(color=bg_color), showlegend=False)

        try: fig.add_trace(trace, row=int(row_pos), col=int(col_pos))
        except: print()#f'{df.loc[i]}: Position not found')

    fig.update_layout(
        showlegend=False,
        height=1500,
        width=3000,
        template="plotly_white"
        )

    return fig

def heat_map_plot(df):
    print('Creating trigger heat map')

    if 'trigger_count' not in df.columns:
        df['trigger_count']  = df.apply(lambda x: check_pulses(x['waveforms'], 50, 'self_trigger'), axis=1)
        df['endpoint'] = df.apply(lambda x: int(find_endpoint(x['src_id']))-100, axis=1)
        df = df.groupby(['endpoint', 'channel', 'row_position', 'col_position'])['trigger_count'].sum().reset_index()
        
    df_map = np.zeros([10, 16])
    df_map[df['row_position'], df['col_position']] = df['trigger_count']
    df_map = df_map[:, ::-1]
    df_map = pd.DataFrame(df_map, index = ['0', '1','2', '3', '4', '5', '6', '7', '8', '9'], columns=['15', '14', '13', '12', '11', '10', '9', '8', '7', '6', '5', '4', '3', '2', '1', '0'])
            
    fig = go.Figure(data=go.Heatmap(z=df_map,
                                    colorscale='RdYlGn',
                                    showscale=True))
                                    
    shapes = [
        dict(type="rect", x0=-0.5, y0=-0.5, x1=3.5, y1=9.5, line=dict(color="black", width=4), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=3.5, y0=-0.5, x1=7.5, y1=9.5, line=dict(color="black", width=4), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=7.5, y0=-0.5, x1=11.5, y1=9.5, line=dict(color="black", width=4), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=11.5, y0=-0.5, x1=15.5, y1=9.5, line=dict(color="black", width=4), fillcolor="rgba(0,0,0,0)")
    ]
    for shape in shapes:
        fig.add_shape(shape)
    
    annotations = [
        dict(x=2, y=-1, text="APA 1", showarrow=False, font=dict(size=12, color='black')),
        dict(x=6, y=-1, text="APA 2", showarrow=False, font=dict(size=12, color='black')),
        dict(x=10, y=-1, text="APA 3", showarrow=False, font=dict(size=12, color='black')),
        dict(x=14, y=-1, text="APA 4", showarrow=False, font=dict(size=12, color='black')),
        dict(x=8, y=-2, text=f"Trigger Heat Map", showarrow=False, font=dict(size=12, color='black'))
    ]
    for annotation in annotations:
        fig.add_annotation(annotation)
    
    fig.update_layout(
        width=1000,
        height=500,
        xaxis=dict(showgrid=False, zeroline=False, tickmode='array', tickvals=list(range(16))),
        yaxis=dict(showgrid=False, zeroline=False, tickmode='array', tickvals=list(range(10)), scaleanchor="x", scaleratio=1),
        margin=dict(t=30, b=30, l=30, r=30))
    
    return fig