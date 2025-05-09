from sklearn import preprocessing
from sklearn.decomposition import PCA


def standardize(features):
    scaler = preprocessing.StandardScaler().fit(features)
    features = scaler.transform(features)
    print("standardized features")
    return features


def dimension_reduction(features, n_components):
    pca = PCA(n_components=n_components)
    features = pca.fit_transform(features)
    print("PCA performed")
    return features
