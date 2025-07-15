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

def empty_plot(text="NO DATA"):

    fig_none = go.Figure()
    fig_none.update_layout(
        xaxis = { "visible": False },
        yaxis = { "visible": False },
        annotations = [
            {
                "text": text,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {
                    "size": 40
                }
            }
        ]
    )
    return fig_none

    fig_none.add_trace(go.Scatter(
        x=[0,1,2],
        y=[0,1,2],
        mode="lines+markers+text",
        text=["",text,""],
        textfont_size=40,
    ))
    fig_none.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white"
    )
    fig_none.update_layout(
        xaxis = dict(
            showgrid=False,
            gridcolor="white",
            zerolinecolor="white"),
        yaxis = dict(
            showgrid=False,
            gridcolor="white",
            zerolinecolor="white"))

    return fig_none

