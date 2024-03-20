import numpy as np
import pandas as pd
from sklearn import linear_model
import os
from tqdm import tqdm
from sklearn.model_selection import KFold
from sklearn.metrics import confusion_matrix
from sklearn.metrics import classification_report
from sklearn.metrics import mean_squared_error, cohen_kappa_score
from  sklearn import preprocessing
from scipy import stats

import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--data_dir",
                    default="data/spoken_test_2022_jan28",
                    type=str)

parser.add_argument("--model_name",
                    default="librispeech_mct_tdnnf_kaldi_tgt3",
                    type=str)

parser.add_argument("--part",
                    default="3",
                    type=str)

parser.add_argument("--aspect",
                    default="2",
                    type=str)

args = parser.parse_args()

# data/spoken_test_2022_jan28/grader.spk2p3s2
model_name = args.model_name
part = args.part
label_fn = "grader.spk2p" + part + "s" + args.aspect
feats_fn = model_name + "-feats.xlsx"

data_dir = args.data_dir

spk2label = {}
spk2feats = {}

phd1_label = {}
phd2_label = {}

convert_level = {"未達B1":0, "B1":1, "B2": 2}

with open(data_dir + "/grader.spk2p3s2.phd1", "r") as fn:
    for line in fn.readlines():
        info = line.split()
        phd1_label[info[0]] = convert_level[info[1]]

with open(data_dir + "/grader.spk2p3s2.phd2", "r") as fn:
    for line in fn.readlines():
        info = line.split()
        phd2_label[info[0]] = convert_level[info[1]]

# label
with open(os.path.join(data_dir, label_fn), "r") as fn:
    for line in fn.readlines():
        spk, grade = line.split()
        spk2label[spk] = float(grade)

# feats
feats_df = pd.read_excel(os.path.join(data_dir, model_name, feats_fn), dtype=str)
feat_keys = [fk for fk in list(feats_df.keys())[6:] if "list" not in fk and "voiced_probs" not in fk]
feat_keys = np.array(feat_keys)

for i, spk in enumerate(feats_df["spkID"]):
    if feats_df["part"][i] != part: continue
    
    feats_vec = [float(feats_df[fk][i]) for fk in feat_keys]
    spk2feats[spk] = feats_vec

# create example
X, y, spk_list = [], [], []
for spk in list(spk2label.keys()):
    X.append(spk2feats[spk])
    y.append(spk2label[spk])
    spk_list.append(spk)

min_max_scaler = preprocessing.MinMaxScaler()

X = np.array(X)
y = np.array(y)
spk_list = np.array(spk_list)

m = len(y) # Number of training examples
b1_bins = np.array([4.0, 5.0])
all_bins = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
kf = KFold(n_splits=5, random_state=66, shuffle=True)

def report(y_true, y_pred):
    print("Report")
    print(classification_report(y_true, y_pred))
    print(confusion_matrix(y_true, y_pred))
    acc = classification_report(y_true, y_pred, output_dict=True)["accuracy"]
    return acc

acc = {"all": 0, "phd1": 0, "phd2": 0}
infos = ["spk_id", "anno", "anno(cefr)", "pred", "pred(cefr)", "results"]
kfold_info = {"Fold" + str(1+i):{info:[] for info in infos} for i in range(5)}
y_test_cefr_label = {}
y_pred_cefr_label = {}

