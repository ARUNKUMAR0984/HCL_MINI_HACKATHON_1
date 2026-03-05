import pandas as pd
from sklearn.cluster import KMeans

def cluster_orders(orders, vehicles):

    coords = orders[['latitude','longitude']]

    kmeans = KMeans(n_clusters=vehicles, random_state=0)

    orders['vehicle'] = kmeans.fit_predict(coords)

    return orders