from os.path import join

import numpy as np
import pandas as pd

def load_dataset(name, data_path, segment_size=10):
    if name == 'alarms':
        alarms = pd.read_csv(join(data_path,'alarm.csv'))

        TIME_WIN_SIZE  = 300
        alarms = alarms.sort_values(by='start_timestamp')
        alarms['win_id'] = alarms['start_timestamp'].map(lambda elem:int(elem/TIME_WIN_SIZE))

        samples=alarms.groupby(['alarm_id','win_id'])['start_timestamp'].count().unstack('alarm_id')
        samples = samples.dropna(how='all').fillna(0)
        samples = samples.sort_index(axis=1)



        true_graph = np.load(r'../data/NeurIPS2023/sample/true_graph.npy')
    else:
        assert False


    X = samples.to_numpy()

    n, d = X.shape
    segments = []
    for offset in range(0, n, segment_size):
        XM = X[offset:offset + segment_size,:].mean(axis=0)
        segments.append(XM)
    #print(segments)
    result = np.vstack(segments)
    X = result


    # print(dag_df)
    print(true_graph)
    print(true_graph.shape)
    print(X.shape)
    return X, true_graph




if __name__ == '__main__':

    load_dataset('gg')
