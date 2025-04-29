import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *

try:
    import pandas as pd
except ModuleNotFoundError as err:
    print(err)
    print("\n\n")
    print("Missing module is likely not part of standard dunedaq releases.")
    print("\n")
    print("Please install the missing module and try again.")
    sys.exit(1)
except:
    raise

def get_CERN_timestamp(df_dict,index):
    trigger_time = df_dict['trh'].loc[(index.run,index.trigger,index.sequence)]["trigger_time"]
    return trigger_time.astimezone(pytz.timezone("Europe/Zurich"))

def _rename_PD2HD_APAs(apa_name):
    if(apa_name=="APA_P02SU"): return "APA1"
    if(apa_name=="APA_P01SU"): return "APA2"
    if(apa_name=="APA_P02NL"): return "APA3"
    if(apa_name=="APA_P01NL"): return "APA4"
    return apa_name

def rename_PD2HD_APAs(df_dict):
    for key, val in df_dict.items():
        if "apa" in val.columns:
            val["apa"] = val["apa"].apply(_rename_PD2HD_APAs)
