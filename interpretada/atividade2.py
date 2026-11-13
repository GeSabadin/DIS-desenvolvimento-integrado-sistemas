"""Atividade 2: operacoes basicas MN = M*N, aM = a*M, Ma = M*a com numpy (BLAS)."""
import os
AQUI = os.path.dirname(os.path.abspath(__file__))
import numpy as np

D = os.path.join(AQUI, '..', 'data', 'dados_teste')
ld = lambda n: np.loadtxt(os.path.join(D, n), delimiter=';', ndmin=2)
M, N, a = ld('M.csv'), ld('N.csv'), ld('a.csv')

MN = M @ N
aM = a @ M          # (1x10)(10x10) -> 1x10
Ma = M @ a.T        # (10x10)(10x1) -> 10x1

print('MN == MN.csv ?', np.allclose(MN, ld('MN.csv')))
print('aM == aM.csv ?', np.allclose(aM, ld('aM.csv'), atol=0.01))
print('Ma =', Ma.ravel().round(2))
