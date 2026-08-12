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

def get_sampling_factor(det_id):
    if det_id==3 or det_id==10:
        return 32
    if det_id==11:
        return 31.25
    else:
        return 1

def plot_TPCData_by_channel(df_dict,var,det_keys,
                            run=None,trigger=None,seq=None,
                            tpc_chmap=None,
                            facet_by_plane=True,
                            title="PLOT_TITLE_DEFAULT",
                            ylabel=None,yrange=None,
                            width=None,height=None,
                            jpeg_base=None):

    #check and filter out to only valid keys
    det_keys[:] = get_valid_keys(df_dict,det_keys)

    if not det_keys:
        print("No valid data keys found.")
        return None

    #get all our data
    df_all = []
    index = None
    for det_key in det_keys:
        df_tmp, index = dfc.select_record(df_dict[det_key],run,trigger,seq)
        df_tmp = df_tmp.reset_index()
        df_tmp = df_tmp[["channel",var,"plane","element"]]
        df_all.append(df_tmp)
    df_all = pd.concat(df_all,ignore_index=True)

    #get the label name
    if tpc_chmap is None:
        df_all["label"] = "Element " + df_all["element"].astype(str)
    else:
        df_all["label"] = df_all['channel'].map(tpc_chmap.get_element_name_from_offline_channel)
    if not facet_by_plane:
        df_all["label"] = df_all["label"] + ", Plane " + df_all["plane"].astype(str)

    trigger_time = get_CERN_timestamp(df_dict,index)
    facet_col = "plane" if facet_by_plane else None
    if ylabel is None: ylabel=var
    if title=="PLOT_TITLE_DEFAULT":
        title=f'Run {index.run}, Record {int(index.trigger),int(index.sequence)}, Time {trigger_time}'
    elif title is not None:
        title=f'{title}: Run {index.run}, Record ({int(index.trigger),int(index.sequence)}), Time {trigger_time}'



    fig = px.scatter(df_all,
                     x="channel",
                     y=var,
                     color="label",
                     facet_col=facet_col,
                     category_orders={"plane": sorted(df_all["plane"].unique())},
                     labels={"channel": "Channel", var: ylabel, "label":""},
                     title=title,
                     width=width,
                     height=height)

    if facet_by_plane:
        fig.for_each_annotation(lambda a: a.update(text=f"Plane {a.text.split('=')[-1]}"))

    if yrange is not None:
        fig.update_yaxes(range=yrange)

    if jpeg_base is not None:
        fig.write_image(f"{jpeg_base}_run{index.run}_trigger{index.trigger}_seq{index.sequence}.jpeg")

    return fig


