import os
import numpy as np
import pandas as pd
from tqdm import tqdm

def calculate_baseline_rms(mode, vector, limit):
    if isinstance(vector, (list, np.ndarray)):  # Check if the input is a list or array
        vector = np.array(vector[:limit])

    count  = 0  
    level  = np.mean(vector)
    vector = vector - level
    while count < 10:
            rms   = np.sqrt(np.mean((vector)**2))
            var    = 2 * np.std(vector)
            vector = vector[np.abs(vector - rms) <= var]
            count += 1

    if mode == 'baseline': output = rms + level
    else: output = rms
    return output

def find_endpoint(target_value):
    map_id = {'104': [1, 2, 3, 4], '105': [5, 6, 7, 9], '107': [10, 8], '109': [11], '111': [12], '112': [13], '113': [14]}
    for key, value_list in map_id.items():
        if target_value in value_list:
            return key

def check_pulses(vector, limit, trigger):
    if isinstance(vector, (list, np.ndarray)):  # Check if the input is a list or array
        vector = np.array(vector)
    baseline = calculate_baseline_rms('baseline', vector, limit)
    pulse    = baseline - np.array(vector)
    return 1 if trigger == "self_trigger" and np.max(pulse) > 6 else 0

def calculate_fft(sig):
    dt = 16e-9
    t = np.arange(0, sig.shape[-1]) * dt
    sigFFT = np.fft.fft(sig) / t.shape[0]
    freq = np.fft.fftfreq(t.shape[0], d=dt)
    firstNegInd = np.argmax(freq < 0)
    freqAxisPos = freq[:firstNegInd]
    sigFFTPos = 2 * sigFFT[:firstNegInd]
    return 20 * np.log10(np.abs(sigFFTPos) / 2 ** 14), freqAxisPos

def df_data(input_list):
    if len(input_list) > 80000: input_list = input_list[:80000]
    input_list = sorted(input_list, key=lambda row: (row[1], row[2]))

    reference_endpoint = input_list[0][1]
    reference_channel  = input_list[0][2]

    count          = 0
    total_adcs     = None
    total_trigger  = 0
    total_baseline = 0

    result = []

    for index, line in enumerate(tqdm(input_list, desc="Creating dataframe")):
        trigger       = line[0]
        endpoint      = line[1]
        channel       = line[2]
        baseline      = calculate_baseline_rms('baseline', np.array(line[3])[:50], 50)
        adcs          = baseline - np.array(line[3])
        trigger_count = check_pulses(line[3][120:150], 50, trigger)

        if endpoint == reference_endpoint and channel == reference_channel:
            if total_adcs is not None:  # Check if total_adcs is initialized
                total_adcs += adcs
            else:
                total_adcs = adcs
            count          += 1
            total_trigger  += trigger_count
            total_baseline += baseline

        elif endpoint != reference_endpoint or channel != reference_channel:
            result.append([reference_endpoint, reference_channel, total_adcs/count, total_baseline/ count, total_trigger])
            
            total_trigger  = trigger_count

            total_adcs = adcs
            count      =  1
            total_baseline     = baseline
            reference_endpoint = endpoint
            reference_channel  = channel

        if index == len(input_list) - 1:
            result.append([reference_endpoint, reference_channel, total_adcs/count, total_baseline/ count, total_trigger])
            
    df = pd.DataFrame(result, columns=['endpoint', 'channel', 'waveforms', 'baseline', 'trigger_count'])
    df['endpoint'] = df['endpoint'].astype(int)-100
    df['channel']  = df['channel'].astype(int)
    df['rms']      = df.apply(lambda x: calculate_baseline_rms('rms', x['waveforms'][:50], 50), axis=1)
    return df

def df_channel_map(df):
    if 'endpoint' not in df.columns:
        if 'src_id' in df.columns:
            df['endpoint'] = df.apply(lambda x: int(find_endpoint(x['src_id']))-100, axis=1)
            df.columns = ['src_id','channel','waveforms','endpoint']

    share_path = os.environ.get('DQMTOOLS_SHARE')
    path = share_path + "/config/APAchannelmap.txt"
    
    map_channel = pd.read_csv(path, sep="\s+", header=None).astype('int')
    map_channel.columns = ["endpoint", "link", "channel", "position"]
    map_channel["col_position"] = map_channel["position"]//10
    map_channel["row_position"] = map_channel["position"] - 10*map_channel["col_position"]
    map_channel["real_col_position"] = 15 - map_channel["col_position"] 

    df = pd.merge(df, map_channel, how="left", on=["endpoint", "channel"])

    return df
