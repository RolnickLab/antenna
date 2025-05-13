import numpy as np
from sklearn.metrics import adjusted_mutual_info_score as ami_score
from sklearn.metrics import adjusted_rand_score as ari_score
from sklearn.metrics.cluster import normalized_mutual_info_score as nmi_score

from .estimate_k import cluster_acc


def pairwise_cost(y_true, y_pred, split_cost=1, merge_cost=2):
    true_match = y_true[:, None] == y_true
    pred_match = y_pred[:, None] == y_pred

    split = true_match & ~pred_match  # true labels same, but cluster labels different
    merge = ~true_match & pred_match  # true labels different, but cluster labels same

    cost = np.sum(np.triu(split * split_cost | merge * merge_cost, k=1))

    return cost


def get_clustering_metrics(labels, preds, old_mask, split_cost, merge_cost):
    all_acc, ind, _ = cluster_acc(labels.astype(int), preds.astype(int), return_ind=True)

    cluster_mapping = {pair[0]: pair[1] for pair in ind}

    preds = np.array([cluster_mapping[c] for c in preds])

    all_nmi, all_ari, all_ami = (
        nmi_score(labels, preds),
        ari_score(labels, preds),
        ami_score(labels, preds),
    )

    all_pw_cost = pairwise_cost(labels, preds, split_cost, merge_cost)

    old_preds = preds[old_mask]
    new_preds = preds[~old_mask]

    old_gt = labels[old_mask]
    new_gt = labels[~old_mask]

    old_acc, old_nmi, old_ari, old_ami = (
        cluster_acc(old_gt.astype(int), old_preds.astype(int)),
        nmi_score(old_gt, old_preds),
        ari_score(old_gt, old_preds),
        ami_score(old_gt, old_preds),
    )

    old_pw_cost = pairwise_cost(old_gt, old_preds, split_cost, merge_cost)

    new_acc, new_nmi, new_ari, new_ami = (
        cluster_acc(new_gt.astype(int), new_preds.astype(int)),
        nmi_score(new_gt, new_preds),
        ari_score(new_gt, new_preds),
        ami_score(new_gt, new_preds),
    )

    new_pw_cost = pairwise_cost(new_gt, new_preds, split_cost, merge_cost)

    metrics = {
        "ACC_all": all_acc,
        "NMI_all": all_nmi,
        "ARI_all": all_ari,
        "AMI_all": all_ami,
        "pw_cost_all": all_pw_cost,
        "ACC_old": old_acc,
        "NMI_old": old_nmi,
        "ARI_old": old_ari,
        "AMI_old": old_ami,
        "pw_cost_old": old_pw_cost,
        "ACC_new": new_acc,
        "NMI_new": new_nmi,
        "ARI_new": new_ari,
        "AMI_new": new_ami,
        "pw_cost_new": new_pw_cost,
    }

    return metrics