def plot_TPC_adc_map(df_dict,det_keys,ele,plane,
                     offset=True,offset_type="median",
                     make_static=False,make_tp_overlay=False,make_ta_overlay=False,
                     orientation="vertical",colorscale='plasma',color_range=(-256,256),
                     run=None,trigger=None,seq=None):

    offset_var = f'adc_{offset_type}'
    element_id = int(ele[3]) #assuming APAX or CRPX

    #check and filter out to only valid keys
    det_keys[:] = get_valid_keys(df_dict,det_keys)

    if not det_keys:
        print("No valid data keys found.")
        return empty_plot()

    #get all our data
    df_all = []
    index=None
    for det_key in det_keys:
        df_tmp = df_dict[det_key]
        df_tmp = df_tmp.loc[(df_tmp["element"]==element_id)&(df_tmp["plane"]==plane)]

        if len(df_tmp)==0: continue

        df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)
        if offset:
            df_tmp = df_tmp.merge(df_dict["detd"+det_key[4:]][offset_var],left_index=True,right_index=True)

        df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
        df_tmp = df_tmp.reset_index()
        df_all.append(df_tmp)

    if len(df_all)==0: 
        print(f"No element {ele} (element_id={element_id}) found.")
        return empty_plot()

    df_tmp = pd.concat(df_all,ignore_index=True)

    df_tmp["timestamps_trg_sub"] = df_tmp.apply(lambda x: x.timestamps.astype(np.int64) - x.trigger_timestamp_dts,axis=1)
    if offset:
        df_tmp["adcs"] = df_tmp["adcs"]-df_tmp[offset_var]
    df_tmp = df_tmp.sort_values("channel")

    #fill in missing time values with np.nan
    all_time_ticks = sorted(set().union(*df_tmp["timestamps_trg_sub"]))
    common_time = np.array(all_time_ticks)

    def map_to_common_time(timestamps, adcs, common_time):
        time_to_adc = dict(zip(timestamps, adcs))
        return np.array([time_to_adc.get(t, np.nan) for t in common_time])

    df_tmp["adcs_full"] = df_tmp.apply(
        lambda row: map_to_common_time(row["timestamps_trg_sub"], row["adcs"], common_time),
        axis=1
    )

    #now fill in missing channels with np.nan
    expected_channels = np.arange(df_tmp["channel"].min(),df_tmp["channel"].max()+1)
    df_tmp_indexed = df_tmp.set_index("channel")
    df_reindexed = df_tmp_indexed.reindex(expected_channels)

    max_adc_len = df_tmp["adcs_full"].apply(len).max()
    df_reindexed["adcs_full"] = df_reindexed["adcs_full"].apply(
        lambda x: x if isinstance(x, np.ndarray) else np.full(max_adc_len, np.nan)
    )

    df_reindexed["channel"] = df_reindexed.index

    df_tmp = df_reindexed

    if orientation=="horizontal":
        xdata = df_tmp.iloc[0]["timestamps_trg_sub"]
        ydata = df_tmp["channel"].values
        zdata = np.vstack(df_tmp["adcs_full"].values)
        yaxis_title='Offline Channel'
        xaxis_title='DTS time ticks (16ns)'
    else:
        ydata = df_tmp.iloc[0]["timestamps_trg_sub"]
        xdata = df_tmp["channel"].values
        zdata = np.vstack(df_tmp["adcs_full"].values).T
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
            zmin = np.nanmin(zdata)
        if zmax is None:
            zmax = np.nanmax(zdata)

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

    #TP overlay
    if make_tp_overlay and "trgd_kDAQ_kTriggerPrimitive" in df_dict:

        df_tmp = df_dict["trgd_kDAQ_kTriggerPrimitive"]

        df_tmp = df_tmp.loc[(df_tmp["element"]==element_id)&(df_tmp["plane"]==plane)]
        df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)

        if len(df_tmp)!=0:

            df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
            df_tmp = df_tmp.reset_index()

            df_tmp["time_start_trg_sub"] = df_tmp.apply(lambda x: x.time_start - x.trigger_timestamp_dts,axis=1)
            df_tmp["time_peak_trg_sub"] = df_tmp["time_start_trg_sub"]+df_tmp["samples_to_peak"]*32
            df_tmp["time_end_trg_sub"] = df_tmp["time_start_trg_sub"]+(df_tmp["samples_over_threshold"]-1)*32

            df_tmp["marker_string"] = df_tmp.apply(lambda x: f"start: {x.time_start_trg_sub}<br>peak: {x.time_peak_trg_sub}<br>end: {x.time_end_trg_sub}<br>channel: {x.channel}<br>sum adc: {x.adc_integral}<br>peak adc: {x.adc_peak}",axis=1)

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
                            showscale=True,colorbar=dict( x=1.12 )
                            ),
                text=df_tmp["marker_string"],
            )

            fig.add_trace(tp_fig)

    #TA overlay
    if make_ta_overlay and "trgd_kDAQ_kTriggerActivity" in df_dict:

        df_ta = df_dict["trgd_kDAQ_kTriggerActivity"]

        df_ta = df_ta.loc[(df_ta["element"]==element_id)&(df_ta["plane"]==plane)]
        df_ta = df_ta.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)

        if len(df_ta)!=0:

            df_ta, index = dfc.select_record(df_ta,run,trigger,seq)
            df_ta = df_ta.reset_index()

            for col in ["time_start","time_end","time_peak"]:
                df_ta[col] = df_ta[col].astype(np.int64) - df_ta["trigger_timestamp_dts"]

            border_time = 16
            border_channel = 0.5

            for ta_idx, ta in df_ta.iterrows():

                text = (f"start: {ta.time_start}<br>peak: {ta.time_peak}<br>end: {ta.time_end}<br>"
                        f"ch_start: {ta.channel_start}<br>ch_peak: {ta.channel_peak}<br>ch_end: {ta.channel_end}<br>"
                        f"peak adc: {ta.adc_peak}<br>adc_integral: {ta.adc_integral}")

                time_points = [ta.time_start-border_time, ta.time_start-border_time,
                               ta.time_end+border_time, ta.time_end+border_time, ta.time_start-border_time]
                channel_points = [ta.channel_start-border_channel, ta.channel_end+border_channel,
                                  ta.channel_end+border_channel, ta.channel_start-border_channel, ta.channel_start-border_channel]

                if orientation=="horizontal":
                    xdata, ydata = time_points, channel_points
                else:
                    xdata, ydata = channel_points, time_points

                fig.add_trace(go.Scatter(
                    name=f"ta[{ta_idx}]",
                    text=text,
                    x=xdata, y=ydata,
                    fill="toself",
                    line=dict(color="RoyalBlue", width=2),
                    fillcolor="LightSkyBlue",
                    opacity=0.5,
                ))

    return fig