for i, (train_index, test_index) in enumerate(kf.split(X)):
    print("Fold", (i+1))
    X_train, X_test = X[train_index], X[test_index]
    y_train, y_test = y[train_index], y[test_index]
    
    clf = linear_model.Lasso(alpha=0.1)
    clf.fit(X_train, y_train)
    
    coef_ = clf.coef_[np.nonzero(clf.coef_)]
    feat_nz_keys = feat_keys[np.nonzero(clf.coef_)]
    
    print(feat_nz_keys[np.argsort(-1 * coef_)])
    print(coef_[np.argsort(-1 * coef_)])
    
    y_pred = clf.predict(X_test)
    for ii in range(len(y_test)):
        print(y_test[ii])
    print("-"*10)
    for ii in range(len(y_pred)):
        print(y_pred[ii])
    
    y_test_cefr = np.digitize(np.array(y_test), b1_bins)
    y_pred_cefr = np.digitize(np.array(np.round_(y_pred * 2) / 2), b1_bins)
    print("="*10)
    print("CEFR")
    print(y_test_cefr)
    print(y_pred_cefr)
    print(spk_list[test_index])
    df = pd.DataFrame({"anno": y_test,
                       "pred": y_pred})
    
    acc["all"] += report(y_test_cefr, y_pred_cefr)
    print("PHD1(ACC)")
    y_test_cefr_new = np.copy(y_test_cefr)
    for spk_idx, spk_id in enumerate(spk_list[test_index]):
        if spk_id in phd1_label:
            y_test_cefr_new[spk_idx] = phd1_label[spk_id]
            y_test_cefr_label[spk_id] = y_test_cefr[spk_idx]
            y_pred_cefr_label[spk_id] = y_pred_cefr[spk_idx]
    acc["phd1"] += report(y_test_cefr_new, y_pred_cefr)

    print("PHD2(ACC)")
    y_test_cefr_new = np.copy(y_test_cefr)
    for spk_idx, spk_id in enumerate(spk_list[test_index]):
        if spk_id in phd2_label:
            y_test_cefr_new[spk_idx] = phd2_label[spk_id]
    acc["phd2"] += report(y_test_cefr_new, y_pred_cefr)
    
    print("="*10)
    print("MSE", mean_squared_error(y_test, y_pred))
    print("RMSE", mean_squared_error(y_test, y_pred, squared=False))
    print("="*10)
    print("pearson")
    print(df.corr(method='pearson'))
    print(stats.pearsonr(y_test, y_pred))
    print()
    kfold_info["Fold" + str(i+1)]["spk_id"] += spk_list[test_index].tolist()
    kfold_info["Fold" + str(i+1)]["anno"] += y_test.tolist()
    kfold_info["Fold" + str(i+1)]["anno(cefr)"] += y_test_cefr.tolist()
    kfold_info["Fold" + str(i+1)]["pred"] += y_pred.tolist()
    kfold_info["Fold" + str(i+1)]["pred(cefr)"] += y_pred_cefr.tolist()
    kfold_info["Fold" + str(i+1)]["results"] += (y_pred_cefr - y_test_cefr).tolist()


acc["all"] /= kf.get_n_splits(X)
print("Accuracy(All)", acc["all"])

acc["phd1"] /= kf.get_n_splits(X)
print("Accuracy(phd1)", acc["phd1"])

acc["phd2"] /= kf.get_n_splits(X)
print("Accuracy(phd2)", acc["phd2"])

with pd.ExcelWriter("linear_regression.xlsx") as writer:
    for f in list(kfold_info.keys()):
        df = pd.DataFrame(kfold_info[f])
        df.to_excel(writer, sheet_name=f)

print(y_test_cefr_label)
print(phd1_label)
print(phd2_label)
print("label vs phd1")
y_true, y_pred = [], []
for spk_id in list(y_test_cefr_label.keys()):
    y_true.append(y_test_cefr_label[spk_id])
    y_pred.append(phd1_label[spk_id])
report(y_true, y_pred)
print(cohen_kappa_score(y_true, y_pred, labels=[0,1,2]))

print("label vs phd2")
y_true, y_pred = [], []
for spk_id in list(y_test_cefr_label.keys()):
    y_true.append(y_test_cefr_label[spk_id])
    y_pred.append(phd2_label[spk_id])
report(y_true, y_pred)
print(cohen_kappa_score(y_true, y_pred, labels=[0,1,2]))

print("phn1 vs phn2")
y_true, y_pred = [], []
for spk_id in list(y_test_cefr_label.keys()):
    y_true.append(phd1_label[spk_id])
    y_pred.append(phd2_label[spk_id])
report(y_true, y_pred)
print(cohen_kappa_score(y_true, y_pred, labels=[0,1,2]))

print("pred vs phd1")
y_true, y_pred = [], []
for spk_id in list(y_pred_cefr_label.keys()):
    y_true.append(y_pred_cefr_label[spk_id])
    y_pred.append(phd1_label[spk_id])
report(y_true, y_pred)
print(cohen_kappa_score(y_true, y_pred, labels=[0,1,2]))

print("pred vs phd2")
y_true, y_pred = [], []
for spk_id in list(y_pred_cefr_label.keys()):
    y_true.append(y_pred_cefr_label[spk_id])
    y_pred.append(phd2_label[spk_id])
report(y_true, y_pred)
print(cohen_kappa_score(y_true, y_pred, labels=[0,1,2]))
