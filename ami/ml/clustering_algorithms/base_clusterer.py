import os

import numpy as np

from .preprocessing_features import dimension_reduction, standardize


class BaseClusterer:
    def __init__(self, config):
        self.config = config
        self.setup_flag = False
        self.data_dict = None

    def setup(self, data_dict):
        new_data_dict = {}
        save_dir = self.config.output_dir
        if not self.setup_flag:
            for data_type in data_dict:
                new_data_dict[data_type] = {}
                features = data_dict[data_type]["feat_list"]
                features = dimension_reduction(standardize(features), self.config.pca.n_components)
                labels = data_dict[data_type]["label_list"]
                new_data_dict[data_type]["feat_list"] = features
                new_data_dict[data_type]["label_list"] = labels

                np.savez(
                    os.path.join(
                        save_dir,
                        f"{data_type}_processed_pca_{self.config.pca.n_components}",
                    ),
                    feat_list=features,
                    label_list=labels,
                )
            self.data_dict = new_data_dict
            self.setup_flag = True
        else:
            pass

    def clustering(self, data_dict):
        pass

    def cluster_detections(self, data_dict):
        pass