def prep_TPC_adc_map(df_dict, det_keys, ele, plane,
                     offset=True, offset_type="median",
                     orientation="vertical",
                     color_range=(-256, 256),
                     run=None, trigger=None, seq=None):

    offset_var = f'adc_{offset_type}'
    element_id = int(ele[3])

    det_keys[:] = get_valid_keys(df_dict, det_keys)
    if not det_keys:
        print("No valid data keys found.")
        return None

    df_all = []
    index = None
    for det_key in det_keys:
        df_tmp = df_dict[det_key]
        df_tmp = df_tmp.loc[(df_tmp["element"] == element_id) & (df_tmp["plane"] == plane)]
        if len(df_tmp) == 0:
            continue
        df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"], left_index=True, right_index=True)
        if offset:
            df_tmp = df_tmp.merge(df_dict["detd" + det_key[4:]][offset_var], left_index=True, right_index=True)
        df_tmp, index = dfc.select_record(df_tmp, run, trigger, seq)
        df_tmp = df_tmp.reset_index()
        df_all.append(df_tmp)

    if len(df_all) == 0:
        print(f"No element {ele} (element_id={element_id}) found.")
        return None

    df_tmp = pd.concat(df_all, ignore_index=True)
    df_tmp["timestamps_trg_sub"] = df_tmp.apply(lambda x: x.timestamps.astype(np.int64) - x.trigger_timestamp_dts, axis=1)
    if offset:
        df_tmp["adcs"] = df_tmp["adcs"] - df_tmp[offset_var]
    df_tmp = df_tmp.sort_values("channel")

    all_time_ticks = sorted(set().union(*df_tmp["timestamps_trg_sub"]))
    common_time = np.array(all_time_ticks)

    def map_to_common_time(timestamps, adcs, common_time):
        time_to_adc = dict(zip(timestamps, adcs))
        return np.array([time_to_adc.get(t, np.nan) for t in common_time])

    df_tmp["adcs_full"] = df_tmp.apply(
        lambda row: map_to_common_time(row["timestamps_trg_sub"], row["adcs"], common_time), axis=1
    )

    expected_channels = np.arange(df_tmp["channel"].min(), df_tmp["channel"].max() + 1)
    df_tmp_indexed = df_tmp.set_index("channel")
    df_reindexed = df_tmp_indexed.reindex(expected_channels)

    max_adc_len = df_tmp["adcs_full"].apply(len).max()
    df_reindexed["adcs_full"] = df_reindexed["adcs_full"].apply(
        lambda x: x if isinstance(x, np.ndarray) else np.full(max_adc_len, np.nan)
    )
    df_reindexed["channel"] = df_reindexed.index
    df_tmp = df_reindexed

    if orientation == "horizontal":
        xdata, ydata = df_tmp.iloc[0]["timestamps_trg_sub"], df_tmp["channel"].values
        zdata = np.vstack(df_tmp["adcs_full"].values)
    else:
        ydata, xdata = df_tmp.iloc[0]["timestamps_trg_sub"], df_tmp["channel"].values
        zdata = np.vstack(df_tmp["adcs_full"].values).T

    zmin, zmax = color_range
    return {
        'x': (xdata, np.min(xdata), np.max(xdata)),
        'y': (ydata, np.min(ydata), np.max(ydata)),
        'z': (zdata, zmin, zmax),
    }


def plot_TPC_adc_map_mpl(df_dict, det_keys, ele, plane,
                         offset=True, offset_type="median",
                         make_static=False, make_tp_overlay=False,
                         orientation="vertical", colorscale='plasma',
                         color_range=(-256, 256),
                         run=None, trigger=None, seq=None,
                         figsize=(12, 8), title=None):

    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    try:
        font_path = os.path.expandvars('$DQMTOOLS_SHARE/config/fonts/OpenSans-VariableFont_wdth,wght.ttf')
        custom_font = fm.FontProperties(fname=font_path)
    except Exception:
        custom_font = fm.FontProperties()

    plot_data = prep_TPC_adc_map(df_dict, det_keys, ele, plane,
                                 offset=offset, offset_type=offset_type,
                                 orientation=orientation, color_range=color_range,
                                 run=run, trigger=trigger, seq=seq)

    fig, ax = plt.subplots(1, 1, figsize=figsize)

    if plot_data is None:
        return fig

    xdata, xmin, xmax = plot_data['x']
    ydata, ymin, ymax = plot_data['y']
    zdata, zmin, zmax = plot_data['z']

    img = ax.imshow(zdata, cmap=colorscale, aspect='auto', vmin=zmin, vmax=zmax,
                    origin='lower', extent=[xmin - 0.5, xmax + 0.5, ymin - 8, ymax + 8])
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    cbar = fig.colorbar(img, cax=cax)

    ax.set_xlabel("Offline Channel", fontsize=18, fontproperties=custom_font)
    ax.set_ylabel("DTS time ticks (16ns)", fontsize=18, fontproperties=custom_font)

    for label in ax.get_xticklabels() + ax.get_yticklabels() + cbar.ax.get_yticklabels():
        label.set_fontsize(14)
        label.set_fontproperties(custom_font)

    if title:
        fig.suptitle(title, ha='left', x=0.1, size=20, fontproperties=custom_font)

    return fig


