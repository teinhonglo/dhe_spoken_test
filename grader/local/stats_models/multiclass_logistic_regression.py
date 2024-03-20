import numpy as np
import pandas as pd
from sklearn import linear_model
import os
from tqdm import tqdm
from sklearn.model_selection import KFold
from sklearn.metrics import confusion_matrix
from sklearn.metrics import classification_report
from sklearn.metrics import mean_squared_error
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

def report(y_test, y_pred, spk_list, bins, kfold_info, fold="Fold1"):
    print("=" * 10, "Raw data", "=" * 10)
    y_test_cefr = np.digitize(np.array(y_test), bins)
    y_pred_cefr = y_pred
    print("spk_list, y_test, y_test_cefr, y_pred, y_pred_cefr")
    for i in range(len(spk_list)):
        print(spk_list[i], y_test[i], y_test_cefr[i], y_pred[i], y_pred_cefr[i])
    print("="* 10)
    
    print("="*10, "Coefficient", "=" * 10)
    print("MSE", mean_squared_error(y_test, y_pred))
    print("RMSE", mean_squared_error(y_test, y_pred, squared=False))
    print("Pearson")
    df = pd.DataFrame({"anno": y_test,
                       "pred": y_pred})
    print(df.corr(method='pearson'))
    print(stats.pearsonr(y_test, y_pred))
     
    print("="*10, "Classification", "=" * 10)
    print(classification_report(y_test_cefr, y_pred_cefr))
    print(confusion_matrix(y_test_cefr, y_pred_cefr))
    print()
    acc = classification_report(y_test_cefr, y_pred_cefr, output_dict=True)["accuracy"]
    
    kfold_info[fold]["spk_id"] += spk_list.tolist()
    kfold_info[fold]["anno"] += y_test.tolist()
    kfold_info[fold]["anno(cefr)"] += y_test_cefr.tolist()
    kfold_info[fold]["pred"] += y_pred.tolist()
    kfold_info[fold]["pred(cefr)"] += y_pred_cefr.tolist()
    kfold_info[fold]["results"] += (y_pred_cefr - y_test_cefr).tolist()
    
    return acc, kfold_info


acc = 0
infos = ["spk_id", "anno", "anno(cefr)", "pred", "pred(cefr)", "results"]
kfold_info = {"Fold" + str(1+i):{info:[] for info in infos} for i in range(5)}

for i, (train_index, test_index) in enumerate(kf.split(X)):
    print("Fold", (i+1))
    X_train, X_test = X[train_index], X[test_index]
    y_train, y_test = y[train_index], y[test_index]
    
    y_train_cefr = np.digitize(np.array(y_train), b1_bins)
    
    clf = linear_model.LogisticRegression()
    clf.fit(X_train, y_train_cefr)
    
    #coef_ = clf.coef_[np.nonzero(clf.coef_)]
    #feat_nz_keys = feat_keys[np.nonzero(clf.coef_)]
    
    #print("=" * 10, "Feature Importance", "=" * 10)
    #print(feat_nz_keys[np.argsort(-1 * coef_)])
    #print(coef_[np.argsort(-1 * coef_)])
    
    y_pred = clf.predict(X_test)
    fold_acc, kfold_info = report(y_test, y_pred, spk_list[test_index], b1_bins, kfold_info, "Fold" + str(i+1))
    acc += fold_acc
    
acc /= kf.get_n_splits(X)
print("Accuracy", acc)

with pd.ExcelWriter("linear_regression.xlsx") as writer:
    for f in list(kfold_info.keys()):
        df = pd.DataFrame(kfold_info[f])
        df.to_excel(writer, sheet_name=f)
    
