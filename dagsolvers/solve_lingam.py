
def solve_lingam(X,Y,p):
    import lingam
    model = lingam.VARLiNGAM(lags=p, criterion=None)
    model.fit(X)

    W_est = model._adjacency_matrices[0]
    print(f'NUMBER OF ADJ MATRICES: {len(model._adjacency_matrices)}. DATA RECURSION: {p}')
    A_est = []
    for i in range(p):
        A_est.append(model._adjacency_matrices[i+1])
    return W_est, A_est
