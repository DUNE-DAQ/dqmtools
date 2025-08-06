import sys

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *

try:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import numpy as np

    from PIL import Image
    from matplotlib.colors import Normalize
    from matplotlib import cm

except ModuleNotFoundError as err:
    print(err)
    print("\n\n")
    print("Missing module is likely not part of standard dunedaq releases.")
    print("\n")
    print("Please install the missing module and try again.")
    sys.exit(1)
except:
    raise

from .plot_utils import *

from .common_plots import *
from .tpc_plots import *

def plot_WIBEth_pulser_by_channel(df_dict,det_name,run=None,trigger=None,seq=None,jpeg_base=None):

    if f"detd_k{det_name}_kWIBEth" not in df_dict.keys():
        print(f"Can not make plots for detd_k{det_name}_kWIBEth, no DATA found")
        return
    
    df_tmp, index = dfc.select_record(df_dict[f"detd_k{det_name}_kWIBEth"],run,trigger,seq)
    df_tmp= df_tmp.reset_index()
    
    trigger_time = get_CERN_timestamp(df_dict,index);
    
    fig = px.scatter(df_tmp,x="channel",y=["adc_max","adc_min","adc_median"],
                     width=1000,height=600)
    fig.update_layout(xaxis_title='Channel',
                      yaxis_title="ADC value",
                      legend_title=None,
                      title=f'WIB Pulser Check: Run {index.run}, Record ({index.trigger,index.sequence}), Time {trigger_time}')
    if jpeg_base is not None:
        fig.write_image(f"{jpeg_base}_run{index.run}_trigger{index.trigger}_seq{index.sequence}.jpeg")
    return fig

