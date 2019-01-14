import numpy as np 

import sys 
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.helpers import get_dir_names,extract_frames,bb_intersection_over_union,extract_trajectories
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler,MinMaxScaler

ROOT = "./../"
CSV = ROOT + "extractors/csv/"

class Extractor:
    def __init__(self,selected_extractor = 0):
        self.selected_extractor = selected_extractor
        
    def extract(self,trajectories):
        if self.selected_extractor == 0:
            return self.extract_first_last(trajectories)

    def extract_first_last(self,trajectories):
        features = []
        for trajectory in trajectories:
            first_point = trajectory[0]
            last_point = trajectory[-1]
            features.append([first_point[0],first_point[1],last_point[0],last_point[1]])
        return features

class Clusterer:
    def __init__(self,selected_clusterer = 0,nb_clusters = 20 ,random_state = 0):
        self.nb_clusters = nb_clusters
        self.random_state = random_state
        self.selected_clusterer = selected_clusterer

    def cluster(self,features):
        if self.selected_clusterer == 0:
            return self.cluster_kmeans(features)

    def cluster_kmeans(self,features):
        
        cl = KMeans(n_clusters= self.nb_clusters, random_state= self.random_state)    
        # std = StandardScaler()
        std = MinMaxScaler()
        features_std = std.fit_transform(features)
        clusters = cl.fit_predict(features_std)        

        return clusters

def multi_step_clustering(file_path,extractors,clusterers):
    trajectories = extract_trajectories(file_path)
    multistep_clusters = []
    multistep_clusters.append({})
    multistep_clusters[0]["0"] = [key for key in trajectories]


    for extractor,clusterer in zip(extractors,clusterers):
       
        clusters = multistep_clusters[-1]

        cluster_nb = 0
        new_clusters = {}
        for key in clusters:
            trajectories_coordinates = []
            for id_ in clusters[key]:
                trajectories_coordinates.append(trajectories[id_]["coordinates"])
            features = extractor.extract(trajectories_coordinates)
            trajectories_label = clusterer.cluster(features)

            sub_clusters = {}

            for i,label in enumerate(trajectories_label):
                if label not in sub_clusters:
                    sub_clusters[label] = []
                sub_clusters[label].append(clusters[key][i])
            for key1 in sub_clusters:
                new_clusters[cluster_nb] = sub_clusters[key1]
                cluster_nb += 1
        multistep_clusters.append(new_clusters)
    return multistep_clusters

def main():


    file_path = CSV + "new_rates/deathCircle1_30.0to2.5.csv"
    

    clusterers = [Clusterer(selected_clusterer= 0),Clusterer(nb_clusters= 5, selected_clusterer= 0 )]
    extractors = [Extractor(0),Extractor(0)]
    multistep_clusters = multi_step_clustering(file_path,extractors,clusterers)




if __name__ == "__main__":
    main()