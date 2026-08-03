from os.path import join
import numpy as np


def load_data(variant, normalize, data_path):
    if variant == 1:
        filename = '1_cd3cd28'
    elif variant == 2:
        filename = '2_cd3cd28icam2'
    elif variant == 3:
        filename = '3_cd3cd28+aktinhib'
    elif variant == 4:
        filename = '4_cd3cd28+g0076'
    elif variant == 5:
        filename = '5_cd3cd28+psitect'
    elif variant == 6:
        filename = '6_cd3cd28+u0126'
    elif variant == 7:
        filename = '7_cd3cd28+ly'
    elif variant == 8:
        filename = '8_pma'
    elif variant == 9:
        filename = '9_b2camp'
    elif variant == 10:
        filename = '10_cd3cd28icam2+aktinhib'
    else:
        assert False

    X = np.loadtxt(join(data_path, filename + '.csv'), delimiter=',', skiprows=1, usecols=(0, 1,2,3,4,5,6,7,8,9,10))  # (0, 5, 2, 8, 7, 3,4, 1,9,10,6))
    if normalize:

        # meane = np.mean(X, axis=0, keepdims=True)
        X = X - np.mean(X, axis=0, keepdims=True)
        X = X / np.var(X, axis=0, keepdims=True)
        print('normalizing')
        #X = X[:1000,:]

    B_true = np.loadtxt(join(data_path, 'sachs_true.csv'), delimiter=',', skiprows=1, usecols=(1,2,3,4,5,6,7,8,9,10,11))

    W_true = B_true.copy()
    return X, B_true, W_true