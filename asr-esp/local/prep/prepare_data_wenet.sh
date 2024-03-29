#!/usr/bin/env bash

stage=0
stop_stage=10000
data_name=spoken_test_2022_jan28
model_name=wenet_gigaspeech
model_tag="/share/nas167/teinhonglo/AcousticModel/spoken_test/models/20210728_u2pp_conformer_libtorch"
replace_text=false
use_streaming=false
data_root=data
# vad parameters
vad_mode=0
max_segment_length=15

. ./cmd.sh
. ./path.sh
. utils/parse_options.sh

set -euo pipefail

if [ ${stage} -le -3 ] && [ ${stop_stage} -ge -3 ]; then
    find $data_root/$data_name -name "*.wav" -size -45k
    exit 0;
fi

if [ ${stage} -le -2 ] && [ ${stop_stage} -ge -2 ]; then
    ./local/prep/create_decode_data.sh --data_root $data_root --test_sets "$data_name"
fi

if [ ${stage} -le -1 ] && [ ${stop_stage} -ge -1 ]; then
    python local/prep/repair_and_resample.py --data_dir $data_root/$data_name
fi

if [ ${stage} -le 0 ] && [ ${stop_stage} -ge 0 ]; then
    ./local/e2e_stt/extract_feats_wenet.sh --data_root $data_root --data_sets $data_name \
                                    --model_name $model_name --model_tag "$model_tag" \
                                    --vad_mode $vad_mode --max_segment_length $max_segment_length --use_streaming $use_streaming
    
    dest_dir=$data_root/$data_name/$model_name
    
    if [ $replace_text == "true" ]; then
        cp $dest_dir/text $data_root/$data_name/text
    fi
fi

if [ ${stage} -le 1 ] && [ ${stop_stage} -ge 1 ]; then
    dest_dir=$data_root/$data_name/$model_name
    ./local/prep/prepare_xlsx.sh --data_root $data_root --data_name $data_name --dest_dir $dest_dir
fi