def plot_WIBEth_adc_map(df_dict,tpc_det_key,ele,plane,
                        offset=True,offset_type="median",
                        make_static=False,make_tp_overlay=False,
                        orientation="vertical",colorscale='plasma',color_range=(-256,256),
                        run=None,trigger=None,seq=None):

    offset_var = f'adc_{offset_type}'
    
    tpc_wvfm_key = "detw"+tpc_det_key[4:]

    if tpc_det_key not in df_dict.keys():
        print(f"Can not make plots for {tpc_det_key}, no DATA found")
        return empty_plot()

    if tpc_wvfm_key not in df_dict.keys():
        print(f"Can not make plots for {tpc_wvfm_key}, no DATA found")
        return empty_plot()
    df_tmp = df_dict[tpc_wvfm_key]
    df_tmp = df_tmp.loc[(df_tmp["element"]==ele)&(df_tmp["plane"]==plane)]

    df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)
    if offset:
        df_tmp = df_tmp.merge(df_dict[tpc_det_key][offset_var],left_index=True,right_index=True)

    df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
    df_tmp = df_tmp.reset_index()
    df_tmp["timestamps_trg_sub"] = df_tmp.apply(lambda x: x.timestamps.astype(np.int64) - x.trigger_timestamp_dts,axis=1)
    if offset:
        df_tmp["adcs"] = df_tmp["adcs"]-df_tmp[offset_var]
    df_tmp = df_tmp.sort_values("channel")

    if orientation=="horizontal":
        xdata = df_tmp.iloc[0]["timestamps_trg_sub"]
        ydata = df_tmp["channel"].values
        zdata = np.vstack(df_tmp["adcs"].values)
        yaxis_title='Offline Channel'
        xaxis_title='DTS time ticks (16ns)'
    else:
        ydata = df_tmp.iloc[0]["timestamps_trg_sub"]
        xdata = df_tmp["channel"].values
        zdata = np.vstack(df_tmp["adcs"].values).T
        xaxis_title='Offline Channel'
        yaxis_title='DTS time ticks (16ns)'

    zmin, zmax = color_range

    if make_static:

        xmin = np.min(xdata)
        xmax = np.max(xdata)
        ymin = np.min(ydata)
        ymax = np.max(ydata)

        zdata = np.flip(zdata,0)
        if zmin is None:
            zmin = np.min(zdata)
        if zmax is None:
            zmax = np.max(zdata)

        col_norm = Normalize(vmin=zmin, vmax=zmax)
        scalarMap  = cm.ScalarMappable(norm=col_norm, cmap=colorscale )
        seg_colors = scalarMap.to_rgba(zdata)
        img = Image.fromarray(np.uint8(seg_colors*255))

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=[xmin, xmax],
                y=[ymin, ymax],
                mode="markers",
                marker={"color":[zmin, zmax],
                        "colorscale":colorscale,
                        "showscale":True,
                        "colorbar":{
                            "title":{
                                #"text": "Counts",
                                "side": "right"
                            }
                        },
                        "opacity": 0
                        },
                showlegend=False
            )
        )

        fig.update_layout(
            images=[go.layout.Image(
                x=xmin,
                sizex=xmax-xmin,
                y=ymax,
                sizey=ymax-ymin,
                xref="x",
                yref="y",
                opacity=1.0,
                layer="below",
                sizing="stretch",
                source=img)]
        )
        fig.update_layout(
            xaxis=dict(showgrid=False, zeroline=False, range=[xmin, xmax]),
            yaxis=dict(showgrid=False, zeroline=False, range=[ymin, ymax]))

    else:
        fig=px.imshow(zdata,
                      aspect="auto", origin='lower',
                      x=list(xdata),y=list(ydata),
                      color_continuous_scale=colorscale,
                      zmin=zmin,zmax=zmax)

    fig.update_layout(
        yaxis_title=yaxis_title,
        xaxis_title=xaxis_title,
    )

    #if we aren't doing the TP overlay, we are done
    if not make_tp_overlay:
        return fig

    #if we are, let's grab the TPs
    df_tmp = df_dict["trgd_kDAQ_kTriggerPrimitive"]

    #ugly hack while we can't better decide which src ids to ignore for duplicated TPs
    # n_elements = len(np.unique(df_tmp["element"]))
    # idx_names = df_tmp.index.names
    # df_tmp = df_tmp.reset_index()
    # df_tmp = df_tmp.loc[(df_tmp["src_id"]<n_elements*3)]
    # df_tmp = df_tmp.set_index(idx_names)

    df_tmp = df_tmp.loc[(df_tmp["element"]==ele)&(df_tmp["plane"]==plane)]
    df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)

    if len(df_tmp)==0:
        return fig
    
    df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
    df_tmp = df_tmp.reset_index()

    df_tmp["time_start_trg_sub"] = df_tmp.apply(lambda x: x.time_start - x.trigger_timestamp_dts,axis=1)
    df_tmp["time_peak_trg_sub"] = df_tmp.apply(lambda x: x.time_start_trg_sub + + x.samples_to_peak * 16, axis=1)
    # df_tmp["time_peak_trg_sub"] = df_tmp.apply(lambda x: x.time_start + x.samples_to_peak * 16 - x.trigger_timestamp_dts,axis=1)

    df_tmp["marker_string"] = df_tmp.apply(lambda x: f"start: {x.time_start_trg_sub}<br>peak: {x.time_peak_trg_sub}<br>end: {x.time_start_trg_sub+x.samples_over_threshold}<br>tot: {x.samples_over_threshold}<br>channel: {x.channel}<br>sum adc: {x.adc_integral}<br>peak adc: {x.adc_peak}",axis=1)

    if orientation=="horizontal":
        xdata = df_tmp["time_peak_trg_sub"]
        ydata = df_tmp["channel"]
    else:
        ydata = df_tmp["time_peak_trg_sub"]
        xdata = df_tmp["channel"]

    tp_fig=go.Scattergl(
        x=xdata,
        y=ydata,
        mode='markers', name="Trigger Primitives",
        marker=dict(size=df_tmp["adc_integral"],
                    sizemode='area',
                    sizeref=2.*max(df_tmp['adc_integral'])/(12**2),sizemin=3,
                    color=df_tmp['adc_peak'], #set color equal to a variable
                    colorscale="delta", # one of plotly colorscales
                    cmin = 0,
                    cmax = zmax,
                    showscale=True,colorbar=dict( x=1.2 ),
                    ),
        text=df_tmp["marker_string"],
    )
    fig.add_trace(tp_fig)
    fig.update_layout(legend=dict(
        yanchor="top",
        y=1.1,
        xanchor="right",
        x=1.35
    ))

    return fig


