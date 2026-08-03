import bnlearn as bn
import numpy as np
from bnlearn import sampling


def load_dataset(name, n, normalize=False, segment_size=10):
    data= name
    if (data=='alarm') or (data=='andes') or (data=='asia') or (data=='sachs') or (data=='water'):
        dag_df = bn.import_DAG(name)['adjmat']
        dag_np = dag_df.to_numpy()
        X = bn.import_example(name).to_numpy()
        print(f'loading {name}')
        print(X.shape)
        n, d = X.shape
        # segments = []
        # for offset in range(0, n, segment_size):
        #     XM = X[offset:offset + segment_size,:].mean(axis=0)
        #     segments.append(XM)
        # #print(segments)
        # result = np.vstack(segments)
        # X = result



    else:
        if name == 'child':
            name = '../data/child.bif'
        dag_df = bn.import_DAG(name)
        adj_mat = dag_df['adjmat']
        dag_np = adj_mat.to_numpy()
        df = sampling(dag_df, n=n, verbose=2)
        X = df.to_numpy()

    print(X.shape)
    if normalize:
        X = X - np.mean(X, axis=0, keepdims=True)
        X = X / np.var(X, axis=0, keepdims=True)
    #print(result)

    # print(dag_df)
    # print(dag_np)
    # print(X.shape)
    return X, dag_np




if __name__ == '__main__':

    load_dataset('asia', 100)
