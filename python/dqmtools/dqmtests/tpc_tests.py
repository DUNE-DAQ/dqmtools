from dqmtools.dqmtools import *
from rawdatautils.unpack.dataclasses import *

import numpy as np
import operator

class CheckNFrames_TPC(DQMTest):

    def __init__(self,frag_type = "WIBEth"):
        super().__init__()
        self.name = f"CheckNFrames_{frag_type}_TPC"
        self.frag_type = frag_type

    def run_test(self,df_dict):
        expected_frag_number = {
            "WIBEth" : 12,
            "TDEEth" : 15
        }
        den = {
            "WIBEth" : 32,
            "TDEEth" : 31
        }

        df_tmp = df_dict["frh"].loc[df_dict["frh"]["fragment_type"]==expected_frag_number[self.frag_type]][["window_begin_dts","window_end_dts"]]
        if len(df_tmp)==0:
            return DQMTestResult(DQMResultEnum.WARNING,f'WARNING: No {self.frag_type} components found.')

        df_tmp["expected_frames"] = np.floor((df_tmp["window_end_dts"]-df_tmp["window_begin_dts"])/(den[self.frag_type]*64))+1
        df_tmp = df_tmp.join(df_dict["daqh"][["n_obj"]])
        df_tmp["nframe_difference"] = df_tmp["expected_frames"]-df_tmp["n_obj"]
        n_frames_wrong = (abs(df_tmp["nframe_difference"])>=2).sum()
        if n_frames_wrong==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_frames_wrong} / {len(df_tmp)}{self.frag_type} fragments have the wrong number of frames.')

class InitialHitThreshold_TPC(DQMTest):

    def __init__(self,det_name,multiplier=3,verbose=False,frag_type="WIBEth"):
        super().__init__()
        self.name = f'CheckRMS_{det_name}'
        self.det_data_key=f'detd_k{det_name}_k{frag_type}'
        self.multiplier = multiplier
        self.verbose = verbose

    def run_test(self,df_dict):

        if self.det_data_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'Could not find {self.det_data_key} in DataFrame dict.')
        
        df_tmp = df_dict[self.det_data_key].reset_index()
        result_df = []
        for e in pd.unique(df_tmp["element"]):
            for p in pd.unique(df_tmp["plane"]):
                mask = (df_tmp["element"] == e) & (df_tmp["plane"] == p)
                rms = np.mean(df_tmp[mask]["adc_rms"])
                result_df.append({"plane" : p, "elemnt" : e, f"basline hit threshold ({self.multiplier} x RMS)" : self.multiplier*rms})

        return DQMTestResult(DQMResultEnum.OK,"", pd.DataFrame(result_df))

class CheckRMS_TPC(DQMTest):

    def __init__(self,det_name,threshold=100,operator=operator.gt,verbose=False,frag_type="WIBEth"):
        super().__init__()
        self.name = f'CheckRMS_{det_name}'
        self.det_data_key=f'detd_k{det_name}_k{frag_type}'

        if not isinstance(threshold,list): #one value for all planes
            self.df_threshold = pd.DataFrame({"plane":[0,1,2],"threshold":np.full(3,threshold)})
        elif len(threshold)==1: #one value for all planes
            self.df_threshold = pd.DataFrame({"plane":[0,1,2],"threshold":np.full(3,threshold[0])})
        elif len(threshold)==2: #two values, first induction, second collection
            self.df_threshold = pd.DataFrame({"plane":[0,1,2],"threshold":np.array([threshold[0],threshold[0],threshold[1]])})
        elif len(threshold)==3: #three values, one for each plane
            self.df_threshold = pd.DataFrame({"plane":[0,1,2],"threshold":np.array(threshold)})
        else:
            print(f'Threshold length {len(threshold)} is not valid.',threshold)
            raise ValueError
        self.operator = operator
        self.verbose = verbose
        

    def run_test(self,df_dict):

        if self.det_data_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'Could not find {self.det_data_key} in DataFrame dict.')
        
        df_tmp = df_dict[self.det_data_key].reset_index().merge(self.df_threshold,on=["plane"])
        df_tmp = df_tmp[["channel","adc_rms","threshold"]].groupby(by="channel").mean().reset_index()
        df_tmp = df_tmp.loc[self.operator(df_tmp["adc_rms"],df_tmp["threshold"])]

        rms_bad = np.unique(df_tmp["channel"])
        n_rms_bad = len(rms_bad)

        if n_rms_bad==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')

        else:
            if self.verbose:
                print("CHANNELS FAILING RMS CHECK")
                print(f"operator {str(self.operator)} ({self.operator.__doc__})")
                df_tmp = df_tmp.merge(df_dict[self.det_data_key].reset_index()[["channel","element","plane"]].drop_duplicates(["channel"]),on=["channel"])
                print(tabulate(df_tmp.reset_index()[["channel","adc_rms","element","plane","threshold"]],
                               headers=["Channel","RMS","APA/CRP","Plane","Threshold"],
                               showindex=False,tablefmt='pretty',floatfmt=".2f"))
            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_rms_bad} channels have RMS outside of range.', df_tmp)