def plot_TPC_waveform(df_dict,det_keys,channel,
                      offset=False,offset_type='median',
                      make_tp_overlay=False,make_ta_overlay=False,
                      run=None,trigger=None,seq=None):

    offset_var = f'adc_{offset_type}'

    #check and filter out to only valid keys
    det_keys[:] = get_valid_keys(df_dict,det_keys)

    if not det_keys:
        print("No valid data keys found.")
        return empty_plot()

    #get all our data
    df_all = []
    index = None
    for det_key in det_keys:

        df_tmp = df_dict[det_key]
        idx_names = df_tmp.index.names
        df_tmp = df_tmp.reset_index()
        df_tmp = df_tmp.loc[df_tmp["channel"]==channel]
        df_tmp = df_tmp.set_index(idx_names)

        if len(df_tmp)==0: continue

        df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)
        if offset:
            df_tmp = df_tmp.merge(df_dict["detd"+det_key[4:]][offset_var],left_index=True,right_index=True)

        df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
        df_tmp = df_tmp.reset_index()
        df_all.append(df_tmp)

    df_all = pd.concat(df_all,ignore_index=True)

    df_all["timestamps_trg_sub"] = df_all.apply(lambda x: x.timestamps.astype(np.int64) - x.trigger_timestamp_dts,axis=1)
    yaxis_title = "ADC counts"
    if offset:
        df_all["adcs"] = df_all["adcs"]-df_all[offset_var]
        yaxis_title = yaxis_title + " (pedestal subtracted)"

    #print(df_tmp)
    #print(df_tmp["timestamps"].values[0])
    #print(df_tmp["adcs"].values[0])
    fig = go.Figure(data=go.Scatter(x=df_all["timestamps_trg_sub"].values[0], y=df_all["adcs"].values[0]))


    fig.update_layout(xaxis_title='DTS Timestamp (16ns) relative to trigger',
                      yaxis_title=yaxis_title,
                      title=f"Waveform for channel {channel}")

    #TP overlay
    if make_tp_overlay and "trgd_kDAQ_kTriggerPrimitive" in df_dict:

        df_tmp = df_dict["trgd_kDAQ_kTriggerPrimitive"]

        idx_names = df_tmp.index.names
        df_tmp = df_tmp.reset_index()
        df_tmp = df_tmp.loc[df_tmp["channel"]==channel]
        df_tmp = df_tmp.set_index(idx_names)

        df_tmp = df_tmp.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)

        if len(df_tmp)!=0:

            df_tmp, index = dfc.select_record(df_tmp,run,trigger,seq)
            df_tmp = df_tmp.reset_index()
            df_tmp["time_start_trg_sub"] = df_tmp.apply(lambda x: x.time_start - x.trigger_timestamp_dts,axis=1)
            df_tmp["time_peak_trg_sub"] = df_tmp["time_start_trg_sub"]+df_tmp["samples_to_peak"]*32
            df_tmp["time_end_trg_sub"] = df_tmp["time_start_trg_sub"]+(df_tmp["samples_over_threshold"]-1)*32

            for tp_idx, tp in df_tmp.iterrows():
                fig.add_vrect(tp['time_start_trg_sub'], tp['time_end_trg_sub'], line_width=0, fillcolor="red", opacity=0.2)
                fig.add_vline(x=tp["time_peak_trg_sub"], line_width=1, line_dash="dash", line_color="red")

    #TA overlay
    if make_ta_overlay and "trgd_kDAQ_kTriggerActivity" in df_dict:

        df_ta = df_dict["trgd_kDAQ_kTriggerActivity"]

        idx_names = df_ta.index.names
        df_ta = df_ta.reset_index()
        df_ta = df_ta.loc[(df_ta["channel_start"]<=channel)&(df_ta["channel_end"]>=channel)]
        df_ta = df_ta.set_index(idx_names)

        df_ta = df_ta.merge(df_dict["frh"]["trigger_timestamp_dts"],left_index=True,right_index=True)

        if len(df_ta)!=0:

            df_ta, index = dfc.select_record(df_ta,run,trigger,seq)
            df_ta = df_ta.reset_index()

            for col in ["time_start","time_end","time_peak"]:
                df_ta[col] = df_ta[col].astype(np.int64) - df_ta["trigger_timestamp_dts"]

            for ta_idx, ta in df_ta.iterrows():
                fig.add_vrect(ta['time_start'], ta['time_end'], line_width=0, fillcolor="blue", opacity=0.2)
                fig.add_vline(x=ta["time_peak"], line_width=1, line_dash="dash", line_color="blue")

    return fig