def plot_WIBEth_waveform(df_dict,tpc_det_key,channel,
                         offset=False,offset_type='median',
                         overlay_tps=False,
                         run=None,trigger=None,seq=None):

    offset_var = f'adc_{offset_type}'
    
    tpc_wvfm_key = "detw"+tpc_det_key[4:]

    if tpc_det_key not in df_dict.keys():
        print(f"Can not make plots for {tpc_det_key}, no DATA found")
        return empty_plot()

    if tpc_wvfm_key not in df_dict.keys():
        print(f"Can not make plots for {tpc_wvfm_key}, no DATA found")
        return empty_plot()

    df_tmp = df_dict[tpc_wvfm_key]
    idx_names = df_tmp.index.names
    df_tmp = df_tmp.reset_index()
    df_tmp = df_tmp.loc[df_tmp["channel"]==channel]
    df_tmp = df_tmp.set_index(idx_names)

    df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)
    if offset:
        df_tmp = df_tmp.merge(df_dict[tpc_det_key][offset_var],left_index=True,right_index=True)

    df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
    df_tmp = df_tmp.reset_index()

    df_tmp["timestamps_trg_sub"] = df_tmp.apply(lambda x: x.timestamps.astype(np.int64) - x.trigger_timestamp_dts,axis=1)
    yaxis_title = "ADC counts"
    if offset:
        df_tmp["adcs"] = df_tmp["adcs"]-df_tmp[offset_var]
        yaxis_title = yaxis_title + " (pedestal subtracted)"

    print(df_tmp)
    print(df_tmp["timestamps"].values[0])
    print(df_tmp["adcs"].values[0])
    fig = go.Figure(data=go.Scatter(x=df_tmp["timestamps_trg_sub"].values[0], y=df_tmp["adcs"].values[0]))


    fig.update_layout(xaxis_title='DTS Timestmap (16ns) relative to trigger',
                      yaxis_title=yaxis_title,
                      title=f"Waveform for channel {channel}")

    #if we're not overlaying TPs, just leave
    if not overlay_tps:
        return fig

    #if we are, let's grab the TPs

    if "trgd_kDAQ_kTriggerPrimitive" not in df_dict:
        return fig
            
    df_tmp = df_dict["trgd_kDAQ_kTriggerPrimitive"]

    #ugly hack while we can't better decide which src ids to ignore for duplicated TPs
    n_elements = len(np.unique(df_tmp["element"]))
    idx_names = df_tmp.index.names
    df_tmp = df_tmp.reset_index()
    df_tmp = df_tmp.loc[(df_tmp["src_id"]<n_elements*3)]
    df_tmp = df_tmp.set_index(idx_names)

    idx_names = df_tmp.index.names
    df_tmp = df_tmp.reset_index()
    df_tmp = df_tmp.loc[df_tmp["channel"]==channel]
    df_tmp = df_tmp.set_index(idx_names)

    df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)

    if len(df_tmp)==0:
        return fig
    
    df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
    df_tmp = df_tmp.reset_index()
    df_tmp["time_peak_trg_sub"] = df_tmp.apply(lambda x: x.time_peak - x.trigger_timestamp_dts,axis=1)
    df_tmp["time_start_trg_sub"] = df_tmp.apply(lambda x: x.time_start - x.trigger_timestamp_dts,axis=1)
    df_tmp["time_end_trg_sub"] = df_tmp.apply(lambda x: x.time_start_trg_sub + x.samples_over_threshold,axis=1)

    for index, tp in df_tmp.iterrows():
        fig.add_vrect(tp['time_start_trg_sub'], tp['time_end_trg_sub'], line_width=0, fillcolor="red", opacity=0.2)
        fig.add_vline(x=tp["time_peak_trg_sub"], line_width=1, line_dash="dash", line_color="red")

    return fig