class CheckPedestal_TPC(DQMTest):

    def __init__(self,det_name,lower_bound=[7500,200],upper_bound=[9500,2000],verbose=False,frag_type="WIBEth"):
        super().__init__()
        self.name = f'CheckPedestal_{det_name}'
        self.det_data_key=f'detd_k{det_name}_k{frag_type}'

        if not isinstance(lower_bound,list): #one value for all planes
            self.df_lower_bound = pd.DataFrame({"plane":[0,1,2],"lower_bound":np.full(3,lower_bound)})
        elif len(lower_bound)==1: #one value for all planes
            self.df_lower_bound = pd.DataFrame({"plane":[0,1,2],"lower_bound":np.full(3,lower_bound[0])})
        elif len(lower_bound)==2: #two values, first induction, second collection
            self.df_lower_bound = pd.DataFrame({"plane":[0,1,2],"lower_bound":np.array([lower_bound[0],lower_bound[0],lower_bound[1]])})
        elif len(lower_bound)==3: #three values, one for each plane
            self.df_lower_bound = pd.DataFrame({"plane":[0,1,2],"lower_bound":np.array(lower_bound)})
        else:
            print(f'Lower_Bound length {len(lower_bound)} is not valid.',lower_bound)
            raise ValueError

        if not isinstance(upper_bound,list): #one value for all planes
            self.df_upper_bound = pd.DataFrame({"plane":[0,1,2],"upper_bound":np.full(3,upper_bound)})
        elif len(upper_bound)==1: #one value for all planes
            self.df_upper_bound = pd.DataFrame({"plane":[0,1,2],"upper_bound":np.full(3,upper_bound[0])})
        elif len(upper_bound)==2: #two values, first induction, second collection
            self.df_upper_bound = pd.DataFrame({"plane":[0,1,2],"upper_bound":np.array([upper_bound[0],upper_bound[0],upper_bound[1]])})
        elif len(upper_bound)==3: #three values, one for each plane
            self.df_upper_bound = pd.DataFrame({"plane":[0,1,2],"upper_bound":np.array(upper_bound)})
        else:
            print(f'Upper_Bound length {len(upper_bound)} is not valid.',upper_bound)
            raise ValueError

        self.verbose = verbose
        

    def run_test(self,df_dict):

        if self.det_data_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'Could not find {self.det_data_key} in DataFrame dict.')
        
        df_tmp = df_dict[self.det_data_key].reset_index().merge(self.df_lower_bound,on=["plane"]).merge(self.df_upper_bound,on=["plane"])
        df_tmp = df_tmp[["channel","adc_mean","lower_bound","upper_bound"]].groupby(by="channel").mean().reset_index()
        df_tmp = df_tmp.loc[(df_tmp["adc_mean"]<df_tmp["lower_bound"])|(df_tmp["adc_mean"]>df_tmp["upper_bound"])]
        n_bad = len(np.unique(df_tmp["channel"]))
        if n_bad==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            if self.verbose:
                print("CHANNELS FAILING PEDESTAL CHECK")
                df_tmp = df_tmp.merge(df_dict[self.det_data_key].reset_index()[["channel","element","plane"]].drop_duplicates(["channel"]),on=["channel"])
                print(tabulate(df_tmp.reset_index()[["channel","adc_mean","element","plane","lower_bound","upper_bound"]],
                               headers=["Channel","Pedestal","APA/CRP","Plane","Lower Bound","Upper Bound"],
                               showindex=False,tablefmt='pretty',floatfmt=".2f"))
            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_bad} channels have pedestal outside of range.')
